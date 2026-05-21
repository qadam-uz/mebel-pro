"""Reusable FastAPI dependencies — DB session and the auth principal chain.

The auth dependency turns the bearer token into a :class:`Principal` (type,
workshop, owner flag, grant set), re-checks the principal/workshop is active,
and gates everything but change-password / logout / me behind
``force_password_change`` (docs/ref/features/access-management.md).
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AppError, forbidden, unauthorized
from app.core.principal import Principal
from app.models.enums import UserStatus
from app.services import sessions as session_service

Session = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False, description="Opaque session access token")
BearerCreds = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


async def _authenticate(db: AsyncSession, creds: BearerCreds) -> tuple[Principal, object]:
    if creds is None or not creds.credentials:
        raise unauthorized()
    session = await session_service.get_session_by_access_token(db, creds.credentials)
    if session is None:
        raise unauthorized("Invalid or expired token.")
    now = datetime.now(UTC)
    expires = session.access_token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < now:
        raise unauthorized("Invalid or expired token.")
    if not await session_service.principal_is_active(db, session):
        raise unauthorized("Account is not active.", code="account_blocked")
    principal = await session_service.load_principal(db, session)
    if principal is None:
        raise unauthorized()
    await session_service.touch(db, session)
    return principal, session


async def get_principal_allow_pwchange(db: Session, creds: BearerCreds) -> Principal:
    """Authenticated principal WITHOUT the force-password-change gate.

    For the handful of endpoints that must work mid-rotation: me, change
    password, logout, list/revoke sessions.
    """
    principal, _ = await _authenticate(db, creds)
    if principal.status is not UserStatus.ACTIVE:
        raise unauthorized("Account is not active.", code="account_blocked")
    return principal


async def get_current_principal(db: Session, creds: BearerCreds) -> Principal:
    """Authenticated, active principal with the force-password-change gate applied."""
    principal = await get_principal_allow_pwchange(db, creds)
    if principal.force_password_change:
        raise AppError(
            "password_change_required",
            "You must change your password before continuing.",
            status_code=403,
        )
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
PrincipalAllowPwChange = Annotated[Principal, Depends(get_principal_allow_pwchange)]


async def require_platform_user(principal: CurrentPrincipal) -> Principal:
    if not principal.is_platform_user:
        raise forbidden()
    return principal


async def require_workshop_user(principal: CurrentPrincipal) -> Principal:
    if not principal.is_workshop_user:
        raise forbidden()
    return principal


async def require_owner(principal: CurrentPrincipal) -> Principal:
    if not (principal.is_workshop_user and principal.is_owner):
        raise forbidden("This action is owner-only.")
    return principal


async def require_client(principal: CurrentPrincipal) -> Principal:
    if not principal.is_client:
        raise forbidden()
    return principal


CurrentPlatformUser = Annotated[Principal, Depends(require_platform_user)]
CurrentWorkshopUser = Annotated[Principal, Depends(require_workshop_user)]
CurrentOwner = Annotated[Principal, Depends(require_owner)]
CurrentClient = Annotated[Principal, Depends(require_client)]


def device_info_from(request: Request) -> dict[str, str]:
    """UA + client IP for the session record / 'where am I logged in' view."""
    return {
        "user_agent": request.headers.get("user-agent", ""),
        "ip": request.client.host if request.client else "",
    }
