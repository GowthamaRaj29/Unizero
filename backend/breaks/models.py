from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Float,
    ForeignKey
)

from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Break(Base):

    __tablename__ = "breaks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id"),
        index=True
    )

    run_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True
    )

    result_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True
    )

    break_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    reconciliation_key: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True
    )

    field: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True
    )

    source_a_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    source_b_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    difference: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="OPEN",
        index=True
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    ai_explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    ai_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
