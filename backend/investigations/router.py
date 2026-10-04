from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File
)

from sqlalchemy.orm import Session

from auth.dependencies import (
    get_current_user,
    require_role
)

from common.enums import Role

from common.utils import safe_filename

from config.database import get_db

from config.settings import settings

from investigations.models import Evidence, Investigation
from audit.service import write_audit

from users.models import User

from pathlib import Path


router = APIRouter(
    prefix="/investigations",
    tags=["Investigations"]
)


def serialize_investigation(
    db,
    item
):

    investigator = db.get(
        User,
        item.investigator_id
    )

    return {
        "id": item.id,
        "break_id": item.break_id,
        "investigator_id": item.investigator_id,
        "investigator_email": (
            investigator.email
            or investigator.username
            if investigator else None
        ),
        "justification": item.justification,
        "status": item.status,
        "created_at": str(item.created_at)
        if item.created_at else None,
    }


def serialize_evidence(item):
    return {
        "id": item.id,
        "investigation_id": item.investigation_id,
        "uploaded_by": item.uploaded_by,
        "filename": item.filename,
        "size": item.size,
        "created_at": str(item.created_at) if item.created_at else None,
    }


@router.get("")
def list_investigations(
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


@router.post("")
def create_investigation(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    break_id = payload.get("break_id")
    justification = payload.get(
        "justification"
    )

    if not break_id or not justification:

        raise HTTPException(
            400,
            "break_id and justification are required"
        )

    investigation = Investigation(
        id=str(uuid4()),
        break_id=break_id,
        investigator_id=user.id,
        justification=justification,
        status="SUBMITTED"
    )

    db.add(investigation)
    db.commit()
    db.refresh(investigation)

    return serialize_investigation(
        db,
        investigation
    )


@router.get("/{investigation_id}")
def get_investigation(
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
            "Investigation not found"
        )

    return serialize_investigation(
        db,
        investigation
    )


@router.put("/{investigation_id}")
def update_investigation(
    investigation_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
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

    if payload.get("justification"):

        investigation.justification = (
            payload["justification"]
        )

    if payload.get("status"):

        investigation.status = (
            payload["status"]
        )

    db.commit()
    db.refresh(investigation)

    return serialize_investigation(
        db,
        investigation
    )


@router.post("/{investigation_id}/submit")
def submit_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
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

    investigation.status = "SUBMITTED"

    db.commit()
    db.refresh(investigation)

    return serialize_investigation(
        db,
        investigation
    )


@router.post("/{investigation_id}/evidence")
async def upload_evidence(
    investigation_id: str,
    file: UploadFile = File(...),
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
            "Investigation not found"
        )

    upload_dir = Path(settings.upload_dir)

    upload_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    stored_name = safe_filename(
        file.filename or "evidence.bin"
    )

    destination = upload_dir / stored_name

    content = await file.read()

    destination.write_bytes(content)

    evidence = Evidence(
        id=str(uuid4()),
        investigation_id=investigation_id,
        uploaded_by=user.id,
        filename=file.filename or stored_name,
        stored_path=str(destination),
        size=len(content),
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    write_audit(
        db,
        user.id,
        "EVIDENCE_UPLOADED",
        new_value=evidence.filename,
        reason=f"Evidence attached to investigation {investigation_id}"
    )

    return serialize_evidence(evidence)


@router.get("/{investigation_id}/evidence")
def list_evidence(
    investigation_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if not db.get(Investigation, investigation_id):
        raise HTTPException(404, "Investigation not found")

    return [
        serialize_evidence(item)
        for item in db.query(Evidence)
        .filter(Evidence.investigation_id == investigation_id)
        .order_by(Evidence.created_at.desc())
        .all()
    ]
