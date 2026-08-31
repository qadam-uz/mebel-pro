"""Authentication and session API schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import (
    AuthenticatedPrincipalType,
    Permission,
    TelegramLoginTokenStatus,
    UserStatus,
)
from app.schemas.common import APIModel


class PlatformLoginRequest(BaseModel):
    login: str
    password: str


class WorkshopLoginRequest(BaseModel):
    login: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class TelegramLoginTokenResponse(APIModel):
    """The two halves of a handshake.

    `token` is public — it rides in the QR. `poll_secret` is the browser's alone
    and is the only credential a session is released against.
    """

    token: str
    poll_secret: str
    deep_link: str
    expires_at: datetime


class TelegramLoginPollRequest(BaseModel):
    poll_secret: str


class TelegramLoginPollResponse(APIModel):
    """The non-terminal answer: the page renders progress, then polls again."""

    status: TelegramLoginTokenStatus
    expired: bool = False


class TelegramLoginCodeRequest(BaseModel):
    code: str


class TelegramLoginDevConfirmRequest(BaseModel):
    """Dev-only: confirm a token as `phone`, skipping Telegram (E2E drives this)."""

    phone: str
    name: str | None = Field(default=None, max_length=80)
    token: str | None = None


class WorkshopClientResolveRequest(BaseModel):
    phone: str
    name: str | None = Field(default=None, max_length=80)


class WorkshopClientResolveResponse(APIModel):
    id: uuid.UUID
    name: str
    phone: str
    created: bool


class WorkshopClientLookupResponse(APIModel):
    """Read-only answer to "is this phone already a client?".

    `found=False` carries the normalized phone and nothing else — a miss must
    not be distinguishable from a hit by anything except this flag, and it must
    never leak a partial name.
    """

    found: bool
    phone: str
    id: uuid.UUID | None = None
    name: str | None = None


class WorkshopClientResponse(APIModel):
    id: uuid.UUID
    name: str
    phone: str


class PermissionGrantResponse(APIModel):
    permission: Permission
    branch_id: uuid.UUID


class MeResponse(APIModel):
    principal_type: AuthenticatedPrincipalType
    principal_id: uuid.UUID
    session_id: uuid.UUID
    password_reset_required: bool = False
    workshop_id: uuid.UUID | None = None
    # The tenant's display name, carried on the principal so every workshop user
    # can render it — `/workshop/settings`, the only other source, is owner-only
    # and staff took a 403 asking for it (QAD-168).
    workshop_name: str | None = None
    is_owner: bool = False
    grants: list[PermissionGrantResponse] = Field(default_factory=list)
    login: str | None = None
    full_name: str | None = None
    phone: str | None = None
    name: str | None = None
    preferred_branch_id: uuid.UUID | None = None
    # The pinned context, resolved off `preferred_branch_id` so the client
    # home's header can name it without a second request. Both are null when
    # nothing is pinned (and when the pin points into a blocked workshop) —
    # the subtitle then stays as it was.
    pinned_workshop_name: str | None = None
    pinned_branch_name: str | None = None
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
