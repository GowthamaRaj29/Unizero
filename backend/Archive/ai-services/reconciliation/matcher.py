"""
Requirement 6, prerequisite: deterministic reconciliation.

Nothing before this module actually joins two or more ingested sources
and diffs their values -- field_mapping/auto_mapping.py and
field_mapping/manual_mapping.py decide WHICH fields represent the same
concept, but explicitly stop short of comparing any values (see both
modules' docstrings). This module is the missing step: given a
confirmed field-mapping session and the underlying DataFrames, it joins
records by a key field and reports where they disagree.

This is deterministic and has no AI involvement whatsoever. It produces
the one true "here is a break, here is exactly what differs" record
that break_management/ builds on -- Claude never runs in this module,
and nothing downstream is allowed to treat this module's output as
anything but the source of truth for what happened.

Design choices, stated explicitly:
  - Only COMMON (human-confirmed-or-accepted) field mappings are used to
    decide what to compare. LIGHT_GREEN/POTENTIAL and RED/UNCOMMON pairs
    are not diffed -- comparing two fields nobody has confirmed represent
    the same concept would manufacture breaks out of a mapping guess,
    not a real discrepancy.
  - crosswalk-method mappings (e.g. gl_account_id <-> fa_key) link
    *different key spaces* to the same real-world entity; they are not
    two restatements of the same value and are never diffed for
    equality. Only exact_name / embedding / value_signature / manual
    pairs -- genuine "same value, same units" pairs -- are compared.
  - The join key itself defaults to "TransactionID" (present, identically
    named, in FA/MA/GL per the dataset spec) but is fully overridable;
    this module does not attempt to auto-detect a key field, to keep it
    simple and predictable.
  - UnizerociliationBreak per key, bundling every difference found for
    that transaction, not one break per differing field -- it's the same
    underlying transaction problem.
  - Bugfix #10: a key with more than one row in a single source (a
    duplicate TransactionID) is reported as its own DUPLICATE_RECORD
    break rather than silently deduplicated -- see _index_by_key and
    ReconciliationBreak.duplicate_in.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from field_mapping.comparison import _json_safe_value
from field_mapping.manual_mapping import COMMON, ManualMappingSession

logger = logging.getLogger("onerecon.reconciliation.matcher")

MISSING_RECORD = "MISSING_RECORD"
AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
DATE_MISMATCH = "DATE_MISMATCH"
CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
FIELD_MISMATCH = "FIELD_MISMATCH"
DUPLICATE_RECORD = "DUPLICATE_RECORD"

# mapping_methods that state "same value space, safe to diff for equality".
# "crosswalk" is deliberately excluded -- see module docstring.
_DIFFABLE_METHODS = {"exact_name", "embedding", "value_signature", "manual_override", "mapping_file"}


class MatcherError(Exception):
    """Raised for invalid reconciliation input -- missing key field,
    no overlapping sources, empty dataframes."""


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


@dataclass
class MatchConfig:
    key_field: str = "TransactionID"
    amount_tolerance: float = 0.01


@dataclass
class FieldDifference:
    source_a: str
    field_a: str
    value_a: object
    source_b: str
    field_b: str
    value_b: object
    difference_type: str  # AMOUNT_MISMATCH | DATE_MISMATCH | CURRENCY_MISMATCH | FIELD_MISMATCH
    mapping_reason: str  # why these two fields were judged comparable, from the mapping entry

    def to_dict(self) -> dict:
        return {
            "source_a": self.source_a,
            "field_a": self.field_a,
            "value_a": _json_safe_value(self.value_a),
            "source_b": self.source_b,
            "field_b": self.field_b,
            "value_b": _json_safe_value(self.value_b),
            "difference_type": self.difference_type,
            "mapping_reason": self.mapping_reason,
        }


@dataclass
class ReconciliationBreak:
    break_key: str
    key_field: str
    present_in: list[str]
    missing_in: list[str]
    records: dict[str, dict] = field(default_factory=dict)  # source -> full row, json-safe
    differences: list[FieldDifference] = field(default_factory=list)
    duplicate_in: dict[str, int] = field(default_factory=dict)  # bugfix #10: source -> row count for this key
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    mapping_session_id: str = ""

    @property
    def break_types(self) -> list[str]:
        types = {d.difference_type for d in self.differences}
        if self.missing_in:
            types.add(MISSING_RECORD)
        if self.duplicate_in:
            types.add(DUPLICATE_RECORD)
        return sorted(types)

    def to_dict(self) -> dict:
        return {
            "break_key": self.break_key,
            "key_field": self.key_field,
            "present_in": list(self.present_in),
            "missing_in": list(self.missing_in),
            "break_types": self.break_types,
            "records": self.records,
            "differences": [d.to_dict() for d in self.differences],
            "duplicate_in": dict(self.duplicate_in),
            "detected_at": self.detected_at,
            "mapping_session_id": self.mapping_session_id,
        }


def _accepted_field_pairs(session: ManualMappingSession, sources: list[str], key_field: str):
    """COMMON entries between two of the given sources, genuinely
    diffable (see _DIFFABLE_METHODS), excluding the join key itself.
    De-duplicated so an entry and its mirror-direction counterpart
    (A->B and B->A) don't produce the comparison twice."""
    key_norm = _normalize(key_field)
    seen: dict[frozenset, object] = {}
    for entry in session.entries.values():
        if entry.category != COMMON or entry.matched_field is None:
            continue
        if entry.source not in sources or entry.matched_source not in sources:
            continue
        if entry.mapping_method not in _DIFFABLE_METHODS:
            continue
        if _normalize(entry.field) == key_norm or _normalize(entry.matched_field) == key_norm:
            continue
        dedup_key = frozenset({(entry.source, entry.field), (entry.matched_source, entry.matched_field)})
        seen.setdefault(dedup_key, entry)
    return list(seen.values())


