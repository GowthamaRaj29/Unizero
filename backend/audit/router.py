from fastapi import (
    APIRouter,
    Depends
)

from sqlalchemy.orm import Session

from auth.dependencies import get_current_user

from config.database import get_db

from audit.models import AuditLog


router = APIRouter(
    prefix="/audit",
    tags=["Audit"]
)


@router.get(
    "/{workflow_id}"
)
def get_audit_logs(
    workflow_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    return (
        db.query(AuditLog)
        .filter(
            AuditLog.workflow_id == workflow_id
        )
        .order_by(
            AuditLog.timestamp.desc()
        )
        .all()
    )