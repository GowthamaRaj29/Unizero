from uuid import uuid4

from sqlalchemy.orm import Session

from auth.security import hash_password
from users.models import User


def create_user(
    db: Session,
    username: str,
    password: str,
    role: str
):

    user = User(
        id=str(uuid4()),
        username=username,
        password_hash=hash_password(password),
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user