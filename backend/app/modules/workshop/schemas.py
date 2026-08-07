"""Workshop owner/staff API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BranchStatus, Currency, Permission, UserStatus, WorkshopStatus
from app.modules.access.schemas import PermissionGrantResponse, SessionResponse
from app.schemas.common import APIModel


class BranchContextItem(APIModel):
    id: uuid.UUID
    name: str
    address: str
    phone: str
    status: BranchStatus
    closed_reason: str | None
    kerf_mm: int
    edge_trim_mm: int
    edge_overhang_mm: int
    own_material_allowed: bool
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
    additional_phones: list[str] = Field(default_factory=list)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    # Physical shop-floor properties (cutting.md); platform defaults when omitted.
    kerf_mm: int = Field(default=4, ge=1, le=20)
    edge_trim_mm: int = Field(default=5, ge=0, le=50)
    edge_overhang_mm: int = Field(default=30, ge=0, le=100)
    # Off unless asked for — a branch opts in to client-supplied sheets.
    own_material_allowed: bool = False


class BranchPatchRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    additional_phones: list[str] | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    kerf_mm: int | None = Field(default=None, ge=1, le=20)
    edge_trim_mm: int | None = Field(default=None, ge=0, le=50)
    edge_overhang_mm: int | None = Field(default=None, ge=0, le=100)
    own_material_allowed: bool | None = None


class BranchStatusRequest(BaseModel):
    status: BranchStatus
    reason: str | None = None


class BranchResponse(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    # Read-only: assigned once at creation, never patchable (workshop.md).
    branch_no: int
    name: str
    address: str
    phone: str
    additional_phones: list[str]
    latitude: Decimal | None
    longitude: Decimal | None
    status: BranchStatus
    closed_reason: str | None
    kerf_mm: int
    edge_trim_mm: int
    edge_overhang_mm: int
    own_material_allowed: bool
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
