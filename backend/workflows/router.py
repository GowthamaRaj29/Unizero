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

from workflows.models import Workflow

from workflows.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse
)

from workflows.service import (
    create_workflow,
    get_workflow,
    update_workflow
)
from audit.service import write_audit


router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"]
)


@router.get(
    "",
    response_model=list[WorkflowResponse]
)
def list_workflows(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    return (
        db.query(Workflow)
        .filter(
            Workflow.created_by == user.id
        )
        .all()
    )


@router.post(
    "",
    response_model=WorkflowResponse
)
def create(
    request: WorkflowCreate,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(
            Role.INVESTIGATOR.value
        )
    )
):

    workflow = create_workflow(
        db,
        request.name,
        request.period,
        user.id
    )

    write_audit(
        db,
        user.id,
        "WORKFLOW_CREATED",
        workflow_id=workflow.id,
        new_value=workflow.name,
        reason="Created through investigator dashboard"
    )

    return workflow


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse
)
def get_one(
    workflow_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    workflow = get_workflow(
        db,
        workflow_id
    )

    if not workflow:

        raise HTTPException(
            404,
            "Workflow not found"
        )

    if (
        workflow.created_by != user.id
        and user.role != Role.APPROVER.value
    ):

        raise HTTPException(
            403,
            "Access denied"
        )

    return workflow


@router.put(
    "/{workflow_id}",
    response_model=WorkflowResponse
)
def update(
    workflow_id: str,
    request: WorkflowUpdate,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(
            Role.INVESTIGATOR.value
        )
    )
):

    workflow = get_workflow(
        db,
        workflow_id
    )

    if not workflow:

        raise HTTPException(
            404,
            "Workflow not found"
        )

    if workflow.created_by != user.id:

        raise HTTPException(
            403,
            "Access denied"
        )

    return update_workflow(
        db,
        workflow,
        request.name,
        request.period,
        request.status
    )


@router.delete(
    "/{workflow_id}"
)
def delete(
    workflow_id: str,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(
            Role.INVESTIGATOR.value
        )
    )
):

    workflow = get_workflow(
        db,
        workflow_id
    )

    if not workflow:

        raise HTTPException(
            404,
            "Workflow not found"
        )

    if workflow.created_by != user.id:

        raise HTTPException(
            403,
            "Access denied"
        )

    db.delete(workflow)
    db.commit()

    return {
        "message": "Workflow deleted"
    }