"""
Requirement 6: Break Management service/orchestration layer.

Ties together, without duplicating any of them:
  - reconciliation.matcher            -- the only source of new breaks
  - field_mapping.manual_mapping      -- which fields were confirmed comparable
  - ingestion.workflow                -- the actual ingested DataFrames
  - break_management.rca              -- AI root-cause analysis (advisory)
  - break_management.prioritization   -- deterministic scoring
  - break_management.lineage          -- transaction lineage graph

In-memory BREAKS store, same trade-off as ingestion.workflow.SESSIONS
and field_mapping.manual_mapping.MAPPING_SESSIONS: swappable for a real
repository later without changing any function signature here.

Nothing in this module ever writes to a reconciled value or an ingested
DataFrame. The only things a caller can change about a Break through
this module are its status (a human decision), its RCA history (append
only), and its priority/lineage cache (both recomputed from what the
break already contains).
"""

from __future__ import annotations

import logging

import uuid
from datetime import datetime, timezone

from break_management.approval_file import ApprovalFileError, parse_approval_file
from break_management.lineage import build_lineage
from break_management.models import (
    APPROVAL_TARGET_STATUSES,
    Authorization,
    Break,
    BreakManagementError,
    BreakStatus,
    InvestigatorFinding,
)
from break_management.permissions import (
    Action,
    PermissionDeniedError,
    require_different_actors,
    require_permission,
)
from break_management.prioritization import PriorityConfig, narrate_priority, score_break
from break_management.rca import run_rca as _run_rca
from field_mapping.crosswalk import CrosswalkError
from field_mapping.manual_mapping import ManualMappingError, get_mapping_session
from ingestion.workflow import WorkflowError, get_session as get_ingestion_session
from reconciliation.aggregate import AggregateReconciliationError, reconcile_aggregates
from reconciliation.matcher import MatchConfig, MatcherError, reconcile

logger = logging.getLogger("onerecon.break_management.service")

#: In-memory break store for this requirement's scope (see module docstring).
BREAKS: dict[str, Break] = {}

_OPEN_LIKE_STATUSES = (BreakStatus.OPEN, BreakStatus.INVESTIGATING, BreakStatus.ESCALATED)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_dataframes(session) -> dict:
    dataframes = {}
    for source_name, ingestion_session_id in session.sources.items():
        try:
            dataframes[source_name] = get_ingestion_session(ingestion_session_id).df
        except WorkflowError as exc:
            raise BreakManagementError(
                f"Ingestion session for source {source_name!r} is unavailable: {exc}"
            ) from exc
    return dataframes


def _occurrence_count(break_key: str, exclude_break_id: str | None = None) -> int:
    """How many breaks already in the store carry this exact transaction
    key -- the deterministic "historical frequency" input to
    prioritization.score_break. A repeatedly-breaking transaction scores
    higher on this component every time it recurs."""
    return sum(
        1 for b in BREAKS.values()
        if b.break_key == break_key and b.break_id != exclude_break_id
    )


def analyze_breaks(
    mapping_session_id: str,
    key_field: str = "TransactionID",
    amount_tolerance: float = 0.01,
    priority_config: PriorityConfig | None = None,
    narrate: bool = False,
    actor: str = "system",
) -> list[Break]:
    """
    Runs deterministic reconciliation for the sources behind
    `mapping_session_id`, then creates+prioritizes a Break for every
    resulting ReconciliationBreak. Skips keys that already have an
    open-like Break for this mapping session, so re-running analysis
    doesn't pile up duplicate breaks for the same still-unresolved
    transaction.
    """
    try:
        mapping_session = get_mapping_session(mapping_session_id)
    except ManualMappingError as exc:
        raise BreakManagementError(str(exc)) from exc

    dataframes = _resolve_dataframes(mapping_session)

    try:
        reconciliation_breaks = reconcile(
            mapping_session, dataframes, MatchConfig(key_field=key_field, amount_tolerance=amount_tolerance)
        )
    except MatcherError as exc:
        raise BreakManagementError(str(exc)) from exc

    already_open = {
        b.break_key for b in BREAKS.values()
        if b.mapping_session_id == mapping_session_id and b.status in _OPEN_LIKE_STATUSES
    }

    created: list[Break] = []
    for rb in reconciliation_breaks:
        if rb.break_key in already_open:
            continue

        br = Break.from_reconciliation_break(rb, actor=actor)
        score = score_break(br, occurrence_count=_occurrence_count(br.break_key), config=priority_config)
        if narrate:
            score.narrative = narrate_priority(br, score)
        br.set_priority(score, actor=actor)

        BREAKS[br.break_id] = br
        created.append(br)

    logger.info(
        "analyze_breaks: mapping_session=%s candidates=%d created=%d (skipped already-open=%d)",
        mapping_session_id, len(reconciliation_breaks), len(created), len(reconciliation_breaks) - len(created),
    )
    return created


