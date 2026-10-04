"""
Tier-3 field mapping: the AI fallback that only runs when a field pair has
no exact name match and no join/crosswalk file entry (Tiers 1 and 2, owned
by the backend team). This module never sees or assumes a specific dataset
schema — it just takes two lists of (field_name, sample_values) and scores
every possible pairing.

Two signals, combined:
  1. Name similarity   — rapidfuzz token-based string similarity
  2. Value similarity  — do the sampled values look like the same kind of
                          data (same inferred type, overlapping value sets
                          for categorical-looking fields, similar numeric
                          range for numeric-looking fields)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

logger = logging.getLogger("Unizero.mapping")


@dataclass
class FieldProfile:
    name: str
    samples: list


@dataclass
class MappingCandidate:
    source_field: str
    target_field: str
    name_score: float
    value_score: float
    combined_score: float


def _infer_kind(samples: list) -> str:
    non_null = [s for s in samples if s is not None and str(s).strip() != ""]
    if not non_null:
        return "unknown"
    numeric = sum(1 for s in non_null if re.fullmatch(r"-?\d+(\.\d+)?", str(s)))
    if numeric / len(non_null) > 0.8:
        return "numeric"
    date_like = sum(1 for s in non_null if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s)))
    if date_like / len(non_null) > 0.8:
        return "date"
    return "text"


def _value_similarity(a: FieldProfile, b: FieldProfile) -> float:
    kind_a, kind_b = _infer_kind(a.samples), _infer_kind(b.samples)
    if kind_a != kind_b:
        return 0.0

    set_a = {str(s) for s in a.samples if s is not None}
    set_b = {str(s) for s in b.samples if s is not None}
    if not set_a or not set_b:
        return 0.3  # same inferred type but nothing to compare further

    overlap = len(set_a & set_b) / max(1, min(len(set_a), len(set_b)))

    if kind_a == "numeric":
        # numeric fields rarely share exact values (amounts) — reward
        # matching *shape* (similar magnitude) instead of exact overlap
        try:
            avg_a = sum(float(s) for s in set_a) / len(set_a)
            avg_b = sum(float(s) for s in set_b) / len(set_b)
            magnitude_match = 1 - min(1.0, abs(avg_a - avg_b) / max(abs(avg_a), abs(avg_b), 1))
            return max(overlap, magnitude_match * 0.6)
        except ValueError:
            return overlap

    return overlap


def suggest_mappings(
    source_fields: list[FieldProfile],
    target_fields: list[FieldProfile],
    min_score: float = 0.35,
) -> list[MappingCandidate]:
    """
    Score every source-target field pair. Caller (the backend) filters to
    unresolved pairs before calling this — this function doesn't know or
    care which pairs Tier 1 / Tier 2 already resolved.
    """
    if not source_fields or not target_fields:
        logger.warning("suggest_mappings called with empty source_fields or target_fields")
        return []

    candidates: list[MappingCandidate] = []
    for sf in source_fields:
        for tf in target_fields:
            name_score = fuzz.token_sort_ratio(sf.name, tf.name) / 100.0
            value_score = _value_similarity(sf, tf)
            combined = 0.5 * name_score + 0.5 * value_score
            if combined >= min_score:
                candidates.append(
                    MappingCandidate(sf.name, tf.name, name_score, value_score, combined)
                )
    candidates.sort(key=lambda c: c.combined_score, reverse=True)
    logger.info(
        "suggest_mappings: %d source x %d target fields -> %d candidates above min_score=%.2f",
        len(source_fields), len(target_fields), len(candidates), min_score,
    )
    return candidates


def classify_confidence(combined_score: float) -> str:
    """Maps a score onto the spec's color-coding tiers for the mapping UI."""
    if combined_score >= 0.95:
        return "green"        # common / exact
    if combined_score >= 0.75:
        return "light_green"  # potential match
    return "red"               # uncommon, needs manual review
