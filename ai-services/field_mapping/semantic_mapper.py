"""Semantic automated field mapping for OneRecon.

The module consumes the field profiles already produced by comparison.py.
It supports two modes:
1. crosswalk: a join_map/crosswalk is authoritative; its column headers and
   observed values establish relationships between source fields.
2. semantic: local sentence-transformer embeddings are compared with cosine
   similarity and combined with datatype/value compatibility.

No source names or field names are hardcoded.
"""
from __future__ import annotations

import csv
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("onerecon.field_mapping.semantic_mapper")


DEFAULT_SEMANTIC_THRESHOLD = 0.90
DEFAULT_EXACT_DATA_THRESHOLD = 0.95


@dataclass
class MappingResult:
    source: str
    field: str
    matched_source: str | None
    matched_field: str | None
    score: float
    color: str
    mapping_method: str
    reason: str
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "field": self.field,
            "matches": [] if self.matched_field is None else [{
                "source": self.matched_source,
                "field": self.matched_field,
                "score": round(float(self.score), 3),
                "color": self.color,
                "mapping_method": self.mapping_method,
                "reason": self.reason,
                "requires_confirmation": self.requires_confirmation,
            }],
        }


def _normalise(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _kind(dtype: str, values: list[Any]) -> str:
    d = str(dtype).lower()
    if any(x in d for x in ("int", "float", "decimal", "double", "number")):
        return "numeric"
    if "date" in d or "time" in d:
        return "date"
    non_null = [v for v in values if v is not None and str(v).strip()]
    if not non_null:
        return "unknown"
    numeric = 0
    dates = 0
    for v in non_null:
        s = str(v).strip()
        try:
            float(s)
            numeric += 1
        except ValueError:
            pass
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ].*)?", s):
            dates += 1
    if numeric / len(non_null) >= 0.8:
        return "numeric"
    if dates / len(non_null) >= 0.8:
        return "date"
    return "text"


def _values(profile: dict) -> list[Any]:
    return [x.get("value") for x in profile.get("top_values", []) if isinstance(x, dict)]


def _value_score(a: dict, b: dict) -> float:
    """Compatibility score, deliberately independent of field-name similarity."""
    ka, kb = _kind(a.get("dtype", ""), _values(a)), _kind(b.get("dtype", ""), _values(b))
    if ka == "unknown" or kb == "unknown":
        return 0.5
    if ka != kb:
        return 0.0

    sa = {_normalise(v) for v in _values(a) if v is not None and str(v).strip()}
    sb = {_normalise(v) for v in _values(b) if v is not None and str(v).strip()}
    if not sa or not sb:
        return 0.6
    overlap = len(sa & sb) / max(1, min(len(sa), len(sb)))
    return float(min(1.0, overlap))


def _is_numeric(profile: dict) -> bool:
    return _kind(profile.get("dtype", ""), _values(profile)) == "numeric"


def _exact_name(a: dict, b: dict) -> bool:
    return _normalise(a.get("field", "")) == _normalise(b.get("field", ""))


