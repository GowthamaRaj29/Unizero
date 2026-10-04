"""
Requirement 2, step 3 (part 2): Mapping Preview and Validation.

Everything here is read-only verification support for a human deciding
whether a mapping is right. Three capabilities:

  * `preview_mapping` -- the first N rows of both mapped fields, side by
    side, so a user can see for themselves that `fa_key` and
    `gl_account_id` really do hold the same kind of value.
  * `datatype_warnings` -- flags a pair whose two sides hold different
    kinds of data ("File 1: String vs File 2: Numeric"). It is a
    *warning*, never an action: nothing here casts, coerces, rounds or
    rewrites a value, least of all a financial one. A String/Numeric
    mismatch on an amount column is precisely the thing a human needs to
    look at, and auto-casting it would destroy the evidence.
  * `detect_duplicate_mappings` -- alerts when one field has been mapped
    to several targets in the same panel, or when several fields have
    been mapped onto the same target.

Out of scope here, as in manual_mapping.py: no reconciliation, no
matching, no break detection, no root-cause analysis. Values are read
and displayed; they are never compared for equality, netted or summed.
"""

from __future__ import annotations

import logging

import pandas as pd

from field_mapping.comparison import _json_safe_value
from field_mapping.manual_mapping import (
    ManualMappingError,
    ManualMappingSession,
    make_key,
    translate_value,
)
from ingestion.workflow import WorkflowError, get_session
from mapping import _infer_kind

logger = logging.getLogger("onerecon.field_mapping.mapping_validation")

DEFAULT_PREVIEW_ROWS = 5
MAX_PREVIEW_ROWS = 50

#: Inferred-kind -> the label shown to a user in a warning message.
_KIND_LABELS = {"numeric": "Numeric", "date": "Date", "text": "String", "unknown": "Unknown"}


def _display_type(series: "pd.Series | None", samples: list) -> str:
    """The human-facing type label. The pandas dtype alone is not enough:
    a CSV column of digits parsed as `object` is still Numeric to a
    reviewer's eye, which is exactly the mismatch worth surfacing. Falls
    back to the value-based inference the rest of the codebase already
    uses (mapping._infer_kind), and only trusts the dtype when it is
    unambiguous."""
    if series is not None:
        if pd.api.types.is_bool_dtype(series):
            return "Boolean"
        if pd.api.types.is_numeric_dtype(series):
            return "Numeric"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "Date"
    return _KIND_LABELS.get(_infer_kind(samples), "Unknown")


def _series_for(session: ManualMappingSession, source: str, field_name: str):
    """Pulls one column out of the DataFrame ingestion already parsed --
    never re-reads a source file, exactly like field_comparison_view.
    Returns (series_or_None, sample_values). The field is validated
    against the session's field index first, so a caller cannot use this
    to read an arbitrary column name it was never shown."""
    profile = session.require_field(source, field_name)
    samples = [tv["value"] for tv in profile.get("top_values", []) if tv.get("value") is not None]

    ingestion_session_id = session.sources.get(source)
    if not ingestion_session_id:
        return None, samples
    try:
        ingestion_session = get_session(ingestion_session_id)
    except WorkflowError:
        return None, samples
    if field_name not in ingestion_session.df.columns:
        return None, samples
    return ingestion_session.df[field_name], samples


def _rows_from(series, samples: list, rows: int) -> list:
    """First `rows` rows of the column, JSON-safe. Falls back to the
    profile's sample values when the DataFrame is unavailable (e.g. a
    synthetic source built from profiles alone)."""
    if series is None:
        return [_json_safe_value(v) for v in samples[:rows]]
    return [_json_safe_value(v) for v in series.head(rows).tolist()]


def datatype_warnings(
    session: ManualMappingSession, key: str
) -> tuple[list[dict], str, str]:
    """Returns (warnings, left_type, right_type) for one mapping."""
    entry = session.entries.get(key)
    if entry is None:
        raise ManualMappingError(f"No such mapping: {key}")
    if entry.matched_field is None:
        return [], "Unknown", "Unknown"

    left_series, left_samples = _series_for(session, entry.source, entry.field)
    right_series, right_samples = _series_for(session, entry.matched_source, entry.matched_field)
    left_type = _display_type(left_series, left_samples)
    right_type = _display_type(right_series, right_samples)

    warnings: list[dict] = []
    if left_type != right_type and "Unknown" not in (left_type, right_type):
        warnings.append({
            "type": "DATATYPE_MISMATCH",
            "severity": "WARNING",
            "key": key,
            "message": (
                f"Data type mismatch for {entry.source}.{entry.field} -> "
                f"{entry.matched_source}.{entry.matched_field}: "
                f"{entry.source}: {left_type} vs {entry.matched_source}: {right_type}"
            ),
            "file_1": entry.source,
            "file_1_type": left_type,
            "file_2": entry.matched_source,
            "file_2_type": right_type,
            "note": (
                "Reported only. No value is cast, converted or normalized automatically; "
                "financial data is left exactly as ingested."
            ),
        })
    return warnings, left_type, right_type


