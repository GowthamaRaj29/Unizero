from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from workflows.models import Workflow


def create_workflow(
    db: Session,
    name: str,
    period: str,
    created_by: str
):

    workflow = Workflow(
        id=str(uuid4()),
        name=name,
        period=period,
        created_by=created_by,
        status="DRAFT"
    )

    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    return workflow


def get_workflow(
    db: Session,
    workflow_id: str
):

    return db.get(
        Workflow,
        workflow_id
    )


def update_workflow(
    db: Session,
    workflow,
    name=None,
    period=None,
    status=None
):

    if name is not None:
        workflow.name = name

    if period is not None:
        workflow.period = period

    if status is not None:
        workflow.status = status

    workflow.updated_at = datetime.now(
        timezone.utc
    )

    db.commit()
    db.refresh(workflow)

    return workflow