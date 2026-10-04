"""
Requirement 2, step 2: Automated Field Mapping.

Dynamically identifies fields representing the same business concept
across any number of ingested sources -- nothing here hardcodes FA, MA,
RR, GL, or any specific field name. It works off whatever field profiles
the existing Field Comparison View (field_comparison_view.py /
comparison.py) already built, and reuses mapping.py's value-similarity
and type-inference logic rather than reimplementing it.

Two mapping-evidence modes, applied per field (not as a single
all-or-nothing switch across the whole run -- see the note in
_score_pair for why: a crosswalk file typically only covers a handful
of key columns, e.g. gl_account_id/ma_customer_key/fa_key, never the
full schema, so falling back to embeddings for the *other* fields in
the same run is what makes the crosswalk-present case actually useful):

  1. Crosswalk evidence (crosswalk.py): if both field names appear as
     linked columns in a supplied join-map file, that's authoritative.
     mapping_method = "crosswalk", score = 1.0.
  2. Semantic embeddings (embeddings.py) + reused value-similarity
     (mapping._value_similarity): combined via configurable weights.
     mapping_method = "embedding". An exact (normalized) name match is
     a fast-path special case of this, mapping_method = "exact_name".

YELLOW is a separate, orthogonal signal from the four "is this a good
match" outcomes above: it marks *which* field is the reconciliation
amount, based on both sides being a numeric/decimal-typed field,
regardless of the underlying match confidence or naming. A pair with
identical names ("Amount"/"Amount") gets promoted from GREEN to YELLOW;
a pair with very different names ("Amount"/"Value") that would
otherwise be RED on naming grounds also gets promoted, as long as it
was still the best available match for at least one side. A
supplementary, purely value-driven pass additionally catches
numeric/numeric pairs that never became anyone's best match at all
(e.g. because some other field won on naming), gated by
`yellow_min_value_score` so two unrelated numeric columns aren't
flagged just because they're both numbers.

For 3+ sources, fields are chained into concept groups via a simple
union-find over accepted (non-RED) pairwise edges -- this generalizes
"FA:Treasury Date -> MA:TransactionDate -> RR:ValueDate" to any number
of sources in any order, rather than assuming a fixed pipeline sequence.

Ambiguous mappings (a close runner-up candidate) are flagged
`needs_review=True` with the runner-up attached, rather than silently
picked -- per the spec's human-in-the-loop requirement.
"""

from __future__ import annotations

import dataclasses
import itertools
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from field_mapping.crosswalk import load_crosswalk_fields
from field_mapping.embeddings import cosine_similarity, embed_texts
from field_mapping.field_comparison_view import get_field_comparison
from mapping import FieldProfile as _MappingFieldProfile
from mapping import _infer_kind, _value_similarity

logger = logging.getLogger("Unizero.field_mapping.auto_mapping")

GREEN, LIGHT_GREEN, RED, YELLOW = "GREEN", "LIGHT_GREEN", "RED", "YELLOW"

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]")


@dataclass
class MappingConfig:
    """Every threshold/weight the requirement asks to keep configurable."""

    green_threshold: float = 0.95
    light_green_threshold: float = 0.75
    semantic_weight: float = 0.6
    value_weight: float = 0.4
    ambiguous_gap: float = 0.05
    # Gate for the supplementary numeric-only pass (fields that never
    # became anyone's best match at all). The in-loop YELLOW override
    # for fields that DID become a best match needs no separate gate --
    # both sides being numeric is itself the signal.
    yellow_min_value_score: float = 0.5
    exact_name_short_circuit: bool = True


@dataclass
class FieldMapping:
    source: str
    field: str
    matched_source: str
    matched_field: str
    score: float
    color: str
    mapping_method: str  # "crosswalk" | "exact_name" | "embedding" | "value_signature"
    reason: str
    needs_review: bool = False
    runner_up: dict | None = None


@dataclass
class ConceptGroup:
    """A cluster of fields, from 2+ sources, judged to be the same
    business concept -- the generalized 'mapping chain'."""

    members: list[dict]
    colors: list[str]
    mapping_methods: list[str]
    avg_score: float


@dataclass
class AutoMappingResult:
    mappings: list[FieldMapping] = field(default_factory=list)
    concept_groups: list[ConceptGroup] = field(default_factory=list)
    config: MappingConfig = field(default_factory=MappingConfig)


# ---------- adapters onto existing field_mapping/comparison.py profiles ----------

def _normalize_name(name: str) -> str:
    return _NON_ALNUM_RE.sub("", name.lower())


def _profile_samples(profile: dict) -> list:
    return [tv["value"] for tv in profile.get("top_values", []) if tv.get("value") is not None]


