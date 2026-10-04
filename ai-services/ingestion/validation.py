"""
Requirement 1, step 2: Validation — deterministic checks only, no AI here.

Checks, in order:
  1. Missing/null values           -> check_nulls
  2. Data type consistency         -> check_dtype_consistency
  3. Format/pattern validation     -> check_format_patterns
  4. Business-rule validation      -> rules_engine.apply_rules (reused)
  5. Duplicate detection           -> check_duplicates
  6. Range/anomaly detection       -> rules_engine.detect_statistical_anomalies (reused)
  7. Schema drift                  -> check_schema_drift

Cross-field consistency is deliberately not implemented yet — deferred
until there are real cross-field relationships to check against.

Reuses the existing rules_engine (business rules + IQR outlier detection)
and the existing mapping module (value-similarity scoring, for schema
drift rename detection) rather than reimplementing either.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from mapping import FieldProfile, suggest_mappings
from rules_engine import apply_rules, detect_statistical_anomalies, load_rules

logger = logging.getLogger("onerecon.ingestion.validation")

_KEY_FIELD_PATTERN = re.compile(r"id|key", re.IGNORECASE)


@dataclass
class SchemaSnapshot:
    """A minimal, storable record of a source's shape — columns, dtypes,
    and a small sample of values per column (not the full dataset), kept
    specifically so a *later* load can detect a renamed field even after
    the original data is gone. Small enough to persist cheaply per source."""

    columns: list[str]
    dtypes: dict[str, str]
    samples: dict[str, list] = field(default_factory=dict)


@dataclass
class ValidationReport:
    null_issues: list[dict] = field(default_factory=list)
    dtype_issues: list[dict] = field(default_factory=list)
    format_issues: list[dict] = field(default_factory=list)
    business_rule_violations: list[dict] = field(default_factory=list)
    duplicate_issues: list[dict] = field(default_factory=list)
    outliers: list[dict] = field(default_factory=list)
    schema_drift: dict = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return bool(
            self.null_issues
            or self.dtype_issues
            or self.format_issues
            or self.business_rule_violations
            or self.duplicate_issues
            or self.outliers
            or self.schema_drift.get("new_columns")
            or self.schema_drift.get("removed_columns")
            or self.schema_drift.get("renamed_fields")
            or self.schema_drift.get("type_changes")
        )

    def to_dict(self) -> dict:
        return {
            "null_issues": self.null_issues,
            "dtype_issues": self.dtype_issues,
            "format_issues": self.format_issues,
            "business_rule_violations": self.business_rule_violations,
            "duplicate_issues": self.duplicate_issues,
            "outliers": self.outliers,
            "schema_drift": self.schema_drift,
            "has_issues": self.has_issues,
        }


# ---------- 1. Missing/null values ----------

def check_nulls(df: pd.DataFrame, max_null_ratio: float = 0.0) -> list[dict]:
    """Flags any column whose null ratio exceeds max_null_ratio.
    Default is 0.0 — any unexpected null is flagged; callers can loosen
    this per-field later once real tolerances are known."""
    issues = []
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        if null_count == 0:
            continue
        ratio = null_count / len(df) if len(df) else 0.0
        if ratio > max_null_ratio:
            issues.append(
                {
                    "field": col,
                    "null_count": null_count,
                    "null_ratio": round(ratio, 4),
                }
            )
    logger.info("check_nulls: %d field(s) with unexpected nulls", len(issues))
    return issues


# ---------- 2. Data type consistency ----------

def check_dtype_consistency(df: pd.DataFrame, expected_dtypes: dict[str, str] | None = None) -> list[dict]:
    """
    Two kinds of dtype problem, both flagged:
    1. Mixed types within a single column (some rows numeric, some text)
       — inferred generically, no expected schema required.
    2. A column's dtype no longer matches a previously known dtype, if
       expected_dtypes is given.
    """
    issues = []
    for col in df.columns:
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        inferred_types = non_null.map(lambda v: type(v).__name__).unique()
        if len(inferred_types) > 1:
            issues.append(
                {
                    "field": col,
                    "issue": "mixed_types_within_column",
                    "types_found": sorted(inferred_types.tolist()),
                }
            )

    if expected_dtypes:
        for col, expected in expected_dtypes.items():
            if col not in df.columns:
                continue
            actual = str(df[col].dtype)
            if actual != expected:
                issues.append(
                    {
                        "field": col,
                        "issue": "dtype_changed_since_last_load",
                        "expected": expected,
                        "actual": actual,
                    }
                )
    logger.info("check_dtype_consistency: %d issue(s)", len(issues))
    return issues


# ---------- 3. Format/pattern validation ----------

def _shape_signature(value) -> str:
    """
    A length + character-class signature, not a literal regex — this is
    what makes it work without any column-specific configuration. A hex
    ID's *exact* characters vary row to row, but "16 characters, made of
    digits and uppercase letters" is stable; that's what gets compared.
    Punctuation characters are kept literally (e.g. '-' vs '/') so a
    genuine separator change inside an otherwise-consistent column (like
    a date field) still shows up as a shape difference.
    """
    s = str(value)
    classes: set[str] = set()
    for ch in s:
        if ch.isdigit():
            classes.add("digit")
        elif ch.isupper():
            classes.add("upper")
        elif ch.islower():
            classes.add("lower")
        elif ch.isspace():
            classes.add("space")
        elif ch.isalnum():
            classes.add("alnum")
        else:
            classes.add(f"punct:{ch}")
    return f"len={len(s)};classes={','.join(sorted(classes))}"


def check_format_patterns(
    df: pd.DataFrame, min_dominant_ratio: float = 0.8, min_sample: int = 10
) -> list[dict]:
    """
    For each text-like column, checks whether one "shape" clearly
    dominates (>= min_dominant_ratio of values) and, if so, flags the
    values that don't match it. Columns with no dominant shape at all
    (free text like a description field) are silently skipped rather
    than flagged — there's nothing to be inconsistent with.
    """
    issues = []
    for col in df.columns:
        non_null = df[col].dropna()
        if len(non_null) < min_sample:
            continue
        if pd.api.types.is_numeric_dtype(non_null) or pd.api.types.is_datetime64_any_dtype(non_null):
            continue

        shapes = non_null.astype(str).map(_shape_signature)
        shape_counts = shapes.value_counts()
        dominant_shape = shape_counts.index[0]
        dominant_ratio = shape_counts.iloc[0] / len(shapes)
        if dominant_ratio < min_dominant_ratio:
            continue

        deviating_mask = shapes != dominant_shape
        deviating_count = int(deviating_mask.sum())
        if deviating_count == 0:
            continue

        issues.append(
            {
                "field": col,
                "dominant_format": dominant_shape,
                "dominant_ratio": round(float(dominant_ratio), 4),
                "deviating_count": deviating_count,
                "examples": non_null[deviating_mask].head(5).tolist(),
            }
        )
    logger.info("check_format_patterns: %d field(s) with format inconsistencies", len(issues))
    return issues


# ---------- 5. Duplicate detection ----------

def check_duplicates(
    df: pd.DataFrame,
    key_fields: list[str] | None = None,
    min_uniqueness_ratio_for_auto_detect: float = 0.9,
) -> list[dict]:
    """
    Two kinds of duplicate, both flagged:
    1. Full-row duplicates — always checked.
    2. Duplicate values within a key field — checked for whichever fields
       are named in key_fields (always checked, since the caller has
       explicitly said these should be unique), plus, if key_fields
       wasn't given, any column whose name contains "id" or "key"
       (case-insensitive) AND whose values are mostly-but-not-entirely
       unique (>= min_uniqueness_ratio_for_auto_detect).

       That uniqueness filter matters: a name like "fa_key" matches the
       pattern but is legitimately a many-to-one account reference (many
       transactions sharing one account) — nowhere near unique by design.
       Auto-flagging it would be a false positive on every single load.
       A column that's genuinely supposed to be a unique identifier looks
       almost entirely unique with only a few accidental repeats, which
       is what this ratio is checking for instead of just the name.
    """
    issues = []

    dup_mask = df.duplicated(keep=False)
    if dup_mask.any():
        issues.append(
            {
                "type": "full_row_duplicate",
                "field": None,
                "duplicate_row_count": int(dup_mask.sum()),
                "example_rows": df.index[dup_mask].tolist()[:5],
            }
        )

    if key_fields is not None:
        candidate_fields = list(key_fields)
    else:
        candidate_fields = []
        for col in df.columns:
            if not _KEY_FIELD_PATTERN.search(col):
                continue
            non_null = df[col].dropna()
            if non_null.empty:
                continue
            uniqueness_ratio = non_null.nunique() / len(non_null)
            if uniqueness_ratio >= min_uniqueness_ratio_for_auto_detect:
                candidate_fields.append(col)
            else:
                logger.info(
                    "check_duplicates: skipping auto-detected candidate %r "
                    "(uniqueness ratio %.3f looks like a many-to-one field, not a key)",
                    col, uniqueness_ratio,
                )

    for col in candidate_fields:
        if col not in df.columns:
            logger.warning("check_duplicates: key field %r not in dataframe columns", col)
            continue
        value_counts = df[col].value_counts()
        dup_values = value_counts[value_counts > 1]
        if not dup_values.empty:
            issues.append(
                {
                    "type": "duplicate_key_value",
                    "field": col,
                    "duplicate_value_count": int(len(dup_values)),
                    "duplicate_row_count": int(dup_values.sum()),
                    "examples": dup_values.head(5).index.tolist(),
                }
            )
    logger.info("check_duplicates: %d issue(s)", len(issues))
    return issues


# ---------- 7. Schema drift ----------

def check_schema_drift(current: SchemaSnapshot, reference: SchemaSnapshot | None) -> dict:
    """
    Compares the current schema to a reference (the last known-good load
    for this source). No reference means this is the first load — nothing
    to drift from.

    Rename detection: a column that disappeared and a column that appeared
    are flagged as "possibly renamed" when their sample values overlap
    strongly. Values for the removed column come from the reference
    snapshot's stored samples — the data itself is long gone by the time
    the next load happens, which is exactly why SchemaSnapshot keeps a
    small sample per column instead of just names and types. Reuses the
    same value-similarity scoring the AI mapping fallback uses.
    """
    if reference is None:
        return {"new_columns": [], "removed_columns": [], "renamed_fields": [], "type_changes": [], "is_first_load": True}

    current_set, reference_set = set(current.columns), set(reference.columns)
    added = sorted(current_set - reference_set)
    removed = sorted(reference_set - current_set)

    renamed = []
    if added and removed:
        removed_profiles = [FieldProfile(c, reference.samples.get(c, [])) for c in removed]
        added_profiles = [FieldProfile(c, current.samples.get(c, [])) for c in added]
        for candidate in suggest_mappings(removed_profiles, added_profiles, min_score=0.6):
            renamed.append(
                {
                    "old_field": candidate.source_field,
                    "new_field": candidate.target_field,
                    "confidence": round(candidate.combined_score, 3),
                }
            )

    truly_added = [c for c in added if c not in {r["new_field"] for r in renamed}]
    truly_removed = [c for c in removed if c not in {r["old_field"] for r in renamed}]

    type_changes = []
    for col in current_set & reference_set:
        if current.dtypes.get(col) != reference.dtypes.get(col):
            type_changes.append(
                {"field": col, "old_type": reference.dtypes.get(col), "new_type": current.dtypes.get(col)}
            )

    result = {
        "new_columns": truly_added,
        "removed_columns": truly_removed,
        "renamed_fields": renamed,
        "type_changes": type_changes,
        "is_first_load": False,
    }
    logger.info(
        "check_schema_drift: +%d -%d renamed=%d type_changes=%d",
        len(truly_added), len(truly_removed), len(renamed), len(type_changes),
    )
    return result


def to_snapshot(df: pd.DataFrame, sample_size: int = 20) -> SchemaSnapshot:
    return SchemaSnapshot(
        columns=list(df.columns),
        dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
        samples={col: df[col].dropna().head(sample_size).tolist() for col in df.columns},
    )


# ---------- combined ----------

def run_validation(
    df: pd.DataFrame,
    business_rules_path: str | Path | None = None,
    reference_schema: SchemaSnapshot | None = None,
    outlier_field: str = "Amount",
    outlier_group_by: str | None = "Currency",
    max_null_ratio: float = 0.0,
    key_fields: list[str] | None = None,
    min_uniqueness_ratio_for_auto_detect: float = 0.9,
    format_min_dominant_ratio: float = 0.8,
) -> ValidationReport:
    """Runs the active checks and returns one combined report."""
    report = ValidationReport()

    report.null_issues = check_nulls(df, max_null_ratio)
    report.dtype_issues = check_dtype_consistency(df)
    report.format_issues = check_format_patterns(df, format_min_dominant_ratio)

    if business_rules_path is not None:
        rules = load_rules(business_rules_path)
        report.business_rule_violations = apply_rules(df, rules)

    report.duplicate_issues = check_duplicates(df, key_fields, min_uniqueness_ratio_for_auto_detect)

    if outlier_field in df.columns:
        report.outliers = detect_statistical_anomalies(df, outlier_field, outlier_group_by)

    current_snapshot = to_snapshot(df)
    report.schema_drift = check_schema_drift(current_snapshot, reference_schema)

    logger.info("run_validation: has_issues=%s", report.has_issues)
    return report