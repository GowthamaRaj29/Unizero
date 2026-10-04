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

from workflows.models import DataSource


router = APIRouter(
    prefix="/ingestion",
    tags=["Ingestion"]
)


# In-memory session registry. The DataSource model
# tracks status; this registry holds per-run detail.
SESSIONS = {}


def build_session(data_source):

    return {
        "id": data_source.id,
        "data_source_id": data_source.id,
        "workflow_id": data_source.workflow_id,
        "name": data_source.name,
        "filename": data_source.filename,
        "status": data_source.status,
    }


@router.get("/sessions")
def list_sessions(
    workflow_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    query = db.query(DataSource)

    if workflow_id:

        query = query.filter(
            DataSource.workflow_id == workflow_id
        )

    return [
        build_session(item)
        for item in query.all()
    ]


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    item = db.get(DataSource, session_id)

    if not item:

        raise HTTPException(
            404,
            "Ingestion session not found"
        )

    session = build_session(item)

    session["detail"] = SESSIONS.get(
        session_id,
        {}
    )

    return session


@router.post("/start")
def start_ingestion(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    data_source_id = payload.get(
        "data_source_id"
    )

    if not data_source_id:

        raise HTTPException(
            400,
            "data_source_id is required"
        )

    item = db.get(DataSource, data_source_id)

    if not item:

        raise HTTPException(
            404,
            "Data source not found"
        )

    item.status = "INGESTING"

    SESSIONS[data_source_id] = {
        "started_by": user.id,
        "attempts": (
            SESSIONS.get(
                data_source_id,
                {}
            ).get("attempts", 0)
            + 1
        ),
    }

    db.commit()
    db.refresh(item)

    return build_session(item)


@router.post("/{session_id}/validate")
def validate_session(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    item = db.get(DataSource, session_id)

    if not item:

        raise HTTPException(
            404,
            "Ingestion session not found"
        )

    item.status = "VALIDATED"

    db.commit()
    db.refresh(item)

    return build_session(item)


@router.post("/{session_id}/approve")
def approve_session(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(
            Role.INVESTIGATOR.value,
            Role.APPROVER.value
        )
    )
):

    item = db.get(DataSource, session_id)

    if not item:

        raise HTTPException(
            404,
            "Ingestion session not found"
        )

    item.status = "APPROVED"

    db.commit()
    db.refresh(item)

    return build_session(item)


@router.post("/{session_id}/retry")
def retry_session(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    item = db.get(DataSource, session_id)

    if not item:

        raise HTTPException(
            404,
            "Ingestion session not found"
        )

    item.status = "INGESTING"

    detail = SESSIONS.get(session_id, {})

    detail["attempts"] = (
        detail.get("attempts", 0) + 1
    )

    SESSIONS[session_id] = detail

    db.commit()
    db.refresh(item)

    return build_session(item)