def list_breaks(
    status: str | None = None,
    break_type: str | None = None,
    source: str | None = None,
    priority_band: str | None = None,
    mapping_session_id: str | None = None,
) -> list[Break]:
    results = list(BREAKS.values())
    if status:
        results = [b for b in results if b.status.value == status]
    if break_type:
        results = [b for b in results if break_type in b.break_types]
    if source:
        results = [b for b in results if source in b.present_in or source in b.missing_in]
    if priority_band:
        results = [b for b in results if b.priority and b.priority.band == priority_band]
    if mapping_session_id:
        results = [b for b in results if b.mapping_session_id == mapping_session_id]
    results.sort(key=lambda b: (b.priority.total if b.priority else -1), reverse=True)
    return results


def get_break(break_id: str) -> Break:
    br = BREAKS.get(break_id)
    if br is None:
        raise BreakManagementError(f"No such break: {break_id}")
    return br


def run_break_rca(break_id: str, actor: str = "user") -> Break:
    br = get_break(break_id)
    _run_rca(br, actor=actor)  # raises explain.ReconciliationRCAError on real service failure
    return br


def change_status(
    break_id: str, new_status: str, actor: str, note: str | None = None, investigator_disagrees: bool = False
) -> Break:
    """The pre-existing, generic human-in-the-loop status path (OPEN /
    INVESTIGATING / ESCALATED, plus reopening a resolved/false-positive
    break back to INVESTIGATING). Left otherwise unmodified.

    Bugfix #1: this must NOT be a way to resolve or false-positive a
    break directly -- that would bypass maker-checker entirely (no
    investigator finding required, no different-approver check, no
    Authorization record). RESOLVED and FALSE_POSITIVE are only
    reachable through authorize_break/bulk_authorize/upload_approvals
    below, which enforce those rules before calling the SAME
    Break.transition() this function uses.
    """
    br = get_break(break_id)
    try:
        status_enum = BreakStatus(new_status)
    except ValueError as exc:
        raise BreakManagementError(
            f"Unknown status {new_status!r}; must be one of {[s.value for s in BreakStatus]}"
        ) from exc

    if status_enum in APPROVAL_TARGET_STATUSES:
        raise BreakManagementError(
            f"{status_enum.value} cannot be set via change_status -- it requires approver "
            "authorization (see authorize_break / bulk_authorize / upload_approvals)"
        )

    if investigator_disagrees and note:
        br.record_investigator_override(note=note, actor=actor)

    br.transition(status_enum, actor=actor, note=note)
    return br


def get_lineage(break_id: str) -> dict:
    br = get_break(break_id)
    lineage = build_lineage(br)
    br.set_lineage_cache(lineage, actor="system")
    return lineage


def get_summary(mapping_session_id: str | None = None) -> dict:
    breaks = list_breaks(mapping_session_id=mapping_session_id)
    by_status: dict[str, int] = {}
    by_band: dict[str, int] = {}
    by_break_type: dict[str, int] = {}
    for b in breaks:
        by_status[b.status.value] = by_status.get(b.status.value, 0) + 1
        if b.priority:
            by_band[b.priority.band] = by_band.get(b.priority.band, 0) + 1
        for t in b.break_types:
            by_break_type[t] = by_break_type.get(t, 0) + 1

    return {
        "total": len(breaks),
        "by_status": by_status,
        "by_priority_band": by_band,
        "by_break_type": by_break_type,
    }