def _classify(entry, field_name: str) -> str:
    if entry.is_amount_candidate:
        return AMOUNT_MISMATCH
    normalized = _normalize(field_name)
    if "date" in normalized:
        return DATE_MISMATCH
    if "currency" in normalized:
        return CURRENCY_MISMATCH
    return FIELD_MISMATCH


def _values_differ(kind: str, value_a, value_b, tolerance: float) -> bool:
    a_missing = value_a is None or (isinstance(value_a, float) and pd.isna(value_a))
    b_missing = value_b is None or (isinstance(value_b, float) and pd.isna(value_b))
    if a_missing and b_missing:
        return False
    if a_missing or b_missing:
        return True

    if kind == AMOUNT_MISMATCH:
        try:
            return abs(float(value_a) - float(value_b)) > tolerance
        except (TypeError, ValueError):
            return str(value_a) != str(value_b)

    if kind == DATE_MISMATCH:
        parsed_a, parsed_b = pd.to_datetime(value_a, errors="coerce"), pd.to_datetime(value_b, errors="coerce")
        if pd.isna(parsed_a) or pd.isna(parsed_b):
            return str(value_a).strip() != str(value_b).strip()
        return parsed_a != parsed_b

    return str(value_a).strip() != str(value_b).strip()


def _index_by_key(df: pd.DataFrame, source: str, key_field: str) -> tuple[dict[str, dict], dict[str, int]]:
    """Bugfix #10: duplicate key values are no longer silently collapsed
    to "keep first and move on" -- every key with more than one row in
    this source is reported back (as {key_value: row_count}) so the
    caller can surface it as a genuine DUPLICATE_RECORD break. The first
    row is still used for field-comparison purposes (reconciliation
    needs *a* row to compare; picking one deterministically is
    reasonable), but the duplication itself is no longer invisible."""
    if key_field not in df.columns:
        raise MatcherError(f"Key field {key_field!r} not present in source {source!r}")

    records: dict[str, dict] = {}
    counts: dict[str, int] = {}
    for _, row in df.iterrows():
        key_value = row[key_field]
        if pd.isna(key_value):
            continue
        key_str = str(key_value)
        counts[key_str] = counts.get(key_str, 0) + 1
        if key_str not in records:
            records[key_str] = {col: _json_safe_value(val) for col, val in row.items()}

    duplicates = {k: n for k, n in counts.items() if n > 1}
    if duplicates:
        logger.warning(
            "reconcile: source=%s has %d duplicated %r value(s) (e.g. %s x%d); "
            "reported as DUPLICATE_RECORD breaks, not silently dropped",
            source, len(duplicates), key_field,
            next(iter(duplicates)), duplicates[next(iter(duplicates))],
        )
    return records, duplicates


