"""
Requirement 6: Break Management domain models.

Mirrors the patterns already established in ingestion/workflow.py
(status Enum + dataclass + audit_log + to_summary()/to_dict()) and
field_mapping/manual_mapping.py (freeze the AI's original output,
layer human decisions on top without mutating it) rather than
inventing a new convention.

Key invariants encoded here, not left to callers:
  - A Break always starts OPEN and is created FROM a
    reconciliation.matcher.ReconciliationBreak -- there is no code path
    that lets break_management invent a break on its own.
  - RCA is advisory and append-only: `rca_history` keeps every AI RCA
    run (including the very first one) forever; `current_rca` points at
    the latest entry but a human overriding it (see
    Break.record_investigator_override) never deletes or rewrites a
    prior entry. Nothing here changes financial data or the reconciled
    values -- there is simply no method on this class that does that.
  - Priority scoring is a plain numeric formula (prioritization.py owns
    the formula); this module only stores the resulting components so
    the score stays reproducible and explainable from what's stored.
  - Status transitions are restricted to the requirement's own state
    machine and always logged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from reconciliation.matcher import ReconciliationBreak


class BreakStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


#: Allowed transitions, enforced by service.py. OPEN is the only entry
#: state (see BreakStatus docstring); a break can move on from any of
#: the three terminal-ish outcomes back to INVESTIGATING if reopened.
ALLOWED_TRANSITIONS: dict[BreakStatus, set[BreakStatus]] = {
    BreakStatus.OPEN: {BreakStatus.INVESTIGATING, BreakStatus.FALSE_POSITIVE, BreakStatus.ESCALATED},
    BreakStatus.INVESTIGATING: {
        BreakStatus.RESOLVED, BreakStatus.ESCALATED, BreakStatus.FALSE_POSITIVE, BreakStatus.OPEN,
    },
    BreakStatus.RESOLVED: {BreakStatus.INVESTIGATING},  # reopen
    BreakStatus.ESCALATED: {BreakStatus.INVESTIGATING, BreakStatus.RESOLVED, BreakStatus.FALSE_POSITIVE},
    BreakStatus.FALSE_POSITIVE: {BreakStatus.INVESTIGATING},  # reopen
}

#: Bugfix (Requirement 8 hardening): the only two statuses a break may
#: reach through the maker-checker approval path (service.authorize_break
#: / bulk_authorize / upload_approvals). This is the set service.py's
#: change_status() must now REFUSE to set directly -- see that function
#: for the other half of the fix. Kept here, next to ALLOWED_TRANSITIONS,
#: since it's the same kind of status-machine policy, not a service-layer
#: implementation detail.
APPROVAL_TARGET_STATUSES: set[BreakStatus] = {BreakStatus.RESOLVED, BreakStatus.FALSE_POSITIVE}


class BreakManagementError(Exception):
    """Raised for invalid break-management operations -- unknown break,
    disallowed status transition, malformed input."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditEvent:
    timestamp: str
    actor: str
    action: str
    details: dict = field(default_factory=dict)


@dataclass
class RCAEntry:
    """One AI RCA run, frozen once created. `current_rca` on Break
    points at the latest of these, but every prior entry stays in
    `rca_history` -- an investigator overriding the AI's read never
    deletes what the AI actually said (Requirement 6: "store the
    original AI RCA even if an investigator overrides it")."""

    rca_id: str
    root_cause: str
    confidence: str
    supporting_evidence: list
    suggested_action: str
    is_unknown: bool
    generated_at: str
    model: str
    # set only when an investigator has explicitly disagreed with THIS
    # entry -- the entry's own root_cause/confidence text is untouched.
    investigator_override: dict | None = None

    def to_dict(self) -> dict:
        return {
            "rca_id": self.rca_id,
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "supporting_evidence": list(self.supporting_evidence),
            "suggested_action": self.suggested_action,
            "is_unknown": self.is_unknown,
            "generated_at": self.generated_at,
            "model": self.model,
            "investigator_override": self.investigator_override,
        }


