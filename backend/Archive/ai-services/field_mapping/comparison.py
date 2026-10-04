"""
Requirement 2, step 1: Field Comparison View.

Builds the side-by-side panel data the spec describes: every field from
an ingested source, its inferred datatype, and its top-5 sample values
ordered by how often they occur — exactly what a hover tooltip needs.
Nothing here is specific to any dataset; it works off whatever columns
the dataframe actually has.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger("onerecon.field_mapping.comparison")


def build_field_profiles(df: pd.DataFrame, top_n: int = 5) -> list[dict]:
    """One profile per column: name, dtype, null count, and the top_n
    most frequent non-null values with their occurrence counts.

    "Top n" means value_counts().head(n) — the n values that occur most
    often in the column — not the first n rows. Nulls are dropped before
    counting, so they never appear in top_values; null_count reports
    them separately instead.
    """
    profiles = []
    for col in df.columns:
        series = df[col]
        non_null = series.dropna()
        top_values = non_null.value_counts().head(top_n)
        profiles.append(
            {
                "field": col,
                "dtype": str(series.dtype),
                "null_count": int(series.isna().sum()),
                "top_values": [
                    {"value": value, "count": int(count)} for value, count in top_values.items()
                ],
            }
        )
    logger.info("build_field_profiles: %d field profile(s) built", len(profiles))
    return profiles


def search_fields(profiles: list[dict], query: str) -> list[dict]:
    """Case-insensitive substring search over field names — backs the
    per-panel search box (e.g. typing 'entity' finds every field
    containing that substring, per the spec's example)."""
    if not query:
        return profiles
    needle = query.lower()
    return [p for p in profiles if needle in p["field"].lower()]


def _json_safe_value(value):
    """
    Converts a single value to something the standard json module can
    serialize without surprises. This is deliberately kept separate from
    build_field_profiles: that function's job is pandas analysis (and
    stays reusable/testable with real pandas/numpy objects in its
    output), this function's job is the API boundary.

    - numpy int/float/bool -> native Python int/float/bool
    - NaN/Infinity floats -> None (not valid JSON; Python's json module
      would emit the non-standard literals NaN/Infinity otherwise)
    - pandas Timestamp/Timedelta -> ISO string
    - bytes -> decoded string (fallback: repr)
    - anything else -> returned as-is if it's already a plain
      str/int/float/bool/None, otherwise stringified as a last resort
    """
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, pd.Timedelta):
        return str(value)
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return repr(value)
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def serialize_field_profiles(profiles: list[dict]) -> list[dict]:
    """Applies _json_safe_value to every top_value's value, leaving the
    rest of each profile (field name, dtype string, counts — already
    plain Python types) untouched."""
    safe_profiles = []
    for profile in profiles:
        safe_profiles.append(
            {
                **profile,
                "top_values": [
                    {"value": _json_safe_value(tv["value"]), "count": tv["count"]}
                    for tv in profile["top_values"]
                ],
            }
        )
    return safe_profiles
