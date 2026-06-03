"""Workshop owner/staff API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import BranchStatus, Permission, UserStatus
from app.schemas.auth import PermissionGrantResponse, SessionResponse
from app.schemas.common import APIModel


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


class GrantInput(BaseModel):
    permission: Permission
    branch_id: uuid.UUID


class WorkshopUserCreateRequest(BaseModel):
    full_name: str
    phone: str
    login: str
    home_branch_id: uuid.UUID | None = None
    grants: list[GrantInput] = Field(default_factory=list)
    temp_password: str | None = None


class WorkshopUserPatchRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
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
    home_branch_id: uuid.UUID | None
    status: UserStatus
    password_reset_required: bool
    created_at: datetime
    grants: list[PermissionGrantResponse] = Field(default_factory=list)


class WorkshopUserCreateResponse(APIModel):
    user: WorkshopUserResponse
    temp_password: str


class TempPasswordResponse(APIModel):
    user: WorkshopUserResponse
    temp_password: str


class WorkshopUserSessionsResponse(APIModel):
    sessions: list[SessionResponse]