# ---------------------------------------------------------------------------
# Bugfix #10 (part 2): business_rules.txt R10, AGGREGATE/SUM reconciliation.
# Deliberately its own reporting function, not folded into the Break/RCA/
# maker-checker lifecycle above -- R10 is an account-level rollup check,
# not a per-transaction break, so it doesn't carry the same investigation/
# authorization shape. Kept minimal on purpose.
# ---------------------------------------------------------------------------

def analyze_aggregates(
    mapping_session_id: str, crosswalk_path: str, tolerance: float = 0.01
) -> list[dict]:
    try:
        mapping_session = get_mapping_session(mapping_session_id)
    except ManualMappingError as exc:
        raise BreakManagementError(str(exc)) from exc

    dataframes = _resolve_dataframes(mapping_session)

    try:
        aggregate_breaks = reconcile_aggregates(mapping_session, dataframes, crosswalk_path, tolerance)
    except (AggregateReconciliationError, CrosswalkError) as exc:
        raise BreakManagementError(str(exc)) from exc

    logger.info(
        "analyze_aggregates: mapping_session=%s accounts_out_of_balance=%d",
        mapping_session_id, len(aggregate_breaks),
    )
    return [b.to_dict() for b in aggregate_breaks]


# ---------------------------------------------------------------------------
# Requirement 8: Maker-Checker.
#
# Everything below is additive -- it reuses get_break, Break.transition
# (the existing, unmodified status machine), Break.record_investigator_
# override (existing, unmodified), and Break.log/audit_log for every
# action's audit trail. No existing function above this line is changed.
# ---------------------------------------------------------------------------

def submit_investigator_cause(
    break_id: str, cause: str, actor: str, role: str, override_rca: bool = False
) -> Break:
    """Requirement 8.2: an investigator submits their own determination
    of a break's cause (InvestigatorFinding), separate from the AI's
    RCA. If override_rca is set, this ALSO calls the existing
    Break.record_investigator_override against the break's current
    RCAEntry -- the original AI text is preserved exactly as it was
    (see RCAEntry/record_investigator_override in models.py); nothing
    here rewrites it.

    role: the actor's role as asserted by the caller (the dashboard/
    admin layer owns actually assigning roles -- see permissions.py);
    this function only checks that role permits the action.
    """
    require_permission(actor, role, Action.SUBMIT_CAUSE)

    if not cause or not cause.strip():
        raise BreakManagementError("Investigator cause must not be empty")
    cause = cause.strip()

    br = get_break(break_id)

    overrides_rca_id = None
    if override_rca:
        require_permission(actor, role, Action.OVERRIDE_RCA)
        if br.current_rca is None:
            raise BreakManagementError("No RCA exists yet to override")
        br.record_investigator_override(note=cause, actor=actor)
        overrides_rca_id = br.current_rca.rca_id

    finding = InvestigatorFinding(
        finding_id=str(uuid.uuid4()), cause=cause, actor=actor,
        submitted_at=_now(), overrides_rca_id=overrides_rca_id,
    )
    br.add_investigator_finding(finding, actor=actor)
    return br


