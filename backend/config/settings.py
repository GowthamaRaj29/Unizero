from pathlib import Path
import secrets

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
BACKEND_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
LOCAL_SECRET_FILE = Path(__file__).resolve().parents[2] / ".jwt-secret"


def _local_jwt_secret() -> str:
    if LOCAL_SECRET_FILE.exists():
        return LOCAL_SECRET_FILE.read_text(encoding="utf-8").strip()

    secret = secrets.token_urlsafe(32)
    LOCAL_SECRET_FILE.write_text(secret, encoding="utf-8")
    return secret


class Settings(BaseSettings):

    app_name: str = "OneRecon Backend"

    database_url: str = (
        "sqlite:///./onerecon.db"
    )

    jwt_secret: str = Field(
        default_factory=_local_jwt_secret
    )
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60


    frontend_origins_raw: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    ai_service_url: str = "http://127.0.0.1:8001"

    upload_dir: str = "./storage/uploads"

    model_config = SettingsConfigDict(
        env_file=[str(ROOT_ENV_FILE), str(BACKEND_ENV_FILE)],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def frontend_origins(self):
        return [
            origin.strip()
            for origin in self.frontend_origins_raw.split(",")
            if origin.strip()
        ]


settings = Settings()