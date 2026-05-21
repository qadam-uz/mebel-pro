"""User-management schemas — platform users, workshop staff, grants."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Permission, UserStatus
from app.schemas.common import APIModel


class PlatformUserOut(APIModel):
    id: uuid.UUID
    login: str
    full_name: str
    phone: str
    status: UserStatus
    force_password_change: bool
    last_login_at: datetime | None = None
    created_at: datetime


class PlatformUserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    login: str = Field(min_length=3, max_length=64)
    phone: str = Field(min_length=1, max_length=20)
    password: str | None = Field(default=None, max_length=128)


class GrantIn(BaseModel):
    permission: Permission
    branch_id: uuid.UUID


class GrantsSet(BaseModel):
    grants: list[GrantIn] = []


class WorkshopUserOut(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    login: str
    full_name: str
    phone: str
    is_owner: bool
    home_branch_id: uuid.UUID | None = None
    status: UserStatus
    force_password_change: bool
    last_login_at: datetime | None = None
    created_at: datetime


class WorkshopUserDetail(WorkshopUserOut):
    grants: list[GrantIn] = Field(default_factory=list)


class WorkshopUserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    login: str = Field(min_length=3, max_length=64)
    phone: str = Field(min_length=1, max_length=20)
    home_branch_id: uuid.UUID | None = None
    grants: list[GrantIn] = []
    password: str | None = Field(default=None, max_length=128)


class WorkshopUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    home_branch_id: uuid.UUID | None = None
    # distinguishes "set home branch to null" from "leave unchanged"
    home_branch_set: bool = False


class CreatedSecretResponse(BaseModel):
    """One-time secret confirmation — login + temp password, shown once."""

    id: uuid.UUID
    login: str
    temp_password: str
