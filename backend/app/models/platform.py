"""Platform job and error-monitor foundation models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import ErrorRecordStatus, JobRunStatus, enum_type


class JobDefinition(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "job_definitions"
    __table_args__ = (UniqueConstraint("name", name="uq_job_definitions_name"),)

    name: Mapped[str] = mapped_column(nullable=False)
    schedule: Mapped[str] = mapped_column(nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    running: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_run_at: Mapped[datetime | None]
    last_result: Mapped[JobRunStatus | None] = mapped_column(
        enum_type(JobRunStatus, "job_run_status")
    )


class JobRun(UUIDPrimaryKey, Base):
    __tablename__ = "job_runs"
    __table_args__ = (Index("ix_job_runs_job_started", "job_name", "started_at"),)

    job_definition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_definitions.id"))
    job_name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[JobRunStatus] = mapped_column(
        enum_type(JobRunStatus, "job_run_status"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None]
    brief_log: Mapped[str | None]
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    trace_id: Mapped[str | None]


class ErrorRecord(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "error_records"
    __table_args__ = (
        UniqueConstraint("code", name="uq_error_records_code"),
        CheckConstraint("count_24h >= 0 AND count_7d >= 0", name="ck_error_records_counts"),
    )

    code: Mapped[str] = mapped_column(nullable=False)
    module: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[ErrorRecordStatus] = mapped_column(
        enum_type(ErrorRecordStatus, "error_record_status"),
        default=ErrorRecordStatus.OPEN,
        nullable=False,
    )
    count_24h: Mapped[int] = mapped_column(default=0, nullable=False)
    count_7d: Mapped[int] = mapped_column(default=0, nullable=False)
    last_occurred_at: Mapped[datetime | None]
    preview_message: Mapped[str | None]
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("platform_users.id"))
    resolved_at: Mapped[datetime | None]


class ErrorOccurrence(UUIDPrimaryKey, Base):
    __tablename__ = "error_occurrences"
    __table_args__ = (Index("ix_error_occurrences_record_time", "error_record_id", "occurred_at"),)

    error_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("error_records.id"), nullable=False
    )
    trace_id: Mapped[str] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(nullable=False)
    stack: Mapped[str | None]
    context: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    workshop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshops.id"))
    user_id: Mapped[uuid.UUID | None]
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
