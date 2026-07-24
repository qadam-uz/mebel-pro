"""Workshop owner/staff API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import BranchStatus, Currency, Permission, UserStatus, WorkshopStatus
from app.modules.access.schemas import PermissionGrantResponse, SessionResponse
from app.schemas.common import APIModel

WEEKDAYS = frozenset(
    {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }
)


class WorkingHoursDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open: str | None = None
    close: str | None = None

    @model_validator(mode="after")
    def validate_day(self) -> "WorkingHoursDay":
        if self.open is None and self.close is None:
            return self
        if self.open is None or self.close is None:
            raise ValueError("open and close must both be set or both be null")
        open_minutes = _time_minutes(self.open)
        close_minutes = _time_minutes(self.close)
        if open_minutes >= close_minutes:
            raise ValueError("open must be before close")
        return self


WorkingHours = dict[str, WorkingHoursDay]


def validate_working_hours(value: WorkingHours) -> WorkingHours:
    keys = set(value)
    if keys != WEEKDAYS:
        raise ValueError("working_hours must include every weekday")
    return value


def dump_working_hours(value: WorkingHours) -> dict[str, dict[str, str | None]]:
    return {weekday: hours.model_dump() for weekday, hours in value.items()}


def _time_minutes(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("time must use HH:MM")
    hours = int(parts[0])
    minutes = int(parts[1])
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        raise ValueError("time must use HH:MM")
    return hours * 60 + minutes


class BranchContextItem(APIModel):
    id: uuid.UUID
    name: str
    address: str
    phone: str
    status: BranchStatus
    closed_reason: str | None
    permissions: list[Permission] = Field(default_factory=list)


class BranchContextResponse(APIModel):
    branches: list[BranchContextItem]


class WorkshopSettingsResponse(APIModel):
    id: uuid.UUID
    name: str
    logo_file_id: uuid.UUID | None
    status: WorkshopStatus
    currency: Currency
    owner_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class WorkshopSettingsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    logo_file_id: uuid.UUID | None = None


class BranchCreateRequest(BaseModel):
    name: str
    address: str
    phone: str
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    working_hours: WorkingHours

    @field_validator("working_hours")
    @classmethod
    def _validate_working_hours(cls, value: WorkingHours) -> WorkingHours:
        return validate_working_hours(value)


class BranchPatchRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    working_hours: WorkingHours | None = None

    @field_validator("working_hours")
    @classmethod
    def _validate_working_hours(cls, value: WorkingHours | None) -> WorkingHours | None:
        if value is None:
            return None
        return validate_working_hours(value)


class BranchStatusRequest(BaseModel):
    status: BranchStatus
    reason: str | None = None


class BranchResponse(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    name: str
    address: str
    phone: str
    latitude: Decimal | None
    longitude: Decimal | None
    working_hours: dict[str, Any]
    status: BranchStatus
    closed_reason: str | None
    created_at: datetime
    updated_at: datetime


class BranchPricingResponse(APIModel):
    branch_id: uuid.UUID
    cutting_rate_tiyin: int | None
    edge_banding_rate_tiyin: int | None
    updated_at: datetime | None
    updated_by_user_id: uuid.UUID | None


class BranchPricingPutRequest(BaseModel):
    cutting_rate_tiyin: int | None = None
    edge_banding_rate_tiyin: int | None = None


class WorkshopOnboardingResponse(APIModel):
    branch_configured: bool
    materials_added: bool
    setup_complete: bool
    first_branch_id: uuid.UUID | None


class GrantInput(BaseModel):
    permission: Permission
    branch_id: uuid.UUID


class WorkshopUserCreateRequest(BaseModel):
    full_name: str
    phone: str
    login: str
    home_branch_id: uuid.UUID
    grants: list[GrantInput] = Field(default_factory=list)
    temp_password: str | None = None


class WorkshopUserPatchRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    login: str | None = None
    home_branch_id: uuid.UUID | None = None


class GrantReplacementRequest(BaseModel):
    grants: list[GrantInput] = Field(default_factory=list)


class BlockWorkshopUserRequest(BaseModel):
    reason: str


class WorkshopUserResponse(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    login: str
    full_name: str
    phone: str
    is_owner: bool
    home_branch_id: uuid.UUID
    status: UserStatus
    password_reset_required: bool
    created_at: datetime
    last_login_at: datetime | None
    grants: list[PermissionGrantResponse] = Field(default_factory=list)


class WorkshopUserCreateResponse(APIModel):
    user: WorkshopUserResponse
    temp_password: str


class TempPasswordResponse(APIModel):
    user: WorkshopUserResponse
    temp_password: str


class WorkshopUserSessionsResponse(APIModel):
    sessions: list[SessionResponse]
