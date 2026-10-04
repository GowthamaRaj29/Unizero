from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class AuditLog(Base):

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id")
    )

    action: Mapped[str] = mapped_column(
        String(200)
    )

    workflow_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflows.id")
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    old_value: Mapped[str | None] = mapped_column(
        Text
    )

    new_value: Mapped[str | None] = mapped_column(
        Text
    )

    reason: Mapped[str | None] = mapped_column(
        Text
    )