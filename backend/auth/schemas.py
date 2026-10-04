from pydantic import BaseModel, ConfigDict, field_validator


class LoginRequest(BaseModel):

    username: str | None = None
    email: str | None = None
    password: str

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_identity(cls, value):
        if value is None:
            return value

        return str(value).strip()

    @property
    def login_name(self):
        return (self.username or self.email or "").strip()


class LoginResponse(BaseModel):

    user_id: str
    username: str
    role: str
    token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):

    full_name: str
    email: str
    password: str
    role: str = "INVESTIGATOR"


class RegisterResponse(BaseModel):

    user_id: str
    username: str
    role: str


class UserResponse(BaseModel):

    id: str
    username: str
    email: str | None = None
    full_name: str | None = None
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)