def _profile_text(profile: dict) -> str:
    """The text handed to the embedder: name + a handful of sample values
    + dtype -- i.e. name/meaning, context, and datatype in one string, as
    the requirement asks for."""
    samples = _profile_samples(profile)
    sample_text = ", ".join(str(s) for s in samples[:5])
    return f"{profile['field']}. sample values: {sample_text}. dtype: {profile.get('dtype', 'unknown')}"


def _is_numeric_field(profile: dict) -> bool:
    return _infer_kind(_profile_samples(profile)) == "numeric"


# ---------- pairwise scoring ----------

def _score_pair(field_a: dict, field_b: dict, crosswalk_fields: set[str] | None, config: MappingConfig):
    """Returns (score, mapping_method, reason, value_score_or_None) for one
    field pair, before color classification or the YELLOW override."""
    name_a, name_b = field_a["field"], field_b["field"]

    if crosswalk_fields and name_a in crosswalk_fields and name_b in crosswalk_fields:
        return (
            1.0,
            "crosswalk",
            f"'{name_a}' and '{name_b}' both appear as linked key columns in the crosswalk file.",
            None,
        )

    if config.exact_name_short_circuit and _normalize_name(name_a) == _normalize_name(name_b):
        return 1.0, "exact_name", f"Field names '{name_a}' and '{name_b}' match exactly.", None

    profile_a = _MappingFieldProfile(name_a, _profile_samples(field_a))
    profile_b = _MappingFieldProfile(name_b, _profile_samples(field_b))
    value_score = _value_similarity(profile_a, profile_b)

    vectors = embed_texts([_profile_text(field_a), _profile_text(field_b)])
    semantic_score = cosine_similarity(vectors[0], vectors[1])

    combined = config.semantic_weight * semantic_score + config.value_weight * value_score
    reason = (
        f"Semantic name/meaning similarity {semantic_score:.2f}, sample-value similarity "
        f"{value_score:.2f} (weights {config.semantic_weight:.1f}/{config.value_weight:.1f})."
    )
    return combined, "embedding", reason, value_score


def _classify_color(score: float, config: MappingConfig) -> str:
    if score >= config.green_threshold:
        return GREEN
    if score >= config.light_green_threshold:
        return LIGHT_GREEN
    return RED


def _is_ambiguous(best_score: float, runner_up: tuple | None, config: MappingConfig) -> bool:
    if runner_up is None:
        return False
    runner_score = runner_up[0]
    if runner_score < config.light_green_threshold:
        return False  # runner-up isn't even a plausible match on its own
    return (best_score - runner_score) <= config.ambiguous_gap


# ---------- main entry points ----------