@dataclass
class InvestigatorFinding:
    """One investigator's submitted cause for a break -- distinct from
    the AI's RCA (RCAEntry above). An investigator may optionally tie a
    finding to overriding the current AI RCA (see
    Break.record_investigator_override, reused unchanged here); when
    they do, `overrides_rca_id` records which RCAEntry it was, but that
    entry's own text is never edited (see RCAEntry docstring)."""

    finding_id: str
    cause: str
    actor: str
    submitted_at: str
    overrides_rca_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "cause": self.cause,
            "actor": self.actor,
            "submitted_at": self.submitted_at,
            "overrides_rca_id": self.overrides_rca_id,
        }


@dataclass
class Authorization:
    """One approver decision (Requirement 8: maker-checker). `maker_actor`
    is whichever investigator's finding was on the break at the time of
    authorization, if any -- kept here as a durable record of who
    proposed vs. who confirmed, independent of the permissions registry
    (which may change over time)."""

    authorization_id: str
    actor: str
    status: str
    note: str | None
    authorized_at: str
    maker_actor: str | None

    def to_dict(self) -> dict:
        return {
            "authorization_id": self.authorization_id,
            "actor": self.actor,
            "status": self.status,
            "note": self.note,
            "authorized_at": self.authorized_at,
            "maker_actor": self.maker_actor,
        }


@dataclass
class PriorityScore:
    """Deterministic, explainable by construction: every component that
    fed the total is stored alongside it, so the number is never a black
    box. prioritization.py computes this; Claude (if used at all) may
    only add `narrative`, never change materiality/risk/frequency/total."""

    materiality: float
    risk: float
    frequency: float
    total: float
    band: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    formula: str
    computed_at: str
    narrative: str | None = None  # optional Claude interpretation of the number, not a re-score

    def to_dict(self) -> dict:
        return {
            "materiality": self.materiality,
            "risk": self.risk,
            "frequency": self.frequency,
            "total": self.total,
            "band": self.band,
            "formula": self.formula,
            "computed_at": self.computed_at,
            "narrative": self.narrative,
        }


@dataclass
class LineageNode:
    node_id: str
    source: str
    label: str
    attributes: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.node_id, "source": self.source, "label": self.label, "attributes": self.attributes}


@dataclass
class LineageEdge:
    from_id: str
    to_id: str
    relationship: str
    attributes: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "from": self.from_id, "to": self.to_id,
            "relationship": self.relationship, "attributes": self.attributes,
        }


