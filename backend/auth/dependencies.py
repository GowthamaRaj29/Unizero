from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from jose import jwt, JWTError
from sqlalchemy.orm import Session

from config.database import get_db
from config.settings import settings
from users.models import User


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login"
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

    try:

        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )

        user_id = payload.get("sub")

        if not user_id:
            raise credentials_error

    except JWTError:

        raise credentials_error

    user = db.get(User, user_id)

    if not user:
        raise credentials_error

    if not user.is_active:
        raise credentials_error

    return user


def require_role(*allowed_roles):

    def role_checker(
        user=Depends(get_current_user)
    ):

        if user.role not in allowed_roles:

            raise HTTPException(
                status_code=403,
                detail="You do not have permission"
            )

        return user

    return role_checker