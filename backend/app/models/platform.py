"""Platform-ops models — scheduled-job runs and the application error monitor.

Spec: docs/ref/features/platform.md.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKey
from app.models.enums import ErrorGroupStatus, JobRunResult


class JobRun(UUIDPrimaryKey, Base):
    """One execution record of a scheduled background job."""

    __tablename__ = "job_run"
    __table_args__ = ()

    job_name: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[JobRunResult] = mapped_column(
        Enum(JobRunResult, native_enum=False, length=12), default=JobRunResult.RUNNING
    )
    log: Mapped[str | None] = mapped_column(Text)


class ErrorGroup(UUIDPrimaryKey, Base):
    """An application error grouped by code — counts, last occurrence, status."""

    __tablename__ = "error_group"

    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    module: Mapped[str | None] = mapped_column(String(60))
    message_preview: Mapped[str | None] = mapped_column(String(400))
    count_total: Mapped[int] = mapped_column(Integer, default=0)
    last_occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ErrorGroupStatus] = mapped_column(
        Enum(ErrorGroupStatus, native_enum=False, length=12), default=ErrorGroupStatus.OPEN
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ErrorEvent(UUIDPrimaryKey, Base):
    """One occurrence of an error, linked to its group."""

    __tablename__ = "error_event"

    error_group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("error_group.id"), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    stack: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # masked at write time
    trace_id: Mapped[str | None] = mapped_column(String(40))
    workshop_id: Mapped[uuid.UUID | None] = mapped_column()
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
