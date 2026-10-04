from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    UserResponse
)

from auth.service import (
    authenticate,
    register_user
)
from auth.dependencies import get_current_user
from config.database import get_db


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post(
    "/login",
    response_model=LoginResponse
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):

    login_name = request.login_name

    if not login_name:
        raise HTTPException(
            status_code=400,
            detail="Username or email is required"
        )

    result = authenticate(
        db,
        login_name,
        request.password
    )

    if not result:

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    user, token = result

    return LoginResponse(
        user_id=user.id,
        username=user.username,
        role=user.role,
        token=token
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):

    user, pending = register_user(
        db,
        request
    )

    if pending:

        raise HTTPException(
            status_code=202,
            detail="Registration request submitted for administrator approval"
        )

    return RegisterResponse(
        user_id=user.id,
        username=user.username,
        role=user.role
    )


@router.get(
    "/me",
    response_model=UserResponse
)
def me(
    user=Depends(get_current_user)
):

    return user
