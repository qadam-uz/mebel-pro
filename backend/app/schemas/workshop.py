"""Workshop administration schemas — provisioning, profile, branches."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import BranchStatus, WorkshopStatus
from app.schemas.common import APIModel

# --- workshop provisioning / admin -----------------------------------------


class WorkshopProvision(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    phone: str = Field(min_length=1, max_length=20)
    address: str | None = Field(default=None, max_length=400)
    logo_file_id: uuid.UUID | None = None
    owner_full_name: str = Field(min_length=1, max_length=120)
    owner_login: str = Field(min_length=3, max_length=64)
    owner_phone: str = Field(min_length=1, max_length=20)
    owner_password: str | None = Field(default=None, max_length=128)


class WorkshopProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=400)
    logo_file_id: uuid.UUID | None = None
    logo_file_id_set: bool = False


class WorkshopBlock(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class WorkshopOut(APIModel):
    id: uuid.UUID
    name: str
    phone: str
    address: str | None = None
    logo_file_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    status: WorkshopStatus
    created_at: datetime
    updated_at: datetime


class WorkshopSummary(WorkshopOut):
    """List/detail row enriched with owner + counts."""

    owner_name: str | None = None
    owner_phone: str | None = None
    branches_count: int = 0
    orders_30d_count: int = 0


class WorkshopProvisionResult(BaseModel):
    """One-time secret confirmation — the workshop plus the owner's temp password."""

    workshop: WorkshopOut
    owner_id: uuid.UUID
    owner_login: str
    temp_password: str


# --- branches ---------------------------------------------------------------


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    address: str = Field(min_length=1, max_length=400)
    phone: str = Field(min_length=1, max_length=20)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    working_hours: dict[str, Any] = Field(default_factory=dict)


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=400)
    phone: str | None = Field(default=None, max_length=20)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude_set: bool = False
    longitude_set: bool = False
    working_hours: dict[str, Any] | None = None


class BranchStatusChange(BaseModel):
    status: BranchStatus
    closed_reason: str | None = Field(default=None, max_length=300)


class BranchOut(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    name: str
    address: str
    phone: str
    latitude: float | None = None
    longitude: float | None = None
    working_hours: dict[str, Any] = Field(default_factory=dict)
    status: BranchStatus
    closed_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class BranchSummary(BranchOut):
    materials_count: int = 0
    low_stock_count: int = 0
    active_orders_count: int = 0
