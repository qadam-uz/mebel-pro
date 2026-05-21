"""Auth request/response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Permission, PrincipalType
from app.schemas.common import APIModel


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TelegramLoginRequest(BaseModel):
    """The Telegram Login Widget payload (extra fields are allowed/forwarded)."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    phone_number: str | None = None
    auth_date: int | None = None
    hash: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105  # not a secret — OAuth token type label


class ClientTokenResponse(TokenResponse):
    is_new: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105  # not a secret — OAuth token type label


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class GrantOut(BaseModel):
    permission: Permission
    branch_id: uuid.UUID


class MeResponse(BaseModel):
    principal_type: PrincipalType
    id: uuid.UUID
    full_name: str | None = None
    phone: str | None = None
    force_password_change: bool = False
    # workshop-user fields
    workshop_id: uuid.UUID | None = None
    is_owner: bool = False
    home_branch_id: uuid.UUID | None = None
    grants: list[GrantOut] = Field(default_factory=list)
    # client fields
    first_name: str | None = None
    photo_url: str | None = None


class SessionInfo(APIModel):
    id: uuid.UUID
    device_info: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    last_used_at: datetime
    current: bool = False
