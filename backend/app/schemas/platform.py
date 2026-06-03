"""Platform operations API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import BranchStatus, Currency, UserStatus, WorkshopStatus
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
    working_hours: dict[str, Any] = Field(default_factory=dict)


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