def reconcile(
    session: ManualMappingSession,
    dataframes: dict[str, pd.DataFrame],
    config: MatchConfig | None = None,
) -> list[ReconciliationBreak]:
    """
    session: a confirmed field-mapping session (field_mapping.manual_mapping)
        for the sources being reconciled -- the source of truth for which
        fields represent the same concept.
    dataframes: source name -> DataFrame, for exactly the sources named in
        session.sources. Callers resolve these from ingestion.workflow's
        session store (see break_management/service.py); this module never
        reads a source file or the ingestion session store itself, so it
        stays independently testable.
    """
    config = config or MatchConfig()

    sources = [s for s in session.sources if s in dataframes]
    if len(sources) < 2:
        raise MatcherError("reconcile requires at least two sources with matching dataframes")

    indexed: dict[str, dict[str, dict]] = {}
    duplicate_counts: dict[str, dict[str, int]] = {}
    for source in sources:
        indexed[source], duplicate_counts[source] = _index_by_key(dataframes[source], source, config.key_field)

    all_keys = sorted(set().union(*(idx.keys() for idx in indexed.values())))
    field_pairs = _accepted_field_pairs(session, sources, config.key_field)

    breaks: list[ReconciliationBreak] = []
    for key_value in all_keys:
        present_in = [s for s in sources if key_value in indexed[s]]
        missing_in = [s for s in sources if s not in present_in]

        differences: list[FieldDifference] = []
        for entry in field_pairs:
            if entry.source not in present_in or entry.matched_source not in present_in:
                continue
            value_a = indexed[entry.source][key_value].get(entry.field)
            value_b = indexed[entry.matched_source][key_value].get(entry.matched_field)
            kind = _classify(entry, entry.field)
            if _values_differ(kind, value_a, value_b, config.amount_tolerance):
                differences.append(
                    FieldDifference(
                        source_a=entry.source,
                        field_a=entry.field,
                        value_a=value_a,
                        source_b=entry.matched_source,
                        field_b=entry.matched_field,
                        value_b=value_b,
                        difference_type=kind,
                        mapping_reason=entry.reason,
                    )
                )

        # Bugfix #10: a key with duplicate rows in any source is never a
        # "clean match" even if the (first-row) field comparison agrees --
        # which of the duplicate rows is authoritative is itself unresolved,
        # so it must surface as a break rather than be silently accepted.
        duplicate_in = {s: duplicate_counts[s][key_value] for s in sources if key_value in duplicate_counts[s]}

        if not missing_in and not differences and not duplicate_in:
            continue  # clean match across every source -- not a break

        breaks.append(
            ReconciliationBreak(
                break_key=key_value,
                key_field=config.key_field,
                present_in=present_in,
                missing_in=missing_in,
                records={s: indexed[s][key_value] for s in present_in},
                differences=differences,
                duplicate_in=duplicate_in,
                mapping_session_id=session.mapping_session_id,
            )
        )

    logger.info(
        "reconcile: mapping_session=%s sources=%s keys=%d breaks=%d",
        session.mapping_session_id, sources, len(all_keys), len(breaks),
    )
    return breaks
