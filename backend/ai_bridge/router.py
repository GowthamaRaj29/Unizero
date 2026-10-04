from datetime import datetime, timezone

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

from breaks.models import Break

from ai_client import ai_get, ai_post


router = APIRouter(
    prefix="/ai",
    tags=["AI Bridge"]
)


def _upsert_breaks(
    db: Session,
    workflow_id: str,
    items: list[dict]
):

    """
    Mirror AI-service breaks into the backend DB so
    the frontend has one stable authenticated source
    for the Breaks table and investigations.
    """

    from uuid import uuid4

    known_ids = set()

    for item in items:

        ai_break_id = item.get("break_id")

        if not ai_break_id:

            continue

        known_ids.add(ai_break_id)

        existing = (
            db.query(Break)
            .filter(Break.id == ai_break_id)
            .first()
        )

        rca = item.get("current_rca") or {}

        if existing:

            existing.status = item.get(
                "status",
                existing.status
            )

            existing.ai_explanation = (
                rca.get("root_cause")
                or existing.ai_explanation
            )

            continue

        priority = item.get("priority") or {}

        db.add(
            Break(
                id=ai_break_id,
                workflow_id=workflow_id,
                run_id=None,
                result_id=None,
                break_type=(
                    ",".join(
                        item.get("break_types")
                        or ["UNKNOWN"]
                    )
                ),
                reconciliation_key=item.get(
                    "break_key"
                ),
                field=None,
                source_a_value=None,
                source_b_value=None,
                difference=None,
                status=item.get(
                    "status", "OPEN"
                ),
                description=(
                    rca.get("root_cause")
                ),
                ai_explanation=(
                    rca.get("root_cause")
                ),
                ai_confidence=None,
                explanation=None
            )
        )

    db.commit()

    return known_ids


@router.post(
    "/workflows/{workflow_id}/analyze"
)
def analyze_workflow(
    workflow_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    mapping_session_id = payload.get(
        "mapping_session_id"
    )

    if not mapping_session_id:

        raise HTTPException(
            400,
            "mapping_session_id is required"
        )

    ok, created = ai_post(
        "/breaks/analyze",
        {
            "mapping_session_id":
                mapping_session_id,
            "key_field": payload.get(
                "key_field",
                "TransactionID"
            ),
            "amount_tolerance":
                payload.get(
                    "amount_tolerance",
                    0.01
                ),
            "actor": user.id
        }
    )

    if not ok:

        raise HTTPException(
            503,
            "AI services is unreachable - "
            "start it on port 8001 "
            "(uvicorn app:app --port 8001)"
        )

    if not created:
        remote_ok, remote = ai_get(
            "/breaks?mapping_session_id="
            + mapping_session_id
        )
        if remote_ok and isinstance(remote, list):
            created = remote

    _upsert_breaks(
        db,
        workflow_id,
        created or []
    )

    return {
        "workflow_id": workflow_id,
        "breaks_created": len(
            created or []
        ),
        "breaks": created or []
    }


@router.get(
    "/workflows/{workflow_id}/breaks"
)
def list_ai_breaks(
    workflow_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    ok, remote = ai_get("/breaks")

    if ok and isinstance(remote, list):

        _upsert_breaks(
            db,
            workflow_id,
            [
                item
                for item in remote
                if item.get(
                    "mapping_session_id"
                )
                is not None
                or True
            ]
        )

    breaks = (
        db.query(Break)
        .filter(
            Break.workflow_id == workflow_id
        )
        .all()
    )

    return [
        {
            "id": item.id,
            "workflow_id": item.workflow_id,
            "run_id": item.run_id,
            "result_id": item.result_id,
            "break_type": item.break_type,
            "key": item.reconciliation_key,
            "field": item.field,
            "source_a_value":
                item.source_a_value,
            "source_b_value":
                item.source_b_value,
            "difference": item.difference,
            "status": item.status,
            "description": item.description,
            "ai_explanation":
                item.ai_explanation,
            "ai_confidence":
                item.ai_confidence,
            "created_at": str(
                item.created_at
            )
            if item.created_at else None,
        }
        for item in breaks
    ]


@router.post(
    "/breaks/{break_id}/investigator/cause"
)
def submit_ai_cause(
    break_id: str,
    payload: dict,
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    ok, result = ai_post(
        f"/breaks/{break_id}"
        "/investigator/cause",
        {
            "actor": user.id,
            "role": "INVESTIGATOR",
            "cause": payload.get(
                "cause", ""
            ),
            "override_rca": payload.get(
                "override_rca", False
            )
        }
    )

    if not ok:

        raise HTTPException(
            503,
            "AI services unreachable or "
            "break not found"
        )

    return result


@router.post(
    "/breaks/{break_id}/authorize"
)
def authorize_ai_break(
    break_id: str,
    payload: dict,
    user=Depends(
        require_role(Role.APPROVER.value)
    )
):

    ok, result = ai_post(
        f"/breaks/{break_id}/authorize",
        {
            "actor": user.id,
            "role": "APPROVER",
            "target_status": payload.get(
                "target_status",
                "RESOLVED"
            ),
            "note": payload.get("comment")
        }
    )

    if not ok:

        raise HTTPException(
            503,
            "AI services unreachable or "
            "break not found"
        )

    return result