def _crosswalk_header_pairs(crosswalk_path: str | Path) -> dict[str, set[str]]:
    """Return relationships between crosswalk column headers.

    The crosswalk used by the supplied dataset contains columns such as
    gl_account_id, ma_customer_key and fa_key. Observed values are not needed
    to identify the field relationship: the headers themselves are the
    authoritative source-field names.
    """
    path = Path(crosswalk_path)
    if not path.exists():
        raise FileNotFoundError(f"Crosswalk not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows or not rows[0]:
        return {}
    headers = [h.strip() for h in rows[0] if h.strip()]
    relations: dict[str, set[str]] = {h: set() for h in headers}
    for i, left in enumerate(headers):
        for right in headers[i + 1:]:
            relations[left].add(right)
            relations[right].add(left)
    return relations


def _crosswalk_maps(sources: list[dict], crosswalk_path: str | Path) -> list[MappingResult]:
    relations = _crosswalk_header_pairs(crosswalk_path)
    results: list[MappingResult] = []
    for source in sources:
        source_name = source["source"]
        for profile in _source_fields(source):
            field = profile["field"]
            matches: list[tuple[str, dict, str]] = []

            # Exact field names remain common-field matches even when a
            # crosswalk exists. The crosswalk is authoritative for semantic
            # relationships where names differ; it never overrides an exact
            # same-name field.
            for other in sources:
                if other["source"] == source_name:
                    continue
                for target in _source_fields(other):
                    if _exact_name(profile, target):
                        matches.append((other["source"], target, "exact"))
                    elif target["field"] in relations.get(field, set()):
                        matches.append((other["source"], target, "crosswalk"))

            if not matches:
                results.append(MappingResult(
                    source_name, field, None, None, 0.0, "red", "crosswalk",
                    "No corresponding field was found in the authoritative crosswalk or by exact name.",
                    True,
                ))
                continue

            for target_source, target, evidence_type in matches:
                color = "yellow" if _is_numeric(profile) and _is_numeric(target) else "green"
                reason = (
                    "Exact field-name match."
                    if evidence_type == "exact"
                    else "Authoritative crosswalk relationship."
                )
                results.append(MappingResult(
                    source_name, field, target_source, target["field"], 1.0,
                    color, "crosswalk", reason, False,
                ))
    return results


def _semantic_text(profile: dict, source: str) -> str:
    values = ", ".join(str(v) for v in _values(profile)[:5])
    return (
        f"Source system: {source}. Field: {profile.get('field')}. "
        f"Datatype: {profile.get('dtype')}. "
        f"Common sample values: {values}."
    )


def _load_encoder(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Semantic mapping requires sentence-transformers. "
            "Install it with: pip install sentence-transformers"
        ) from exc
    return SentenceTransformer(model_name)


def _cosine_matrix(embeddings: list[list[float]]) -> list[list[float]]:
    # Kept dependency-light; numpy is already a transitive dependency of pandas.
    import numpy as np
    x = np.asarray(embeddings, dtype=float)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    x = x / np.clip(norms, 1e-12, None)
    return (x @ x.T).tolist()


def _semantic_maps(
    sources: list[dict],
    threshold: float,
    model_name: str,
    encoder: Any | None = None,
) -> list[MappingResult]:
    fields = []
    for source in sources:
        for profile in _source_fields(source):
            fields.append((source["source"], profile))
    if not fields:
        return []

    encoder = encoder or _load_encoder(model_name)
    texts = [_semantic_text(profile, source) for source, profile in fields]
    embeddings = encoder.encode(texts, normalize_embeddings=True)

    import numpy as np
    matrix = np.asarray(embeddings, dtype=float)
    scores = matrix @ matrix.T
    results: list[MappingResult] = []

    for i, (source_name, profile) in enumerate(fields):
        candidates = []
        for j, (target_source, target) in enumerate(fields):
            if source_name == target_source or i == j:
                continue
            semantic = float(max(0.0, min(1.0, scores[i, j])))
            value = _value_score(profile, target)
            exact = _exact_name(profile, target)
            # Semantic meaning is the primary signal. Data compatibility is
            # secondary evidence and cannot rescue an incompatible datatype.
            if value == 0.0:
                combined = semantic * 0.75
            else:
                combined = semantic * 0.80 + value * 0.20
            candidates.append((combined, semantic, value, target_source, target, exact))

        candidates.sort(key=lambda x: x[0], reverse=True)
        if not candidates:
            results.append(MappingResult(source_name, profile["field"], None, None, 0.0, "red", "semantic", "No candidate field in another source.", True))
            continue

        combined, semantic, value, target_source, target, exact = candidates[0]
        if exact:
            color = "yellow" if _is_numeric(profile) and _is_numeric(target) else "green"
            reason = "Exact field-name match; semantic and datatype evidence agree."
            confirmation = False
        elif combined >= threshold:
            color = "yellow" if _is_numeric(profile) and _is_numeric(target) else "light_green"
            reason = f"Semantic similarity {semantic:.2f} with datatype/value compatibility {value:.2f}."
            confirmation = True
        else:
            results.append(MappingResult(source_name, profile["field"], None, None, combined, "red", "semantic", f"Best semantic candidate scored {combined:.2f}, below threshold {threshold:.2f}.", True))
            continue
        results.append(MappingResult(source_name, profile["field"], target_source, target["field"], combined, color, "semantic", reason, confirmation))
    return results


def map_fields(
    sources: list[dict],
    *,
    crosswalk_path: str | Path | None = None,
    semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    encoder: Any | None = None,
) -> dict:
    """Map fields across all supplied sources and return frontend-ready data."""
    if not sources:
        raise ValueError("At least one source is required")
    if crosswalk_path:
        results = _crosswalk_maps(sources, crosswalk_path)
    else:
        results = _semantic_maps(sources, semantic_threshold, model_name, encoder)

    # De-duplicate symmetric pairs while retaining the first source's result.
    seen = set()
    mappings = []
    for result in results:
        key = (result.source, result.field, result.matched_source, result.matched_field)
        if key in seen:
            continue
        seen.add(key)
        mappings.append(result.to_dict())
    return {
        "mapping_method": "crosswalk" if crosswalk_path else "semantic",
        "semantic_threshold": semantic_threshold,
        "sources": sources,
        "mappings": mappings,
    }
def _source_fields(source: dict) -> list[dict]:
    """Return field profiles from either supported source shape."""
    return source.get("fields") or source.get("profiles") or []