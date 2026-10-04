from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Approval(Base):

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id")
    )

    approver_id: Mapped[str] = mapped_column(
        ForeignKey("users.id")
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING"
    )

    comment: Mapped[str | None] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )