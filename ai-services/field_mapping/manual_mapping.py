"""
Requirement 2, step 3: Manual Field Mapping Override.

Sits on top of field_mapping/auto_mapping.py without changing it. The
AI result produced by compute_field_mappings_for_sessions() is loaded
once into an override session; from then on every change a human makes
is recorded as a *layer* over that frozen AI recommendation rather than
a mutation of it. That is the whole point of this module:

  * `ai_recommendation` on every entry keeps the original AI mapping
    verbatim (matched field, score, color, method, reason) forever, so
    "what did the model actually say" survives any number of human
    edits -- and Reset always has something authoritative to go back to.
  * `mapping_method="manual_override"` marks anything a human decided.
    Human decisions are authoritative: nothing in this module ever
    re-scores, re-ranks, or second-guesses an override, and no code path
    recomputes the AI mapping over the top of one.
  * `previous_mapping` + `override` + `audit_log` keep the before/after,
    the actor, the timestamp and the reason for each change, which is
    what an approver reviewing the run afterwards needs.

Three kinds of human input are supported, all through the same layer:

  1. A decision on an AI Potential match (LIGHT_GREEN): ACCEPT it into
     Common, REJECT it into Uncommon, or KEEP_POTENTIAL -- the last one
     lets a user hand-pick a different target field while deliberately
     leaving the pair flagged as still-unconfirmed.
  2. A free manual mapping between any two fields in any two ingested
     sources, regardless of what the AI said about either of them --
     including two fields the AI classified RED/Uncommon and never
     paired at all.
  3. A mapping file for uncommon fields, whose lines look like
     `Counterparty Code: 1 -> Client Type: Current Ac - Retail`. These
     are treated as explicit and authoritative: the file states, value
     by value, what maps to what. Nothing here infers, extrapolates,
     interpolates or casts a value that the file did not literally
     contain -- an unlisted source value simply has no mapping, and is
     reported as such.

Explicitly NOT in scope, and deliberately absent from this module: any
reconciliation, matching, break detection or root-cause analysis.
Overriding a mapping, previewing it and validating it are metadata
operations. No amount is compared, summed, netted or converted here.
"""

from __future__ import annotations

import copy
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from field_mapping.auto_mapping import (
    GREEN,
    LIGHT_GREEN,
    RED,
    YELLOW,
    AutoMappingResult,
    MappingConfig,
    compute_field_mappings_for_sessions,
)
from field_mapping.field_comparison_view import get_field_comparison

logger = logging.getLogger("onerecon.field_mapping.manual_mapping")

MANUAL_METHOD = "manual_override"
MAPPING_FILE_METHOD = "mapping_file"

COMMON, POTENTIAL, UNCOMMON = "COMMON", "POTENTIAL", "UNCOMMON"

CATEGORY_COLORS = {COMMON: GREEN, POTENTIAL: LIGHT_GREEN, UNCOMMON: RED}
COLOR_CATEGORIES = {GREEN: COMMON, LIGHT_GREEN: POTENTIAL, RED: UNCOMMON}

#: Decisions a human may take on an existing (usually AI Potential) match.
ACCEPT, REJECT, KEEP_POTENTIAL = "ACCEPT", "REJECT", "KEEP_POTENTIAL"
DECISIONS = (ACCEPT, REJECT, KEEP_POTENTIAL)

_DECISION_CATEGORY = {ACCEPT: COMMON, REJECT: UNCOMMON, KEEP_POTENTIAL: POTENTIAL}

# `Counterparty Code: 1 -> Client Type: Current Ac - Retail`, with either
# the unicode arrow or ASCII `->`/`=>` as the separator. Both sides are
# split on the FIRST colon only, so values may themselves contain colons.
_ARROW_RE = re.compile(r"\s*(?:->|=>|\u2192)\s*")

#: Hard caps, so an uploaded file or an API caller can't exhaust memory.
MAX_MAPPING_FILE_BYTES = 2 * 1024 * 1024
MAX_MAPPING_FILE_LINES = 20_000