def preview_mapping(
    session: ManualMappingSession,
    key: str | None = None,
    source: str | None = None,
    field_name: str | None = None,
    matched_source: str | None = None,
    matched_field: str | None = None,
    rows: int = DEFAULT_PREVIEW_ROWS,
) -> dict:
    """
    Side-by-side sample data for both mapped fields so a user can verify
    the mapping before accepting it.

    Either pass an existing mapping `key`, or pass the four field
    coordinates directly to preview a pair the user is *considering*
    mapping but has not committed yet -- the frontend needs the second
    form to show a preview while a target is still being picked.
    """
    rows = max(1, min(int(rows), MAX_PREVIEW_ROWS))
    entry = None

    if key is not None:
        entry = session.entries.get(key)
        if entry is None:
            raise ManualMappingError(f"No such mapping: {key}")
        source, field_name = entry.source, entry.field
        matched_source, matched_field = entry.matched_source, entry.matched_field

    if not all([source, field_name, matched_source, matched_field]):
        raise ManualMappingError(
            "preview requires either a mapping key or all of "
            "source/field/matched_source/matched_field"
        )

    left_series, left_samples = _series_for(session, source, field_name)
    right_series, right_samples = _series_for(session, matched_source, matched_field)
    left_rows = _rows_from(left_series, left_samples, rows)
    right_rows = _rows_from(right_series, right_samples, rows)
    left_type = _display_type(left_series, left_samples)
    right_type = _display_type(right_series, right_samples)

    if entry is not None:
        warnings, _, _ = datatype_warnings(session, entry.key)
    else:
        warnings = []
        if left_type != right_type and "Unknown" not in (left_type, right_type):
            warnings.append({
                "type": "DATATYPE_MISMATCH",
                "severity": "WARNING",
                "key": make_key(source, field_name, matched_source),
                "message": (
                    f"Data type mismatch for {source}.{field_name} -> "
                    f"{matched_source}.{matched_field}: "
                    f"{source}: {left_type} vs {matched_source}: {right_type}"
                ),
                "file_1": source,
                "file_1_type": left_type,
                "file_2": matched_source,
                "file_2_type": right_type,
                "note": (
                    "Reported only. No value is cast, converted or normalized automatically; "
                    "financial data is left exactly as ingested."
                ),
            })

    # Explicit mapping-file translations, applied to the previewed rows
    # only for display. Unmapped values stay unmapped -- never guessed.
    value_translations = None
    if entry is not None and entry.value_mappings:
        value_translations = [translate_value(entry, v) for v in left_rows]

    preview = {
        "key": entry.key if entry is not None else make_key(source, field_name, matched_source),
        "rows": rows,
        "left": {
            "source": source,
            "field": field_name,
            "data_type": left_type,
            "values": left_rows,
        },
        "right": {
            "source": matched_source,
            "field": matched_field,
            "data_type": right_type,
            "values": right_rows,
        },
        "warnings": warnings,
        "value_translations": value_translations,
        "note": (
            "Preview only: sample rows are displayed for human verification. "
            "No reconciliation, matching or root-cause analysis is performed here."
        ),
    }
    logger.info(
        "preview_mapping: %s.%s vs %s.%s (%d row(s), %d warning(s))",
        source, field_name, matched_source, matched_field, rows, len(warnings),
    )
    return preview


def detect_duplicate_mappings(session: ManualMappingSession) -> list[dict]:
    """
    Two independent alerts:

      * one source field mapped to several target fields inside the same
        target panel ("Field X is mapped to multiple targets");
      * several source fields from one panel mapped onto the same target
        field ("Field Y is targeted by multiple source fields").

    A field mapped into *different* sources (FA:Amount -> GL:Amount and
    FA:Amount -> MA:Amount) is normal multi-source mapping and is not
    flagged.
    """
    by_field: dict[tuple[str, str, str], list] = {}
    by_target: dict[tuple[str, str, str], list] = {}

    for entry in session.entries.values():
        if entry.category == "UNCOMMON" or entry.matched_field is None:
            continue  # an uncommon/rejected field isn't claiming a target
        by_field.setdefault((entry.source, entry.field, entry.matched_source), []).append(entry)
        by_target.setdefault(
            (entry.matched_source, entry.matched_field, entry.source), []
        ).append(entry)

    alerts: list[dict] = []

    for (source, field_name, matched_source), entries in sorted(by_field.items()):
        targets = sorted({e.matched_field for e in entries})
        if len(targets) > 1:
            alerts.append({
                "type": "DUPLICATE_MAPPING",
                "severity": "ALERT",
                "message": (
                    f"Field {source}.{field_name} is mapped to multiple targets in "
                    f"{matched_source}: {', '.join(targets)}"
                ),
                "source": source,
                "field": field_name,
                "matched_source": matched_source,
                "targets": targets,
                "keys": sorted({e.key for e in entries}),
            })

    for (matched_source, matched_field, source), entries in sorted(by_target.items()):
        fields = sorted({e.field for e in entries})
        if len(fields) > 1:
            alerts.append({
                "type": "DUPLICATE_TARGET",
                "severity": "ALERT",
                "message": (
                    f"Field {matched_source}.{matched_field} is targeted by multiple "
                    f"fields in {source}: {', '.join(fields)}"
                ),
                "source": source,
                "fields": fields,
                "matched_source": matched_source,
                "matched_field": matched_field,
                "keys": sorted({e.key for e in entries}),
            })

    logger.info(
        "detect_duplicate_mappings: mapping_session=%s %d alert(s)",
        session.mapping_session_id, len(alerts),
    )
    return alerts


def validate_mapping_session(session: ManualMappingSession) -> dict:
    """One call the frontend can poll for the whole validation panel:
    every datatype warning plus every duplicate alert. Purely advisory --
    it blocks nothing and changes nothing."""
    warnings: list[dict] = []
    for key in list(session.entries):
        entry_warnings, _, _ = datatype_warnings(session, key)
        warnings.extend(entry_warnings)

    duplicates = detect_duplicate_mappings(session)
    return {
        "mapping_session_id": session.mapping_session_id,
        "datatype_warnings": warnings,
        "duplicate_alerts": duplicates,
        "warning_count": len(warnings),
        "alert_count": len(duplicates),
        "note": (
            "Advisory validation only. Nothing is auto-corrected, no data type is cast, "
            "and no reconciliation or root-cause analysis is performed."
        ),
    }