def _do_authorize(break_id: str, actor: str, target_status: str, note: str | None) -> Break:
    """The actual work of authorizing one break -- no PERMISSION check
    here (callers already did theirs); shared by authorize_break,
    bulk_authorize, and upload_approvals so every business rule below
    (bugfixes #2, #3, #4) is applied IDENTICALLY across all three paths
    (bugfix #7) -- there is exactly one place these rules live.
    """
    br = get_break(break_id)

    # Bugfix #2: an approver cannot authorize a break nobody has
    # investigated yet -- maker-checker requires a maker step first.
    if not br.investigator_findings:
        raise BreakManagementError(
            f"Break {break_id} cannot be authorized: no investigator finding/cause has been "
            "submitted yet (see submit_investigator_cause)"
        )

    # Bugfix #4: authorization may only land a break on a genuine
    # approval outcome -- not INVESTIGATING/OPEN/ESCALATED, which are
    # the existing human-in-the-loop path's job (change_status), not an
    # approver "authorization" decision.
    try:
        status_enum = BreakStatus(target_status)
    except ValueError as exc:
        raise BreakManagementError(
            f"Unknown status {target_status!r}; must be one of {[s.value for s in BreakStatus]}"
        ) from exc
    if status_enum not in APPROVAL_TARGET_STATUSES:
        raise BreakManagementError(
            f"target_status must be one of {sorted(s.value for s in APPROVAL_TARGET_STATUSES)}, "
            f"got {status_enum.value!r}"
        )

    # Bugfix #3 (already-correct rule, re-verified here): maker != checker.
    maker_actor = br.investigator_findings[-1].actor
    require_different_actors(maker_actor, actor)

    br.transition(status_enum, actor=actor, note=note)  # reuses the existing, unmodified state machine

    authorization = Authorization(
        authorization_id=str(uuid.uuid4()), actor=actor, status=status_enum.value,
        note=note, authorized_at=_now(), maker_actor=maker_actor,
    )
    br.add_authorization(authorization, actor=actor)
    return br


def authorize_break(
    break_id: str, actor: str, role: str, target_status: str = "RESOLVED", note: str | None = None
) -> Break:
    """Requirement 8.3."""
    require_permission(actor, role, Action.AUTHORIZE_BREAK)
    return _do_authorize(break_id, actor, target_status, note)


def bulk_authorize(
    break_ids: list[str], actor: str, role: str, target_status: str = "RESOLVED", note: str | None = None
) -> dict:
    """Requirement 8.4. Partial success by design: one bad id (unknown
    break, disallowed transition, maker==checker) does not abort the
    whole batch -- it's reported per-item instead."""
    require_permission(actor, role, Action.BULK_AUTHORIZE)

    authorized: list[str] = []
    failed: list[dict] = []
    for break_id in break_ids:
        try:
            br = _do_authorize(break_id, actor, target_status, note)
            authorized.append(br.break_id)
        except (BreakManagementError, PermissionDeniedError) as exc:
            failed.append({"break_id": break_id, "error": str(exc)})

    logger.info(
        "bulk_authorize: actor=%s requested=%d authorized=%d failed=%d",
        actor, len(break_ids), len(authorized), len(failed),
    )
    return {"authorized": authorized, "failed": failed}


def upload_approvals(content: str, actor: str, role: str, default_status: str = "RESOLVED") -> dict:
    """Requirement 8.5: an approver uploads a file of individual
    approvals (see approval_file.parse_approval_file for the format).
    Each line is authoritative and explicit -- nothing here infers a
    status for a line that doesn't state one; a line that genuinely
    omits its status (bugfix #6 made this a real, parseable case) falls
    back to default_status, validated up front here so a bad default
    fails once with a clear message instead of as N confusing per-line
    errors."""
    require_permission(actor, role, Action.UPLOAD_APPROVALS)

    try:
        default_status_enum = BreakStatus(default_status)
    except ValueError as exc:
        raise BreakManagementError(
            f"Unknown default_status {default_status!r}; must be one of {[s.value for s in BreakStatus]}"
        ) from exc
    if default_status_enum not in APPROVAL_TARGET_STATUSES:
        raise BreakManagementError(
            f"default_status must be one of {sorted(s.value for s in APPROVAL_TARGET_STATUSES)}, "
            f"got {default_status_enum.value!r}"
        )

    try:
        records, parse_errors = parse_approval_file(content)
    except ApprovalFileError as exc:
        raise BreakManagementError(str(exc)) from exc

    authorized: list[str] = []
    errors: list[dict] = list(parse_errors)
    for record in records:
        try:
            br = _do_authorize(
                record["break_id"], actor, record["status"] or default_status_enum.value, record["note"]
            )
            authorized.append(br.break_id)
        except (BreakManagementError, PermissionDeniedError) as exc:
            errors.append({"line_number": record["line_number"], "break_id": record["break_id"], "error": str(exc)})

    logger.info(
        "upload_approvals: actor=%s lines=%d authorized=%d errors=%d",
        actor, len(records), len(authorized), len(errors),
    )
    return {"authorized": authorized, "authorized_count": len(authorized), "errors": errors}
