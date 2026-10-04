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

from auth.dependencies import (
    get_current_user,
    require_role
)

from common.enums import Role

from workflows.models import (
    DataSource,
    FieldMapping,
    Workflow
)


router = APIRouter(
    prefix="/field-mappings",
    tags=["Field Mappings"]
)


def serialize_mapping(item):

    return {
        "id": item.id,
        "workflow_id": item.workflow_id,
        "source_field": item.source_field,
        "target_field": item.target_field,
        "confidence": item.confidence,
        "method": item.method,
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
def list_field_mappings(
    workflow_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    query = db.query(FieldMapping)

    if workflow_id:

        query = query.filter(
            FieldMapping.workflow_id == workflow_id
        )

    return [
        serialize_mapping(item)
        for item in query.all()
    ]


@router.post("", status_code=201)
def create_field_mapping(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    workflow_id = payload.get("workflow_id")

    source_field = payload.get("source_field")

    target_field = payload.get("target_field")

    if not workflow_id or not source_field or not target_field:

        raise HTTPException(
            400,
            "workflow_id, source_field and target_field are required"
        )

    _require_workflow(db, workflow_id)

    mapping = FieldMapping(
        id=str(uuid4()),
        workflow_id=workflow_id,
        source_field=source_field,
        target_field=target_field,
        confidence=payload.get("confidence", 100),
        method=payload.get("method", "MANUAL")
    )

    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return serialize_mapping(mapping)


@router.get("/{mapping_id}")
def get_field_mapping(
    mapping_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    item = db.get(FieldMapping, mapping_id)

    if not item:

        raise HTTPException(
            404,
            "Field mapping not found"
        )

    return serialize_mapping(item)


@router.put("/{mapping_id}")
def update_field_mapping(
    mapping_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    item = db.get(FieldMapping, mapping_id)

    if not item:

        raise HTTPException(
            404,
            "Field mapping not found"
        )

    if payload.get("source_field"):

        item.source_field = payload["source_field"]

    if payload.get("target_field"):

        item.target_field = payload["target_field"]

    if payload.get("confidence") is not None:

        item.confidence = payload["confidence"]

    if payload.get("method"):

        item.method = payload["method"]

    db.commit()
    db.refresh(item)

    return serialize_mapping(item)


@router.delete("/{mapping_id}")
def delete_field_mapping(
    mapping_id: str,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    item = db.get(FieldMapping, mapping_id)

    if not item:

        raise HTTPException(
            404,
            "Field mapping not found"
        )

    db.delete(item)
    db.commit()

    return {
        "message": "Field mapping deleted"
    }


@router.post("/{mapping_id}/values")
def add_value_crosswalk(
    mapping_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    item = db.get(FieldMapping, mapping_id)

    if not item:

        raise HTTPException(
            404,
            "Field mapping not found"
        )

    return {
        "id": str(uuid4()),
        "field_mapping_id": mapping_id,
        "source_value": payload.get("source_value"),
        "target_value": payload.get("target_value"),
        "status": "CREATED"
    }


@router.post(
    "/crosswalks/upload",
    tags=["Crosswalks"]
)
async def upload_crosswalk(
    workflow_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.INVESTIGATOR.value)
    )
):

    _require_workflow(db, workflow_id)

    content = await file.read()

    try:

        text = content.decode("utf-8-sig")

    except UnicodeDecodeError:

        raise HTTPException(
            400,
            "Crosswalk file must be a CSV or text file"
        )

    created = []

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for line in lines[1:]:

        parts = [
            part.strip()
            for part in line.split(",")
        ]

        if len(parts) < 2:

            continue

        mapping = FieldMapping(
            id=str(uuid4()),
            workflow_id=workflow_id,
            source_field=parts[0],
            target_field=parts[1],
            confidence=100,
            method="CROSSWALK"
        )

        db.add(mapping)

        created.append(mapping)

    if created:

        db.commit()

        for mapping in created:

            db.refresh(mapping)

    return {
        "workflow_id": workflow_id,
        "filename": file.filename,
        "mappings_created": len(created),
        "mappings": [
            serialize_mapping(item)
            for item in created
        ],
    }
