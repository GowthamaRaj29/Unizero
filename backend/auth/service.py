from sqlalchemy.orm import Session

from users.models import User
from auth.security import (
    verify_password,
    create_access_token
)
from auth.schemas import RegisterRequest


def authenticate(
    db: Session,
    username: str,
    password: str
):

    user = (
        db.query(User)
        .filter(
            (User.username == username)
            | (User.email == username)
        )
        .first()
    )

    if not user:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.password_hash
    ):
        return None

    token = create_access_token(
        user.id,
        user.role
    )

    return user, token


def register_user(
    db: Session,
    request: RegisterRequest
):

    existing = (
        db.query(User)
        .filter(
            (User.username == request.email)
            | (User.email == request.email)
        )
        .first()
    )

    if existing:

        return existing, False

    from auth.security import hash_password

    from uuid import uuid4

    is_first_user = db.query(User).count() == 0
    requested_role = (request.role or "INVESTIGATOR").upper()
    role = "ADMIN" if is_first_user else requested_role

    if role not in ("INVESTIGATOR", "APPROVER", "ADMIN") or (
        role == "ADMIN" and not is_first_user
    ):

        role = "INVESTIGATOR"

    user = User(
        id=str(uuid4()),
        username=request.email,
        email=request.email,
        full_name=request.full_name,
        password_hash=hash_password(request.password),
        role=role,
        is_active=is_first_user
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user, not is_first_user
