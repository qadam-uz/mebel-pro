"""Platform operations API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator

from app.models.enums import (
    ActorType,
    BranchStatus,
    Currency,
    ErrorRecordStatus,
    JobRunStatus,
    UserStatus,
    WorkshopStatus,
)
from app.modules.workshop.schemas import WorkingHours, validate_working_hours
from app.schemas.common import APIModel


class WorkshopInput(BaseModel):
    name: str
    phone: str
    address: str | None = None
    code: str | None = None
    currency: Currency = Currency.UZS


class FirstBranchInput(BaseModel):
    name: str
    address: str
    phone: str
    latitude: Decimal
    longitude: Decimal
    working_hours: WorkingHours

    @field_validator("working_hours")
    @classmethod
    def _validate_working_hours(cls, value: WorkingHours) -> WorkingHours:
        return validate_working_hours(value)


class OwnerInput(BaseModel):
    full_name: str
    login: str
    phone: str


class ProvisionWorkshopRequest(BaseModel):
    workshop: WorkshopInput
    branch: FirstBranchInput
    owner: OwnerInput
    temp_password: str | None = None


class WorkshopSummary(APIModel):
    id: uuid.UUID
    code: str
    name: str
    phone: str
    address: str | None
    status: WorkshopStatus
    currency: Currency
    owner_user_id: uuid.UUID
    created_at: datetime


class BranchSummary(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    name: str
    address: str
    phone: str
    latitude: Decimal
    longitude: Decimal
    working_hours: dict[str, Any]
    status: BranchStatus
    closed_reason: str | None
    created_at: datetime


class WorkshopUserSummary(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    login: str
    full_name: str
    phone: str
    is_owner: bool
    home_branch_id: uuid.UUID | None
    status: UserStatus
    password_reset_required: bool
    created_at: datetime


class ProvisionWorkshopResponse(APIModel):
    workshop: WorkshopSummary
    branch: BranchSummary
    owner: WorkshopUserSummary
    temp_password: str


class PlatformWorkshopDetail(APIModel):
    workshop: WorkshopSummary
    branches: list[BranchSummary]
    owner: WorkshopUserSummary


class BlockWorkshopRequest(BaseModel):
    reason: str


class PlatformUserCreateRequest(BaseModel):
    full_name: str
    login: str
    phone: str
    temp_password: str | None = None


class PlatformUserPatchRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None


class PlatformUserResponse(APIModel):
    id: uuid.UUID
    login: str
    full_name: str
    phone: str
    status: UserStatus
    password_reset_required: bool
    failed_login_count: int
    locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PlatformUserTempPasswordResponse(APIModel):
    user: PlatformUserResponse
    temp_password: str


class BlockPlatformUserRequest(BaseModel):
    reason: str


class JobDefinitionResponse(APIModel):
    id: uuid.UUID
    name: str
    schedule: str
    enabled: bool
    running: bool
    last_run_at: datetime | None
    last_result: JobRunStatus | None
    updated_at: datetime


class JobRunResponse(APIModel):
    id: uuid.UUID
    job_definition_id: uuid.UUID | None
    job_name: str
    status: JobRunStatus
    started_at: datetime
    finished_at: datetime | None
    brief_log: str | None
    error_code: str | None
    error_message: str | None
    trace_id: str | None


class PlatformJobSummary(APIModel):
    definition: JobDefinitionResponse
    recent_runs: list[JobRunResponse]


class ErrorRecordSummary(APIModel):
    id: uuid.UUID
    code: str
    module: str
    status: ErrorRecordStatus
    count_24h: int
    count_7d: int
    last_occurred_at: datetime | None
    preview_message: str | None
    resolved_by_user_id: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ErrorOccurrenceResponse(APIModel):
    id: uuid.UUID
    error_record_id: uuid.UUID
    trace_id: str
    message: str
    stack: str | None
    context: dict[str, Any] | None
    workshop_id: uuid.UUID | None
    user_id: uuid.UUID | None
    occurred_at: datetime


class ErrorRecordDetail(APIModel):
    record: ErrorRecordSummary
    occurrences: list[ErrorOccurrenceResponse]


class ActionLogResponse(APIModel):
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


class StatusChangeLogResponse(APIModel):
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
    action_log_id: uuid.UUID | None
    changed_at: datetime
