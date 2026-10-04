from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):

    id: str
    username: str
    email: str | None = None
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
