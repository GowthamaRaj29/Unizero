from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Investigation(Base):

    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    break_id: Mapped[str] = mapped_column(
        ForeignKey("breaks.id")
    )

    investigator_id: Mapped[str] = mapped_column(
        ForeignKey("users.id")
    )

    justification: Mapped[str] = mapped_column(
        Text
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="SUBMITTED"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class Evidence(Base):

    __tablename__ = "investigation_evidence"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id")
    )

    uploaded_by: Mapped[str] = mapped_column(
        ForeignKey("users.id")
    )

    filename: Mapped[str] = mapped_column(
        String(500)
    )

    stored_path: Mapped[str] = mapped_column(
        String(1000)
    )

    size: Mapped[int] = mapped_column(
        default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )