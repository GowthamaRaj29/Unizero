from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from config.settings import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str) -> str:

    return pwd_context.hash(password)


def verify_password(
    password: str,
    password_hash: str
) -> bool:

    return pwd_context.verify(
        password,
        password_hash
    )


def create_access_token(
    user_id: str,
    role: str
):

    expiration = (
        datetime.now(timezone.utc)
        +
        timedelta(
            minutes=settings.access_token_minutes
        )
    )

    payload = {
        "sub": user_id,
        "role": role,
        "exp": expiration
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )

    return token