@dataclass
class Break:
    """Unizerociliation break under human-in-the-loop management.
    Always constructed from a ReconciliationBreak -- see
    Break.from_reconciliation_break -- never invented directly."""

    break_id: str
    break_key: str
    key_field: str
    mapping_session_id: str
    present_in: list[str]
    missing_in: list[str]
    break_types: list[str]
    records: dict[str, dict]
    differences: list[dict]  # FieldDifference.to_dict() snapshots, frozen at detection time
    detected_at: str
    duplicate_in: dict[str, int] = field(default_factory=dict)  # bugfix #10: source -> row count for this key
    status: BreakStatus = BreakStatus.OPEN
    rca_history: list[RCAEntry] = field(default_factory=list)
    priority: PriorityScore | None = None
    lineage_cache: dict | None = None  # {"nodes": [...], "edges": [...]}, recomputed on demand
    audit_log: list[AuditEvent] = field(default_factory=list)
    investigator_findings: list[InvestigatorFinding] = field(default_factory=list)  # Requirement 8
    authorizations: list[Authorization] = field(default_factory=list)               # Requirement 8

    @classmethod
    def from_reconciliation_break(cls, rb: ReconciliationBreak, actor: str = "system") -> "Break":
        br = cls(
            break_id=str(uuid.uuid4()),
            break_key=rb.break_key,
            key_field=rb.key_field,
            mapping_session_id=rb.mapping_session_id,
            present_in=list(rb.present_in),
            missing_in=list(rb.missing_in),
            break_types=list(rb.break_types),
            records=rb.records,
            differences=[d.to_dict() for d in rb.differences],
            detected_at=rb.detected_at,
            duplicate_in=dict(rb.duplicate_in),
        )
        br.log(actor, "break.detected", break_types=br.break_types, key=br.break_key)
        return br

    def log(self, actor: str, action: str, **details) -> None:
        self.audit_log.append(AuditEvent(timestamp=_now(), actor=actor, action=action, details=details))

    @property
    def current_rca(self) -> RCAEntry | None:
        return self.rca_history[-1] if self.rca_history else None

    def add_rca(self, entry: RCAEntry, actor: str = "system") -> None:
        self.rca_history.append(entry)
        self.log(actor, "rca.generated", rca_id=entry.rca_id, root_cause=entry.root_cause,
                  confidence=entry.confidence, is_unknown=entry.is_unknown)

    def record_investigator_override(self, note: str, actor: str) -> None:
        """An investigator disagreeing with the latest RCA. This
        annotates that RCAEntry (in place, as metadata) -- it never
        edits root_cause/confidence/suggested_action, which stay exactly
        what the model said."""
        if self.current_rca is None:
            raise BreakManagementError("No RCA exists yet to override")
        self.current_rca.investigator_override = {"actor": actor, "note": note, "timestamp": _now()}
        self.log(actor, "rca.overridden", rca_id=self.current_rca.rca_id, note=note)

    def add_investigator_finding(self, finding: InvestigatorFinding, actor: str) -> None:
        """Requirement 8.2. Append-only, same convention as add_rca: a
        later finding never erases an earlier one."""
        self.investigator_findings.append(finding)
        self.log(actor, "investigator.finding_submitted", finding_id=finding.finding_id,
                  cause=finding.cause, overrides_rca_id=finding.overrides_rca_id)

    def add_authorization(self, authorization: Authorization, actor: str) -> None:
        """Requirement 8.3/8.4. Append-only record of every approver
        decision, independent of (but usually paired with, via
        service.authorize_break) the status transition it accompanies."""
        self.authorizations.append(authorization)
        self.log(actor, "approver.authorized", authorization_id=authorization.authorization_id,
                  status=authorization.status, maker_actor=authorization.maker_actor)

    def set_priority(self, score: PriorityScore, actor: str = "system") -> None:
        self.priority = score
        self.log(actor, "priority.scored", total=score.total, band=score.band)

    def set_lineage_cache(self, lineage: dict, actor: str = "system") -> None:
        self.lineage_cache = lineage
        self.log(actor, "lineage.built", node_count=len(lineage.get("nodes", [])))

    def transition(self, new_status: BreakStatus, actor: str, note: str | None = None) -> None:
        from break_management.models import ALLOWED_TRANSITIONS  # local, avoids a circular-import footgun
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise BreakManagementError(
                f"Cannot move break {self.break_id} from {self.status.value} to {new_status.value} "
                f"(allowed: {sorted(s.value for s in allowed)})"
            )
        previous = self.status
        self.status = new_status
        self.log(actor, "status.changed", previous=previous.value, new=new_status.value, note=note)

    def to_summary(self) -> dict:
        """List-view shape: no full evidence payload, matches
        ingestion.workflow.IngestionSession.to_summary()'s convention of
        never handing back more than a list view needs."""
        return {
            "break_id": self.break_id,
            "break_key": self.break_key,
            "status": self.status.value,
            "break_types": self.break_types,
            "present_in": self.present_in,
            "missing_in": self.missing_in,
            "detected_at": self.detected_at,
            "priority": self.priority.to_dict() if self.priority else None,
            "current_rca": self.current_rca.to_dict() if self.current_rca else None,
        }

    def to_detail(self) -> dict:
        return {
            **self.to_summary(),
            "key_field": self.key_field,
            "mapping_session_id": self.mapping_session_id,
            "records": self.records,
            "differences": self.differences,
            "duplicate_in": self.duplicate_in,
            "rca_history": [r.to_dict() for r in self.rca_history],
            "lineage_cache": self.lineage_cache,
            "audit_log": [vars(e) for e in self.audit_log],
            "investigator_findings": [f.to_dict() for f in self.investigator_findings],
            "authorizations": [a.to_dict() for a in self.authorizations],
        }