class ManualMappingError(Exception):
    """Raised for an invalid override request -- unknown mapping session,
    unknown source or field, malformed mapping file, nothing to undo."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ValueMapping:
    """One literal line from a mapping file. `source_value` and
    `target_value` are kept exactly as written -- never parsed into
    numbers, never normalized, never rounded."""

    source_value: str
    target_value: str
    line_number: int


@dataclass
class MappingEntry:
    """One directed field mapping slot, keyed by (source, field,
    matched_source). A field may legitimately map into several *other*
    sources at once; mapping it twice within the SAME target source is
    what duplicate detection flags."""

    source: str
    field: str
    matched_source: str
    matched_field: str | None
    score: float
    category: str                      # COMMON | POTENTIAL | UNCOMMON
    mapping_method: str
    reason: str
    is_amount_candidate: bool = False  # the YELLOW reconciliation-field flag
    needs_review: bool = False
    runner_up: dict | None = None
    ai_recommendation: dict | None = None   # frozen: never written after creation
    is_manual_override: bool = False
    previous_mapping: dict | None = None
    override: dict | None = None
    value_mappings: list[ValueMapping] = field(default_factory=list)

    @property
    def key(self) -> str:
        return make_key(self.source, self.field, self.matched_source)

    @property
    def color(self) -> str:
        """YELLOW stays orthogonal to the category, exactly as in
        auto_mapping: it says 'this is the reconciliation amount', not
        'this is a good match'."""
        if self.is_amount_candidate:
            return YELLOW
        return CATEGORY_COLORS[self.category]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "source": self.source,
            "field": self.field,
            "matched_source": self.matched_source,
            "matched_field": self.matched_field,
            "score": self.score,
            "category": self.category,
            "color": self.color,
            "mapping_method": self.mapping_method,
            "reason": self.reason,
            "is_amount_candidate": self.is_amount_candidate,
            "needs_review": self.needs_review,
            "runner_up": self.runner_up,
            "ai_recommendation": self.ai_recommendation,
            "is_manual_override": self.is_manual_override,
            "previous_mapping": self.previous_mapping,
            "override": self.override,
            "value_mappings": [vars(v) for v in self.value_mappings],
        }


@dataclass
class ManualMappingSession:
    """In-memory holder for one field-mapping review, mirroring
    ingestion.workflow.SESSIONS' pattern -- swappable for a repository
    later without changing any signature in this module."""

    mapping_session_id: str
    ingestion_session_ids: list[str]
    entries: dict[str, MappingEntry]
    sources: dict[str, str]            # source name -> ingestion session id
    field_index: dict[str, dict[str, dict]]  # source name -> field name -> profile
    config: MappingConfig
    audit_log: list[dict] = field(default_factory=list)
    _undo_stack: list[tuple[str, MappingEntry | None]] = field(default_factory=list)

    def log(self, actor: str, action: str, **details) -> None:
        self.audit_log.append(
            {"timestamp": _now(), "actor": actor, "action": action, "details": details}
        )

    def require_field(self, source: str, field_name: str) -> dict:
        if source not in self.field_index:
            raise ManualMappingError(
                f"Unknown source {source!r}; known sources: {sorted(self.field_index)}"
            )
        profile = self.field_index[source].get(field_name)
        if profile is None:
            raise ManualMappingError(f"Unknown field {field_name!r} in source {source!r}")
        return profile

    def to_dict(self) -> dict:
        return {
            "mapping_session_id": self.mapping_session_id,
            "ingestion_session_ids": list(self.ingestion_session_ids),
            "sources": dict(self.sources),
            "entries": [e.to_dict() for e in self.entries.values()],
            "manual_override_count": sum(1 for e in self.entries.values() if e.is_manual_override),
            "can_undo": bool(self._undo_stack),
            "audit_log": list(self.audit_log),
        }


#: Mapping-session store for this requirement's scope (see the note on
#: ingestion.workflow.SESSIONS -- same trade-off, same upgrade path).
MAPPING_SESSIONS: dict[str, ManualMappingSession] = {}


def make_key(source: str, field_name: str, matched_source: str) -> str:
    return f"{source}::{field_name}::{matched_source}"


# ---------- session construction ----------

def _entry_from_ai(mapping, config: MappingConfig) -> MappingEntry:
    """Splits auto_mapping's single `color` back into its two independent
    signals: the amount flag (YELLOW) and the match category, the latter
    re-derived from the score with the same thresholds the AI used. That
    way promoting a numeric pair to YELLOW hasn't destroyed the
    information about how confident the naming/value match itself was."""
    is_amount = mapping.color == YELLOW
    if is_amount:
        base_color = (
            GREEN if mapping.score >= config.green_threshold
            else LIGHT_GREEN if mapping.score >= config.light_green_threshold
            else RED
        )
    else:
        base_color = mapping.color

    ai_recommendation = {
        "matched_source": mapping.matched_source,
        "matched_field": mapping.matched_field,
        "score": mapping.score,
        "color": mapping.color,
        "category": COLOR_CATEGORIES[base_color],
        "mapping_method": mapping.mapping_method,
        "reason": mapping.reason,
        "needs_review": mapping.needs_review,
        "runner_up": copy.deepcopy(mapping.runner_up),
    }
    return MappingEntry(
        source=mapping.source,
        field=mapping.field,
        matched_source=mapping.matched_source,
        matched_field=mapping.matched_field,
        score=mapping.score,
        category=COLOR_CATEGORIES[base_color],
        mapping_method=mapping.mapping_method,
        reason=mapping.reason,
        is_amount_candidate=is_amount,
        needs_review=mapping.needs_review,
        runner_up=copy.deepcopy(mapping.runner_up),
        ai_recommendation=ai_recommendation,
    )


def create_mapping_session(
    session_ids: list[str],
    crosswalk_path: str | Path | None = None,
    config: MappingConfig | None = None,
    auto_result: AutoMappingResult | None = None,
    sources: list[dict] | None = None,
    actor: str = "system",
) -> ManualMappingSession:
    """
    Loads an AI mapping run into a reviewable override session.

    Normal use passes `session_ids` only and lets this run the AI mapper.
    `auto_result` + `sources` are injection points for callers that have
    already computed both (and for tests) -- they are never recomputed
    once stored, so a later manual override can't be silently undone by
    a re-run.
    """
    config = config or MappingConfig()

    if sources is None:
        comparison = get_field_comparison(session_ids)
        sources = [{**s, "name": s.get("name") or s["session_id"]} for s in comparison["sources"]]

    if auto_result is None:
        auto_result = compute_field_mappings_for_sessions(
            session_ids, crosswalk_path=crosswalk_path, config=config
        )
        config = auto_result.config

    entries: dict[str, MappingEntry] = {}
    for mapping in auto_result.mappings:
        entry = _entry_from_ai(mapping, config)
        # auto_mapping emits at most one best match per (source, field,
        # target source), so a collision here would mean a duplicate in
        # the AI result; keep the higher-scoring one and move on.
        existing = entries.get(entry.key)
        if existing is None or entry.score > existing.score:
            entries[entry.key] = entry

    mapping_session = ManualMappingSession(
        mapping_session_id=str(uuid.uuid4()),
        ingestion_session_ids=list(session_ids),
        entries=entries,
        sources={s["name"]: s.get("session_id", "") for s in sources},
        field_index={s["name"]: {f["field"]: f for f in s["fields"]} for s in sources},
        config=config,
    )
    mapping_session.log(
        actor,
        "mapping_session.created",
        ingestion_session_ids=list(session_ids),
        ai_mapping_count=len(entries),
    )
    MAPPING_SESSIONS[mapping_session.mapping_session_id] = mapping_session
    logger.info(
        "create_mapping_session: %s built from %d source(s), %d AI mapping(s)",
        mapping_session.mapping_session_id, len(sources), len(entries),
    )
    return mapping_session


def get_mapping_session(mapping_session_id: str) -> ManualMappingSession:
    session = MAPPING_SESSIONS.get(mapping_session_id)
    if session is None:
        raise ManualMappingError(f"No such mapping session: {mapping_session_id}")
    return session


# ---------- undo bookkeeping ----------

def _snapshot(session: ManualMappingSession, key: str) -> None:
    """Pushes the pre-change state of one entry onto the undo stack.
    `None` records 'this entry did not exist yet', so undoing a manual
    mapping that created a brand-new pair removes it again rather than
    leaving an orphan."""
    existing = session.entries.get(key)
    session._undo_stack.append((key, copy.deepcopy(existing) if existing else None))


def _mapping_view(entry: MappingEntry) -> dict:
    """The compact before-image stored in `previous_mapping` -- enough
    for an auditor to see what the mapping was, without nesting whole
    entry histories inside each other."""
    return {
        "matched_source": entry.matched_source,
        "matched_field": entry.matched_field,
        "score": entry.score,
        "category": entry.category,
        "color": entry.color,
        "mapping_method": entry.mapping_method,
        "reason": entry.reason,
        "is_manual_override": entry.is_manual_override,
    }


def undo_last(session: ManualMappingSession, actor: str = "user") -> ManualMappingSession:
    """Reverts the most recent change of any kind (override, decision,
    mapping-file application, reset). Repeated calls walk back through
    the whole session."""
    if not session._undo_stack:
        raise ManualMappingError("Nothing to undo in this mapping session")

    key, snapshot = session._undo_stack.pop()
    if snapshot is None:
        session.entries.pop(key, None)
        session.log(actor, "mapping.undo", key=key, restored="removed (entry did not exist before)")
    else:
        session.entries[key] = snapshot
        session.log(
            actor, "mapping.undo", key=key, restored_to=_mapping_view(snapshot),
        )
    logger.info("undo_last: mapping_session=%s key=%s", session.mapping_session_id, key)
    return session


def reset_to_ai(session: ManualMappingSession, key: str, actor: str = "user") -> MappingEntry:
    """Drops every human layer on one mapping and restores the AI's
    original recommendation. An entry that only ever existed because a
    human created it has no AI recommendation to fall back to, so it is
    removed instead."""
    entry = session.entries.get(key)
    if entry is None:
        raise ManualMappingError(f"No such mapping: {key}")

    _snapshot(session, key)
    recommendation = entry.ai_recommendation

    if recommendation is None:
        del session.entries[key]
        session.log(actor, "mapping.reset", key=key, result="removed (no AI recommendation existed)")
        logger.info("reset_to_ai: %s removed (manual-only mapping)", key)
        return entry

    restored = MappingEntry(
        source=entry.source,
        field=entry.field,
        matched_source=entry.matched_source,
        matched_field=recommendation["matched_field"],
        score=recommendation["score"],
        category=recommendation["category"],
        mapping_method=recommendation["mapping_method"],
        reason=recommendation["reason"],
        is_amount_candidate=recommendation["color"] == YELLOW,
        needs_review=recommendation["needs_review"],
        runner_up=copy.deepcopy(recommendation["runner_up"]),
        ai_recommendation=copy.deepcopy(recommendation),
        is_manual_override=False,
        previous_mapping=_mapping_view(entry),
        override=None,
    )
    session.entries[key] = restored
    session.log(actor, "mapping.reset", key=key, reverted_from=_mapping_view(entry))
    logger.info("reset_to_ai: %s restored to AI recommendation", key)
    return restored


# ---------- the three human-input paths ----------

def set_manual_mapping(
    session: ManualMappingSession,
    source: str,
    field_name: str,
    matched_source: str,
    matched_field: str,
    category: str = COMMON,
    actor: str = "user",
    note: str | None = None,
) -> MappingEntry:
    """
    Maps any two fields across any two source panels, whatever the AI
    said about them -- GREEN/Common, LIGHT_GREEN/Potential and
    RED/Uncommon fields are all equally mappable, and the pair need not
    have been considered by the AI at all.

    `category` lets the caller choose where the result lands: COMMON,
    UNCOMMON, or POTENTIAL to hand-pick a target while deliberately
    leaving it flagged as unconfirmed.
    """
    if category not in CATEGORY_COLORS:
        raise ManualMappingError(f"category must be one of {sorted(CATEGORY_COLORS)}, got {category!r}")
    if source == matched_source and field_name == matched_field:
        raise ManualMappingError("A field cannot be mapped to itself")

    session.require_field(source, field_name)
    session.require_field(matched_source, matched_field)

    key = make_key(source, field_name, matched_source)
    _snapshot(session, key)
    existing = session.entries.get(key)

    entry = MappingEntry(
        source=source,
        field=field_name,
        matched_source=matched_source,
        matched_field=matched_field,
        # A human decision carries no model confidence. 1.0 would imply
        # the AI was certain; the honest value is "not scored", and the
        # authority comes from mapping_method instead.
        score=existing.score if existing and existing.matched_field == matched_field else 0.0,
        category=category,
        mapping_method=MANUAL_METHOD,
        reason=note or f"Manually mapped by {actor}; human decision overrides the AI recommendation.",
        is_amount_candidate=existing.is_amount_candidate if existing else False,
        needs_review=category == POTENTIAL,
        runner_up=copy.deepcopy(existing.runner_up) if existing else None,
        ai_recommendation=copy.deepcopy(existing.ai_recommendation) if existing else None,
        is_manual_override=True,
        previous_mapping=_mapping_view(existing) if existing else None,
        override={
            "actor": actor,
            "timestamp": _now(),
            "action": "manual_mapping",
            "category": category,
            "note": note,
        },
        value_mappings=list(existing.value_mappings) if existing else [],
    )
    session.entries[key] = entry
    session.log(
        actor,
        "mapping.manual_override",
        key=key,
        matched_field=matched_field,
        category=category,
        previous=entry.previous_mapping,
        note=note,
    )
    logger.info("set_manual_mapping: %s -> %s:%s (%s)", key, matched_source, matched_field, category)
    return entry


def decide_mapping(
    session: ManualMappingSession,
    key: str,
    decision: str,
    actor: str = "user",
    note: str | None = None,
    matched_field: str | None = None,
) -> MappingEntry:
    """
    Accept / reject / keep-as-potential an existing mapping -- the
    workflow for AI Potential (LIGHT_GREEN) matches.

      ACCEPT          -> moves it to Common.
      REJECT          -> moves it to Uncommon; the AI's suggested target
                         is retained on the entry (and in
                         ai_recommendation) so the rejection itself is
                         auditable rather than the pair just vanishing.
      KEEP_POTENTIAL  -> leaves it flagged Potential, optionally with a
                         different hand-picked `matched_field`.

    `matched_field` may also be supplied with ACCEPT, to accept the
    concept but correct the target field in one step.
    """
    if decision not in DECISIONS:
        raise ManualMappingError(f"decision must be one of {list(DECISIONS)}, got {decision!r}")

    entry = session.entries.get(key)
    if entry is None:
        raise ManualMappingError(f"No such mapping: {key}")

    if matched_field is not None:
        session.require_field(entry.matched_source, matched_field)

    _snapshot(session, key)
    previous = _mapping_view(entry)
    category = _DECISION_CATEGORY[decision]

    entry.previous_mapping = previous
    entry.category = category
    entry.matched_field = matched_field if matched_field is not None else entry.matched_field
    entry.needs_review = decision == KEEP_POTENTIAL
    entry.is_manual_override = True
    entry.mapping_method = MANUAL_METHOD
    entry.reason = note or (
        f"AI recommendation {decision.lower().replace('_', ' ')}ed by {actor}; "
        "human decision overrides the AI recommendation."
    )
    entry.override = {
        "actor": actor,
        "timestamp": _now(),
        "action": decision,
        "category": category,
        "note": note,
        "ai_matched_field": (entry.ai_recommendation or {}).get("matched_field"),
    }
    session.log(
        actor, "mapping.decision", key=key, decision=decision, category=category,
        previous=previous, note=note,
    )
    logger.info("decide_mapping: %s decision=%s -> %s", key, decision, category)
    return entry


# ---------- mapping file ----------

def parse_mapping_file(content: str) -> tuple[list[dict], list[dict]]:
    """
    Parses lines of the form

        Counterparty Code: 1 -> Client Type: Current Ac - Retail

    into explicit (source_field, source_value, target_field,
    target_value) records. Blank lines and `#` comments are skipped;
    every other unparseable line is returned as an error rather than
    guessed at.

    Values are kept as literal strings. This function deliberately does
    no type coercion, no numeric parsing and no normalization beyond
    stripping surrounding whitespace: a mapping file is an authoritative
    statement of what maps to what, and inventing a value it does not
    contain would be exactly the failure mode this design forbids.
    """
    if len(content.encode("utf-8", errors="ignore")) > MAX_MAPPING_FILE_BYTES:
        raise ManualMappingError(
            f"Mapping file exceeds the {MAX_MAPPING_FILE_BYTES} byte limit"
        )

    lines = content.splitlines()
    if len(lines) > MAX_MAPPING_FILE_LINES:
        raise ManualMappingError(f"Mapping file exceeds {MAX_MAPPING_FILE_LINES} lines")

    records: list[dict] = []
    errors: list[dict] = []

    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = _ARROW_RE.split(line)
        if len(parts) != 2:
            errors.append({"line_number": number, "line": line, "error": "expected exactly one '->' separator"})
            continue

        left, right = parts
        if ":" not in left or ":" not in right:
            errors.append({
                "line_number": number, "line": line,
                "error": "expected '<field>: <value>' on both sides of the arrow",
            })
            continue

        source_field, source_value = (p.strip() for p in left.split(":", 1))
        target_field, target_value = (p.strip() for p in right.split(":", 1))
        if not source_field or not target_field:
            errors.append({"line_number": number, "line": line, "error": "field name is empty"})
            continue

        records.append({
            "source_field": source_field,
            "source_value": source_value,
            "target_field": target_field,
            "target_value": target_value,
            "line_number": number,
        })

    return records, errors


def apply_mapping_file(
    session: ManualMappingSession,
    content: str,
    source: str,
    matched_source: str,
    actor: str = "user",
    category: str = COMMON,
) -> dict:
    """
    Applies an uploaded mapping file to a pair of source panels. Each
    distinct (source_field -> target_field) pair in the file becomes one
    mapping entry carrying the explicit value translations that back it.

    A line naming a field that does not exist in the given panels is
    reported as an error and skipped -- the file is authoritative about
    values, not about schema, and silently accepting an unknown field
    would let a typo create a mapping nobody can see.
    """
    if category not in CATEGORY_COLORS:
        raise ManualMappingError(f"category must be one of {sorted(CATEGORY_COLORS)}, got {category!r}")

    records, errors = parse_mapping_file(content)
    errors = list(errors)

    grouped: dict[tuple[str, str], list[ValueMapping]] = {}
    for record in records:
        try:
            session.require_field(source, record["source_field"])
            session.require_field(matched_source, record["target_field"])
        except ManualMappingError as exc:
            errors.append({"line_number": record["line_number"], "error": str(exc)})
            continue
        grouped.setdefault((record["source_field"], record["target_field"]), []).append(
            ValueMapping(
                source_value=record["source_value"],
                target_value=record["target_value"],
                line_number=record["line_number"],
            )
        )

    applied: list[MappingEntry] = []
    for (source_field, target_field), value_mappings in grouped.items():
        key = make_key(source, source_field, matched_source)
        _snapshot(session, key)
        existing = session.entries.get(key)

        entry = MappingEntry(
            source=source,
            field=source_field,
            matched_source=matched_source,
            matched_field=target_field,
            score=1.0,  # an explicit file entry is a statement of fact, not a model score
            category=category,
            mapping_method=MAPPING_FILE_METHOD,
            reason=(
                f"Mapped via uploaded mapping file: {len(value_mappings)} explicit value "
                f"translation(s) supplied by {actor}. Values are used exactly as written; "
                "no value is inferred."
            ),
            is_amount_candidate=existing.is_amount_candidate if existing else False,
            needs_review=category == POTENTIAL,
            ai_recommendation=copy.deepcopy(existing.ai_recommendation) if existing else None,
            is_manual_override=True,
            previous_mapping=_mapping_view(existing) if existing else None,
            override={
                "actor": actor,
                "timestamp": _now(),
                "action": "mapping_file_upload",
                "category": category,
                "value_mapping_count": len(value_mappings),
            },
            value_mappings=value_mappings,
        )
        session.entries[key] = entry
        applied.append(entry)
        session.log(
            actor, "mapping.mapping_file_applied", key=key, matched_field=target_field,
            value_mapping_count=len(value_mappings), previous=entry.previous_mapping,
        )

    logger.info(
        "apply_mapping_file: mapping_session=%s applied=%d error_lines=%d",
        session.mapping_session_id, len(applied), len(errors),
    )
    return {
        "applied": [e.to_dict() for e in applied],
        "applied_count": len(applied),
        "value_mapping_count": sum(len(e.value_mappings) for e in applied),
        "errors": errors,
    }


def translate_value(entry: MappingEntry, value) -> dict:
    """
    Looks a single source value up in the entry's explicit value
    mappings. Returns `{"mapped": False, ...}` when the file does not
    cover that value -- it never falls back to passing the value
    through, guessing a nearby match, or casting it. For financial data
    an unmapped value is a fact to report, not a gap to fill.
    """
    needle = "" if value is None else str(value).strip()
    for vm in entry.value_mappings:
        if vm.source_value == needle:
            return {"source_value": needle, "target_value": vm.target_value, "mapped": True}
    return {
        "source_value": needle,
        "target_value": None,
        "mapped": False,
        "note": "No explicit mapping-file entry for this value; nothing inferred.",
    }
