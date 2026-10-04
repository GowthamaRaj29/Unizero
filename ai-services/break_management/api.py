"""
Requirement 6: Break Management API surface.

A plain APIRouter so app.py mounts it (`app.include_router(router)`)
without any change to the existing routes defined there. Every endpoint
is a thin wrapper over break_management/service.py -- no business logic
lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import explain
from break_management import service
from break_management.models import BreakManagementError
from break_management.permissions import PermissionDeniedError

router = APIRouter(prefix="/breaks", tags=["break-management"])


# ---------- request/response models ----------

class AnalyzeBreaksRequest(BaseModel):
    mapping_session_id: str
    key_field: str = "TransactionID"
    amount_tolerance: float = 0.01
    narrate: bool = False
    actor: str = "system"


class AnalyzeAggregatesRequest(BaseModel):
    mapping_session_id: str
    crosswalk_path: str
    tolerance: float = 0.01


class RunRCARequest(BaseModel):
    actor: str = "user"


class ChangeStatusRequest(BaseModel):
    status: str  # OPEN | INVESTIGATING | RESOLVED | ESCALATED | FALSE_POSITIVE
    actor: str
    note: str | None = None
    investigator_disagrees: bool = False


# ---------- Requirement 8: Maker-Checker request models ----------
# `role` is asserted by the caller on every request below (INVESTIGATOR |
# APPROVER) -- the dashboard/admin layer owns actually assigning roles to
# actors; this API only checks that the asserted role permits the action.

class SubmitCauseRequest(BaseModel):
    actor: str
    role: str
    cause: str
    override_rca: bool = False


class AuthorizeRequest(BaseModel):
    actor: str
    role: str
    target_status: str = "RESOLVED"
    note: str | None = None


class BulkAuthorizeRequest(BaseModel):
    actor: str
    role: str
    break_ids: list[str]
    target_status: str = "RESOLVED"
    note: str | None = None


class UploadApprovalsRequest(BaseModel):
    actor: str
    role: str
    content: str  # raw file text -- see approval_file.parse_approval_file for the line format
    default_status: str = "RESOLVED"


# ---------- endpoints ----------

@router.post("/analyze")
def analyze_breaks(req: AnalyzeBreaksRequest) -> list[dict]:
    try:
        created = service.analyze_breaks(
            mapping_session_id=req.mapping_session_id,
            key_field=req.key_field,
            amount_tolerance=req.amount_tolerance,
            narrate=req.narrate,
            actor=req.actor,
        )
    except BreakManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [b.to_summary() for b in created]


@router.get("")
def list_breaks(
    status: str | None = None,
    break_type: str | None = None,
    source: str | None = None,
    priority_band: str | None = None,
    mapping_session_id: str | None = None,
) -> list[dict]:
    results = service.list_breaks(
        status=status, break_type=break_type, source=source,
        priority_band=priority_band, mapping_session_id=mapping_session_id,
    )
    return [b.to_summary() for b in results]


@router.get("/summary")
def breaks_summary(mapping_session_id: str | None = Query(default=None)) -> dict:
    return service.get_summary(mapping_session_id=mapping_session_id)


@router.post("/aggregate/analyze")
def analyze_aggregates(req: AnalyzeAggregatesRequest) -> list[dict]:
    """business_rules.txt R10 -- account-level AGGREGATE/SUM check
    (bugfix #10, part 2). Independent of the per-transaction /analyze
    endpoint above; see reconciliation/aggregate.py."""
    try:
        return service.analyze_aggregates(
            mapping_session_id=req.mapping_session_id,
            crosswalk_path=req.crosswalk_path,
            tolerance=req.tolerance,
        )
    except BreakManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{break_id}")
def get_break(break_id: str) -> dict:
    try:
        return service.get_break(break_id).to_detail()
    except BreakManagementError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{break_id}/rca")
def run_rca(break_id: str, req: RunRCARequest) -> dict:
    try:
        br = service.run_break_rca(break_id, actor=req.actor)
    except BreakManagementError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except explain.ReconciliationRCAError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return br.to_detail()


@router.post("/{break_id}/status")
def change_status(break_id: str, req: ChangeStatusRequest) -> dict:
    try:
        br = service.change_status(
            break_id, new_status=req.status, actor=req.actor,
            note=req.note, investigator_disagrees=req.investigator_disagrees,
        )
    except BreakManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return br.to_detail()


@router.get("/{break_id}/lineage")
def get_lineage(break_id: str) -> dict:
    try:
        return service.get_lineage(break_id)
    except BreakManagementError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------- Requirement 8: Maker-Checker endpoints ----------

@router.post("/{break_id}/investigator/cause")
def submit_investigator_cause(break_id: str, req: SubmitCauseRequest) -> dict:
    try:
        br = service.submit_investigator_cause(
            break_id, cause=req.cause, actor=req.actor, role=req.role, override_rca=req.override_rca,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BreakManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return br.to_detail()


@router.post("/{break_id}/authorize")
def authorize_break(break_id: str, req: AuthorizeRequest) -> dict:
    try:
        br = service.authorize_break(
            break_id, actor=req.actor, role=req.role, target_status=req.target_status, note=req.note,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BreakManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return br.to_detail()


@router.post("/authorize/bulk")
def bulk_authorize(req: BulkAuthorizeRequest) -> dict:
    try:
        return service.bulk_authorize(
            req.break_ids, actor=req.actor, role=req.role, target_status=req.target_status, note=req.note,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/authorize/upload")
def upload_approvals(req: UploadApprovalsRequest) -> dict:
    try:
        return service.upload_approvals(
            req.content, actor=req.actor, role=req.role, default_status=req.default_status,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BreakManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
