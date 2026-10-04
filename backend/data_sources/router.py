from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File
)

from sqlalchemy.orm import Session

from config.database import get_db

from config.settings import settings

from auth.dependencies import (
    get_current_user,
    require_role
)

from common.enums import Role

from common.utils import safe_filename

from workflows.models import DataSource, Workflow

from pathlib import Path
from audit.service import write_audit


router = APIRouter(
    prefix="/data-sources",
    tags=["Data Sources"]
)


def serialize_data_source(item):

    return {
        "id": item.id,
        "workflow_id": item.workflow_id,
        "name": item.name,
        "filename": item.filename,
        "status": item.status,
        "ai_session_id": item.ai_session_id,
    }


def _require_workflow(
    db: Session,
    workflow_id: str
):

    workflow = db.get(
        Workflow,
        workflow_id
    )

    if not workflow:

        raise HTTPException(
            404,
            "Workflow not found"
        )

    return workflow


@router.get("")
def list_data_sources(
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
        serialize_data_source(item)
        for item in query.all()
    ]


@router.post("", status_code=201)
def create_data_source(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    workflow_id = payload.get("workflow_id")

    name = payload.get("name")

    if not workflow_id or not name:

        raise HTTPException(
            400,
            "workflow_id and name are required"
        )

    _require_workflow(db, workflow_id)

    data_source = DataSource(
        id=str(uuid4()),
        workflow_id=workflow_id,
        name=name,
        filename=payload.get("filename", name),
        path=payload.get("path", ""),
        ai_session_id=payload.get("ai_session_id"),
        status="UPLOADED"
    )

    db.add(data_source)
    db.commit()
    db.refresh(data_source)

    write_audit(
        db,
        user.id,
        "DATA_SOURCE_CREATED",
        workflow_id=workflow_id,
        new_value=data_source.filename,
        reason="Registered for workflow ingestion"
    )

    return serialize_data_source(data_source)


@router.get("/{data_source_id}")
def get_data_source(
    data_source_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    item = db.get(DataSource, data_source_id)

    if not item:

        raise HTTPException(
            404,
            "Data source not found"
        )

    return serialize_data_source(item)


@router.put("/{data_source_id}")
def update_data_source(
    data_source_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    item = db.get(DataSource, data_source_id)

    if not item:

        raise HTTPException(
            404,
            "Data source not found"
        )

    if payload.get("name"):

        item.name = payload["name"]

    if payload.get("status"):

        item.status = payload["status"]

    if payload.get("ai_session_id"):

        item.ai_session_id = payload["ai_session_id"]

    db.commit()
    db.refresh(item)

    return serialize_data_source(item)


@router.delete("/{data_source_id}")
def delete_data_source(
    data_source_id: str,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    item = db.get(DataSource, data_source_id)

    if not item:

        raise HTTPException(
            404,
            "Data source not found"
        )

    db.delete(item)
    db.commit()

    return {
        "message": "Data source deleted"
    }


@router.post("/upload")
def upload_data_source(
    workflow_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    _require_workflow(db, workflow_id)

    upload_dir = Path(settings.upload_dir)

    upload_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    stored_name = safe_filename(
        file.filename or "upload.bin"
    )

    destination = upload_dir / stored_name

    content = file.file.read()

    destination.write_bytes(content)

    data_source = DataSource(
        id=str(uuid4()),
        workflow_id=workflow_id,
        name=file.filename or stored_name,
        filename=file.filename or stored_name,
        path=str(destination),
        status="UPLOADED"
    )

    db.add(data_source)
    db.commit()
    db.refresh(data_source)

    write_audit(
        db,
        user.id,
        "DATA_UPLOADED",
        workflow_id=workflow_id,
        new_value=data_source.filename,
        reason="Uploaded through investigator dashboard"
    )

    return serialize_data_source(data_source)
