from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from fastapi.responses import StreamingResponse

from sqlalchemy.orm import Session

from auth.dependencies import get_current_user

from config.database import get_db

from workflows.models import Workflow

from reports.service import (
    create_pdf_report,
    create_excel_report
)

from breaks.models import Break


router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)


@router.get(
    "/{workflow_id}/pdf"
)
def pdf_report(
    workflow_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
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

    breaks = (
        db.query(Break)
        .filter(
            Break.workflow_id == workflow_id
        )
        .all()
    )

    pdf = create_pdf_report(
        workflow.name,
        workflow.period,
        breaks
    )

    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
            f'attachment; filename="{workflow.name}.pdf"'
        }
    )


@router.get(
    "/{workflow_id}/excel"
)
def excel_report(
    workflow_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
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

    breaks = (
        db.query(Break)
        .filter(
            Break.workflow_id == workflow_id
        )
        .all()
    )

    excel = create_excel_report(
        breaks
    )

    return StreamingResponse(
        excel,
        media_type=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition":
            f'attachment; filename="{workflow.name}.xlsx"'
        }
    )