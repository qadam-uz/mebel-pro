"""Authentication and session API schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import AuthenticatedPrincipalType, Permission, UserStatus
from app.schemas.common import APIModel


class PlatformLoginRequest(BaseModel):
    login: str
    password: str


class WorkshopLoginRequest(BaseModel):
    workshop_code: str
    login: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class ClientOtpRequest(BaseModel):
    phone: str


class ClientOtpRequestResponse(APIModel):
    phone: str
    expires_at: datetime
    resend_after_seconds: int


class ClientOtpVerifyRequest(BaseModel):
    phone: str
    code: str
    name: str | None = None


class ClientOtpRegistrationRequiredResponse(APIModel):
    is_new: Literal[True] = True


class PermissionGrantResponse(APIModel):
    permission: Permission
    branch_id: uuid.UUID


class MeResponse(APIModel):
    principal_type: AuthenticatedPrincipalType
    principal_id: uuid.UUID
    session_id: uuid.UUID
    password_reset_required: bool = False
    workshop_id: uuid.UUID | None = None
    is_owner: bool = False
    grants: list[PermissionGrantResponse] = Field(default_factory=list)
    login: str | None = None
    full_name: str | None = None
    phone: str | None = None
    name: str | None = None
    preferred_branch_id: uuid.UUID | None = None
    status: UserStatus | None = None


class TokenResponse(APIModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type literal.
    access_token_expires_at: datetime
    me: MeResponse


class SessionResponse(APIModel):
    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    device_info: dict[str, Any]
    is_current: bool
