from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from users.schemas import UserOut


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get(
    "/me",
    response_model=UserOut
)
def get_my_profile(
    user=Depends(get_current_user)
):

    return user