def compute_mapping_for_sources(
    sources: list[dict],
    crosswalk_path: str | Path | None = None,
    config: MappingConfig | None = None,
) -> AutoMappingResult:
    """
    sources: a list of {"name": str, "fields": [<comparison.py field
    profile dict>, ...]}. This is exactly the shape
    field_comparison_view.get_field_comparison()["sources"] returns, so
    it can be passed straight through -- see
    compute_field_mappings_for_sessions below.
    """
    config = config or MappingConfig()
    crosswalk_fields = load_crosswalk_fields(crosswalk_path) if crosswalk_path else None

    mappings: list[FieldMapping] = []
    seen_pairs: set[tuple] = set()

    for src_a, src_b in itertools.permutations(sources, 2):
        for field_a in src_a["fields"]:
            best = None
            runner_up = None
            for field_b in src_b["fields"]:
                score, method, reason, value_score = _score_pair(field_a, field_b, crosswalk_fields, config)
                candidate = (score, method, reason, value_score, field_b)
                if best is None or score > best[0]:
                    runner_up = best
                    best = candidate
                elif runner_up is None or score > runner_up[0]:
                    runner_up = candidate

            if best is None:
                continue

            score, method, reason, value_score, field_b = best
            color = _classify_color(score, config)
            needs_review = _is_ambiguous(score, runner_up, config)

            if _is_numeric_field(field_a) and _is_numeric_field(field_b):
                color = YELLOW
                reason += (
                    " Both fields are numeric/decimal-typed, so this pair is also flagged as "
                    "the reconciliation-amount candidate, independent of match confidence."
                )

            runner_up_dict = None
            if needs_review:
                r_score, _r_method, _r_reason, _r_value, r_field_b = runner_up
                runner_up_dict = {
                    "matched_source": src_b["name"],
                    "matched_field": r_field_b["field"],
                    "score": round(r_score, 4),
                }

            record = FieldMapping(
                source=src_a["name"],
                field=field_a["field"],
                matched_source=src_b["name"],
                matched_field=field_b["field"],
                score=round(score, 4),
                color=color,
                mapping_method=method,
                reason=reason,
                needs_review=needs_review,
                runner_up=runner_up_dict,
            )
            seen_pairs.add((record.source, record.field, record.matched_source, record.matched_field))
            mappings.append(record)

    # Supplementary pass: numeric fields that never became anyone's best
    # match at all (so the loop above never considered them a pair),
    # caught here purely on value-profile similarity -- this is the
    # "even if its name differs across sources" case taken to its
    # fullest extent, gated by yellow_min_value_score so two unrelated
    # numeric columns aren't flagged just because they're both numbers.
    for src_a, src_b in itertools.combinations(sources, 2):
        numeric_a = [f for f in src_a["fields"] if _is_numeric_field(f)]
        numeric_b = [f for f in src_b["fields"] if _is_numeric_field(f)]
        for field_a in numeric_a:
            for field_b in numeric_b:
                key_ab = (src_a["name"], field_a["field"], src_b["name"], field_b["field"])
                key_ba = (src_b["name"], field_b["field"], src_a["name"], field_a["field"])
                if key_ab in seen_pairs or key_ba in seen_pairs:
                    continue

                profile_a = _MappingFieldProfile(field_a["field"], _profile_samples(field_a))
                profile_b = _MappingFieldProfile(field_b["field"], _profile_samples(field_b))
                value_score = _value_similarity(profile_a, profile_b)
                if value_score < config.yellow_min_value_score:
                    continue

                reason = (
                    "No adequate name/semantic match was found, but both are the numeric/decimal "
                    f"field in their source with a similar value profile (value similarity "
                    f"{value_score:.2f}) -- flagged as a likely reconciliation-amount pair despite "
                    "differing names."
                )
                mappings.append(
                    FieldMapping(
                        source=src_a["name"],
                        field=field_a["field"],
                        matched_source=src_b["name"],
                        matched_field=field_b["field"],
                        score=round(value_score, 4),
                        color=YELLOW,
                        mapping_method="value_signature",
                        reason=reason,
                    )
                )
                seen_pairs.add(key_ab)

    mappings.sort(key=lambda m: m.score, reverse=True)
    concept_groups = _build_concept_groups(mappings)
    logger.info(
        "compute_mapping_for_sources: %d source(s), %d mapping(s), %d concept group(s)",
        len(sources), len(mappings), len(concept_groups),
    )
    return AutoMappingResult(mappings=mappings, concept_groups=concept_groups, config=config)


def compute_field_mappings_for_sessions(
    session_ids: list[str],
    crosswalk_path: str | Path | None = None,
    config: MappingConfig | None = None,
) -> AutoMappingResult:
    """
    Thin wrapper: reuses the existing Field Comparison View to get field
    metadata for already-ingested, already-approved sessions. Never
    re-reads a source file -- get_field_comparison pulls the DataFrame
    that ingestion.py already parsed straight out of the in-memory
    session store.
    """
    comparison = get_field_comparison(session_ids)
    sources = [{**s, "name": s.get("name") or s["session_id"]} for s in comparison["sources"]]
    return compute_mapping_for_sources(sources, crosswalk_path=crosswalk_path, config=config)


# ---------- concept groups (generalized mapping chains) ----------

def _build_concept_groups(mappings: list[FieldMapping]) -> list[ConceptGroup]:
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(x: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: tuple[str, str], y: tuple[str, str]) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    relevant = [m for m in mappings if m.color != RED]
    for m in relevant:
        union((m.source, m.field), (m.matched_source, m.matched_field))

    clusters: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for m in relevant:
        for node in ((m.source, m.field), (m.matched_source, m.matched_field)):
            clusters.setdefault(find(node), set()).add(node)

    groups: list[ConceptGroup] = []
    for root, nodes in clusters.items():
        if len(nodes) < 2:
            continue
        member_edges = [m for m in relevant if find((m.source, m.field)) == root]
        groups.append(
            ConceptGroup(
                members=[{"source": s, "field": f} for s, f in sorted(nodes)],
                colors=sorted({m.color for m in member_edges}),
                mapping_methods=sorted({m.mapping_method for m in member_edges}),
                avg_score=round(sum(m.score for m in member_edges) / len(member_edges), 4),
            )
        )
    groups.sort(key=lambda g: g.avg_score, reverse=True)
    return groups


def result_to_dict(result: AutoMappingResult) -> dict:
    """JSON-safe view for the API -- mirrors IngestionSession.to_summary()'s
    pattern of never handing back internal objects directly."""
    return {
        "mappings": [dataclasses.asdict(m) for m in result.mappings],
        "concept_groups": [dataclasses.asdict(g) for g in result.concept_groups],
        "config": dataclasses.asdict(result.config),
    }
