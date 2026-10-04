from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from config.database import get_db

from auth.dependencies import require_role

from common.enums import Role

from users.models import User

from users.schemas import UserOut

from audit.models import AuditLog

from audit.service import write_audit


router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


ROLE_PERMISSIONS = {
    "ADMIN": [
        "users.view",
        "users.create",
        "users.update",
        "users.disable",
        "roles.view",
        "roles.manage",
        "permissions.view",
        "permissions.manage",
        "system.manage",
        "audit.view",
        "reconciliation.view",
        "reports.view",
    ],
    "INVESTIGATOR": [
        "reconciliation.view",
        "breaks.view",
        "investigation.view",
        "investigation.create",
        "investigation.update",
        "evidence.view",
        "evidence.upload",
        "investigation.submit",
    ],
    "APPROVER": [
        "reconciliation.view",
        "breaks.view",
        "investigation.view",
        "approval.view",
        "approval.approve",
        "approval.reject",
        "approval.history",
    ],
}


def require_admin(user=Depends(require_role(Role.ADMIN.value))):
    return user


@router.get(
    "/users",
    response_model=list[UserOut]
)
def list_users(
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    return db.query(User).all()


@router.post(
    "/users",
    response_model=UserOut,
    status_code=201
)
def create_user(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    username = payload.get("username") or payload.get("email")

    if not username or not payload.get("password"):

        raise HTTPException(
            400,
            "username/email and password are required"
        )

    existing = (
        db.query(User)
        .filter(
            (User.username == username)
            | (User.email == username)
        )
        .first()
    )

    if existing:

        raise HTTPException(
            409,
            "User already exists"
        )

    from auth.security import hash_password

    new_user = User(
        id=str(uuid4()),
        username=username,
        email=payload.get("email", username),
        full_name=payload.get("full_name"),
        password_hash=hash_password(
            payload["password"]
        ),
        role=(
            payload.get("role", "INVESTIGATOR")
            .upper()
        ),
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    write_audit(
        db,
        user.id,
        "USER_CREATED",
        new_value=username,
        reason="Created via admin console"
    )

    return new_user


@router.put(
    "/users/{user_id}",
    response_model=UserOut
)
def update_user(
    user_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    target = db.get(User, user_id)

    if not target:

        raise HTTPException(
            404,
            "User not found"
        )

    if payload.get("role"):

        target.role = payload["role"].upper()

    if payload.get("is_active") is not None:

        target.is_active = bool(
            payload["is_active"]
        )

    db.commit()
    db.refresh(target)

    write_audit(
        db,
        user.id,
        "USER_UPDATED",
        new_value=target.username,
        reason="Updated via admin console"
    )

    return target


@router.post("/users/{user_id}/disable")
def disable_user(
    user_id: str,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    target = db.get(User, user_id)

    if not target:

        raise HTTPException(
            404,
            "User not found"
        )

    target.is_active = False

    db.commit()

    write_audit(
        db,
        user.id,
        "USER_DISABLED",
        old_value=target.username,
        reason="Disabled via admin console"
    )

    return {
        "id": target.id,
        "is_active": target.is_active
    }


@router.get("/pending-registrations")
def pending_registrations(
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    users = (
        db.query(User)
        .filter(User.is_active == False)  # noqa: E712
        .all()
    )

    return [
        {
            "id": item.id,
            "full_name": item.full_name,
            "email": item.email or item.username,
            "role": item.role.lower(),
            "requested_at": str(item.created_at)
            if item.created_at else None,
        }
        for item in users
    ]


@router.post(
    "/pending-registrations/{user_id}/approve"
)
def approve_registration(
    user_id: str,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    target = db.get(User, user_id)

    if not target:

        raise HTTPException(
            404,
            "Registration not found"
        )

    target.is_active = True

    db.commit()

    write_audit(
        db,
        user.id,
        "REGISTRATION_APPROVED",
        new_value=target.username,
        reason="Approved by administrator"
    )

    return {
        "id": target.id,
        "status": "APPROVED"
    }


@router.post(
    "/pending-registrations/{user_id}/reject"
)
def reject_registration(
    user_id: str,
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    target = db.get(User, user_id)

    if not target:

        raise HTTPException(
            404,
            "Registration not found"
        )

    target.is_active = False

    db.commit()

    write_audit(
        db,
        user.id,
        "REGISTRATION_REJECTED",
        old_value=target.username,
        reason="Rejected by administrator"
    )

    return {
        "id": target.id,
        "status": "REJECTED"
    }


@router.get("/roles")
def get_roles(
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    return [
        {
            "id": name,
            "name": name,
            "description": description,
            "permission_count": len(
                ROLE_PERMISSIONS[name]
            ),
        }
        for name, description in [
            (
                "ADMIN",
                "Manage users, roles, permissions, system configuration and audit activity."
            ),
            (
                "APPROVER",
                "Review and authorize investigation resolutions."
            ),
            (
                "INVESTIGATOR",
                "Investigate reconciliation breaks and submit resolutions."
            ),
        ]
    ]


@router.get("/permissions")
def get_permissions(
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    return ROLE_PERMISSIONS


@router.get("/audit-logs")
def get_audit_logs(
    db: Session = Depends(get_db),
    user=Depends(
        require_role(Role.ADMIN.value)
    )
):

    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(200)
        .all()
    )

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "workflow_id": log.workflow_id,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "reason": log.reason,
            "timestamp": str(log.timestamp)
            if log.timestamp else None,
        }
        for log in logs
    ]
