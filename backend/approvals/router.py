from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from config.database import get_db

from auth.dependencies import (
    get_current_user,
    require_role
)

from common.enums import Role

from approvals.models import Approval

from investigations.models import Investigation

from breaks.models import Break

from users.models import User
from audit.service import write_audit


router = APIRouter(
    prefix="/approvals",
    tags=["Approvals"]
)


def serialize_investigation(
    db,
    item
):

    investigator = db.get(
        User,
        item.investigator_id
    )

    break_item = db.get(
        Break,
        item.break_id
    )

    return {
        "id": item.id,
        "break_id": item.break_id,
        "investigation_id": item.id,
        "status": item.status,
        "justification": item.justification,
        "investigator_email": (
            investigator.email
            or investigator.username
            if investigator else None
        ),
        "break": {
            "id": break_item.id,
            "key": break_item.reconciliation_key,
            "field": break_item.field,
            "run_id": break_item.run_id,
            "difference": break_item.difference,
            "source_a_value":
                break_item.source_a_value,
            "source_b_value":
                break_item.source_b_value,
            "ai_explanation":
                break_item.ai_explanation,
        }
        if break_item else None,
        "created_at": str(item.created_at)
        if item.created_at else None,
    }


@router.get("")
def list_approvals(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    items = (
        db.query(Investigation)
        .order_by(
            Investigation.created_at.desc()
        )
        .all()
    )

    return [
        serialize_investigation(db, item)
        for item in items
    ]


@router.get("/history")
def approval_history(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    approvals = (
        db.query(Approval)
        .order_by(
            Approval.created_at.desc()
        )
        .all()
    )

    results = []

    for approval in approvals:

        investigation = db.get(
            Investigation,
            approval.investigation_id
        )

        break_item = (
            db.get(
                Break,
                investigation.break_id
            )
            if investigation else None
        )

        approver = db.get(
            User,
            approval.approver_id
        )

        results.append(
            {
                "id": approval.id,
                "break_id":
                    investigation.break_id
                    if investigation else None,
                "investigation_id":
                    approval.investigation_id,
                "action":
                    approval.status.lower(),
                "status": approval.status,
                "comment": approval.comment,
                "actor": (
                    approver.email
                    or approver.username
                    if approver else None
                ),
                "key":
                    break_item.reconciliation_key
                    if break_item else None,
                "timestamp": str(
                    approval.created_at
                )
                if approval.created_at else None,
            }
        )

    return results


@router.get("/pending")
def pending_approvals(
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.APPROVER.value)
    )
):

    items = (
        db.query(Investigation)
        .filter(
            Investigation.status == "SUBMITTED"
        )
        .all()
    )

    return [
        serialize_investigation(db, item)
        for item in items
    ]


@router.get("/{investigation_id}")
def get_approval(
    investigation_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    investigation = db.get(
        Investigation,
        investigation_id
    )

    if not investigation:

        raise HTTPException(
            404,
            "Approval not found"
        )

    result = serialize_investigation(
        db,
        investigation
    )

    result["ai_root_cause"] = (
        result.get("break") or {}
    ).get("ai_explanation")

    return result


@router.post(
    "/{investigation_id}/approve"
)
def approve(
    investigation_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.APPROVER.value)
    )
):

    investigation = db.get(
        Investigation,
        investigation_id
    )

    if not investigation:

        raise HTTPException(
            404,
            "Investigation not found"
        )

    approval = Approval(
        id=str(uuid4()),
        investigation_id=investigation_id,
        approver_id=user.id,
        status="APPROVED",
        comment=payload.get("comment")
    )

    investigation.status = "APPROVED"

    break_item = db.get(
        Break,
        investigation.break_id
    )

    if break_item:

        break_item.status = "APPROVED"

    db.add(approval)
    db.commit()

    write_audit(
        db,
        user.id,
        "APPROVAL_RECORDED",
        old_value=investigation_id,
        new_value="APPROVED",
        reason=payload.get("comment") or "Approved by approver"
    )

    return {
        "status": "APPROVED",
        "investigation_id": investigation_id
    }


@router.post(
    "/{investigation_id}/reject"
)
def reject(
    investigation_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.APPROVER.value)
    )
):

    investigation = db.get(
        Investigation,
        investigation_id
    )

    if not investigation:

        raise HTTPException(
            404,
            "Investigation not found"
        )

    approval = Approval(
        id=str(uuid4()),
        investigation_id=investigation_id,
        approver_id=user.id,
        status="REJECTED",
        comment=payload.get("comment")
    )

    investigation.status = "REJECTED"

    break_item = db.get(
        Break,
        investigation.break_id
    )

    if break_item:

        break_item.status = "OPEN"

    db.add(approval)
    db.commit()

    write_audit(
        db,
        user.id,
        "APPROVAL_RECORDED",
        old_value=investigation_id,
        new_value="REJECTED",
        reason=payload.get("comment") or "Rejected by approver"
    )

    return {
        "status": "REJECTED",
        "investigation_id": investigation_id
    }
