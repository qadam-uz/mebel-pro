"""Schemas for the platform-ops surfaces — jobs, errors, audit, dashboard."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import (
    ActorType,
    ErrorGroupStatus,
    JobRunResult,
    WorkshopStatus,
)
from app.schemas.common import APIModel

# --- jobs console -----------------------------------------------------------


class JobOut(BaseModel):
    name: str
    interval_seconds: int
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_result: JobRunResult | None
    last_log: str | None


# --- error monitor ----------------------------------------------------------


class ErrorGroupRow(BaseModel):
    id: uuid.UUID
    code: str
    module: str | None
    message_preview: str | None
    status: ErrorGroupStatus
    count_total: int
    count_24h: int
    count_7d: int
    last_occurred_at: datetime | None


class ErrorEventOut(APIModel):
    id: uuid.UUID
    message: str | None
    stack: str | None
    context: dict[str, Any] | None
    trace_id: str | None
    workshop_id: uuid.UUID | None
    occurred_at: datetime


class ErrorGroupDetail(BaseModel):
    id: uuid.UUID
    code: str
    module: str | None
    message_preview: str | None
    status: ErrorGroupStatus
    count_total: int
    count_24h: int
    count_7d: int
    last_occurred_at: datetime | None
    resolved_at: datetime | None
    affected_workshops: list[str]
    trace_ids: list[str]
    events: list[ErrorEventOut]


# --- audit viewer -----------------------------------------------------------


class ActionLogRow(APIModel):
    id: uuid.UUID
    actor_type: ActorType
    actor_user_id: uuid.UUID | None
    actor_client_id: uuid.UUID | None
    workshop_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    action: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    summary: str | None
    details: dict[str, Any] | None
    trace_id: str
    created_at: datetime


class StatusChangeRow(APIModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    workshop_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    from_status: str | None
    to_status: str
    actor_type: ActorType
    actor_user_id: uuid.UUID | None
    actor_client_id: uuid.UUID | None
    reason: str | None
    changed_at: datetime


# --- dashboard --------------------------------------------------------------


class RecentWorkshop(APIModel):
    id: uuid.UUID
    name: str
    status: WorkshopStatus
    created_at: datetime


class DashboardOut(BaseModel):
    workshops_count: int
    branches_count: int
    clients_count: int
    recent_workshops: list[RecentWorkshop]
    failed_jobs_24h: int
    open_error_groups: int
