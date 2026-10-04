from uuid import uuid4

from audit.models import AuditLog


def write_audit(
    db,
    user_id,
    action,
    workflow_id=None,
    old_value=None,
    new_value=None,
    reason=None
):

    log = AuditLog(
        id=str(uuid4()),
        user_id=user_id,
        action=action,
        workflow_id=workflow_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason
    )

    db.add(log)
    db.commit()

    return log