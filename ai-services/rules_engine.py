"""
Generic business-rule validation engine.

Reads business_rules.txt at runtime and applies whatever rules it finds to
whatever dataframe it's given. Nothing about a specific field name, rule
type, or dataset is hardcoded here — add a new rule to the .txt file and
this engine picks it up automatically, no code change required.

business_rules.txt format (pipe-delimited):
    RULE_ID|FIELD|TYPE|PARAMS|DESCRIPTION

Supported TYPEs: REGEX, DATE, RANGE, LOOKUP
Meta rule types (FILE_PAIR, KEY_SPEC, AGGREGATE, DEFINE, INGEST) describe
workflow-level configuration, not per-row checks, so they're parsed but
skipped by the validator — they belong to the ingestion/mapping stage,
not here.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger("Unizero.rules_engine")

PER_ROW_TYPES = {"REGEX", "DATE", "RANGE", "LOOKUP"}


@dataclass
class Rule:
    rule_id: str
    field: str
    rule_type: str
    params: str
    description: str


class RulesFileError(Exception):
    """Raised when business_rules.txt is missing or unreadable — never let
    this surface as a raw stack trace to the caller."""


def load_rules(path: str | Path) -> list[Rule]:
    """Parse business_rules.txt into a list of Rule objects."""
    file_path = Path(path)
    if not file_path.exists():
        logger.error("Rules file not found: %s", file_path)
        raise RulesFileError(f"Rules file not found: {file_path}")

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Could not read rules file %s: %s", file_path, exc)
        raise RulesFileError(f"Could not read rules file: {exc}") from exc

    rules: list[Rule] = []
    skipped = 0
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 5:
            skipped += 1
            logger.warning("Skipping malformed rule on line %d: %r", line_no, raw_line)
            continue
        rule_id, field, rule_type, params, description = parts[:5]
        rules.append(Rule(rule_id, field, rule_type, params, description))

    logger.info("Loaded %d rules from %s (%d lines skipped)", len(rules), file_path, skipped)
    return rules


def _check_regex(value, params: str) -> bool:
    if pd.isna(value):
        return False
    pattern = params.replace("$$", "$")  # source file has doubled trailing $
    return re.fullmatch(pattern, str(value)) is not None


def _check_date(value, params: str) -> bool:
    if pd.isna(value):
        return False
    try:
        datetime.strptime(str(value), params)
        return True
    except ValueError:
        return False


def _check_range(value, params: str) -> bool:
    if pd.isna(value):
        return False
    try:
        lo, hi = (float(x) for x in params.split(","))
        return lo <= float(value) <= hi
    except (ValueError, TypeError):
        return False


def _check_lookup(value, params: str) -> bool:
    if pd.isna(value):
        return False
    allowed = {v.strip() for v in params.split(",")}
    return str(value) in allowed


_CHECKS = {
    "REGEX": _check_regex,
    "DATE": _check_date,
    "RANGE": _check_range,
    "LOOKUP": _check_lookup,
}


def apply_rules(df: pd.DataFrame, rules: list[Rule]) -> list[dict]:
    """
    Apply every per-row rule whose field exists in df.
    Returns a list of violation dicts — empty list means the batch is clean.
    Rules for fields not present in this dataframe are silently skipped:
    that's expected, since the same rule file covers multiple sources
    (e.g. R02 only applies to files that have a gl_account_id column).
    """
    violations: list[dict] = []
    for rule in rules:
        if rule.rule_type not in PER_ROW_TYPES:
            continue
        if rule.field not in df.columns:
            continue
        check = _CHECKS[rule.rule_type]
        bad_mask = ~df[rule.field].apply(lambda v: check(v, rule.params))
        for idx in df.index[bad_mask]:
            violations.append(
                {
                    "row": int(idx),
                    "rule_id": rule.rule_id,
                    "field": rule.field,
                    "value": df.at[idx, rule.field],
                    "message": rule.description,
                }
            )
    logger.info("apply_rules: %d rows, %d violations found", len(df), len(violations))
    return violations


def detect_statistical_anomalies(
    df: pd.DataFrame, field: str = "Amount", group_by: str | None = "Currency"
) -> list[dict]:
    """
    Flags statistical outliers using the IQR method, optionally per group
    (e.g. per currency, since 1000 JPY and 1000 USD aren't comparable).
    This is the "beyond simple field comparison" anomaly detection the
    spec asks for — deterministic and fast, no LLM call needed for this part.
    """
    if field not in df.columns:
        logger.warning("detect_statistical_anomalies: field %r not in dataframe columns", field)
        return []
    if df.empty:
        logger.info("detect_statistical_anomalies: empty dataframe, nothing to check")
        return []

    anomalies: list[dict] = []
    groups = df.groupby(group_by) if group_by and group_by in df.columns else [(None, df)]

    for group_value, group_df in groups:
        values = pd.to_numeric(group_df[field], errors="coerce")
        q1, q3 = values.quantile(0.25), values.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_mask = (values < lower) | (values > upper)
        for idx in group_df.index[outlier_mask.fillna(False)]:
            anomalies.append(
                {
                    "row": int(idx),
                    "field": field,
                    "group": group_value,
                    "value": float(values[idx]),
                    "expected_range": [round(float(lower), 2), round(float(upper), 2)],
                }
            )
    logger.info("detect_statistical_anomalies: %d anomalies found in field %r", len(anomalies), field)
    return anomalies
