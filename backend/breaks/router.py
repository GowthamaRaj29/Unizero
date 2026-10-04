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

from common.enums import Role, BreakStatus

from breaks.models import Break

from investigations.models import Investigation


router = APIRouter(
    prefix="/breaks",
    tags=["Breaks"]
)


def serialize_break(break_item):

    return {
        "id": break_item.id,
        "workflow_id": break_item.workflow_id,
        "run_id": break_item.run_id,
        "result_id": break_item.result_id,
        "break_type": break_item.break_type or "TRANSACTION",
        "key": break_item.reconciliation_key,
        "field": break_item.field,
        "source_a_value": break_item.source_a_value,
        "source_b_value": break_item.source_b_value,
        "difference": break_item.difference,
        "status": break_item.status,
        "description": break_item.description,
        "ai_explanation": break_item.ai_explanation,
        "ai_confidence": break_item.ai_confidence,
        "created_at": str(break_item.created_at)
            if break_item.created_at else None,
    }


@router.get("")
def list_breaks(
    workflow_id: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    query = db.query(Break)

    if workflow_id:
        query = query.filter(
            Break.workflow_id == workflow_id
        )

    if run_id:
        query = query.filter(
            Break.run_id == run_id
        )

    if status:
        query = query.filter(
            Break.status == status.upper()
        )

    return [
        serialize_break(item)
        for item in query.all()
    ]


@router.get("/{break_id}")
def get_break(
    break_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    break_item = db.get(Break, break_id)

    if not break_item:

        raise HTTPException(
            404,
            "Break not found"
        )

    return serialize_break(break_item)


@router.post(
    "/{break_id}/investigate",
    dependencies=[
        Depends(
            require_role(
                Role.INVESTIGATOR.value
            )
        )
    ]
)
def start_investigation(
    break_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(
            Role.INVESTIGATOR.value
        )
    )
):

    break_item = db.get(Break, break_id)

    if not break_item:

        raise HTTPException(
            404,
            "Break not found"
        )

    break_item.status = (
        BreakStatus.INVESTIGATING.value
    )

    if payload.get("notes"):

        break_item.explanation = (
            payload["notes"]
        )

    db.commit()

    return {
        "id": break_item.id,
        "status": break_item.status
    }


@router.post(
    "/{break_id}/submit",
    dependencies=[
        Depends(
            require_role(
                Role.INVESTIGATOR.value
            )
        )
    ]
)
def submit_investigation(
    break_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(
            Role.INVESTIGATOR.value
        )
    )
):

    break_item = db.get(Break, break_id)

    if not break_item:

        raise HTTPException(
            404,
            "Break not found"
        )

    justification = (
        payload.get("justification")
        or payload.get("notes")
        or ""
    )

    if not justification.strip():

        raise HTTPException(
            400,
            "justification is required"
        )

    investigation = Investigation(
        id=str(uuid4()),
        break_id=break_id,
        investigator_id=user.id,
        justification=justification,
        status="SUBMITTED"
    )

    break_item.status = "SUBMITTED_FOR_APPROVAL"

    db.add(investigation)
    db.commit()
    db.refresh(investigation)

    return {
        "id": investigation.id,
        "break_id": break_id,
        "status": investigation.status
    }
