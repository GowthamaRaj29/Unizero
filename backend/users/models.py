from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class User(Base):

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True
    )

    full_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True
    )

    password_hash: Mapped[str] = mapped_column(
        String(255)
    )

    role: Mapped[str] = mapped_column(
        String(30)
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )