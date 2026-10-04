from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    Float,
    Text,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Workflow(Base):

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(200)
    )

    period: Mapped[str] = mapped_column(
        String(50)
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="DRAFT"
    )

    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class DataSource(Base):

    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id")
    )

    name: Mapped[str] = mapped_column(
        String(200)
    )

    filename: Mapped[str] = mapped_column(
        String(500)
    )

    path: Mapped[str] = mapped_column(
        String(1000)
    )

    ai_session_id: Mapped[str | None] = mapped_column(
        String(100)
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="UPLOADED"
    )


class FieldMapping(Base):

    __tablename__ = "field_mappings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id")
    )

    source_field: Mapped[str] = mapped_column(
        String(200)
    )

    target_field: Mapped[str] = mapped_column(
        String(200)
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    method: Mapped[str] = mapped_column(
        String(50),
        default="AI"
    )


class ReconciliationRun(Base):

    __tablename__ = "reconciliation_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id")
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="RUNNING"
    )

    total_records: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    matched_count: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    break_count: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    total_variance: Mapped[float] = mapped_column(
        Float,
        default=0
    )


class ReconciliationResult(Base):

    __tablename__ = "reconciliation_results"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id")
    )

    result_type: Mapped[str] = mapped_column(
        String(30)
    )

    record_key: Mapped[str] = mapped_column(
        String(200)
    )

    source_a_value: Mapped[str | None] = mapped_column(
        Text
    )

    source_b_value: Mapped[str | None] = mapped_column(
        Text
    )

    difference: Mapped[float | None] = mapped_column(
        Float
    )