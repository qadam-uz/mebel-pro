"""Reusable FastAPI dependencies.

Use the ``Session`` annotated alias in route signatures::

    @router.get("/things")
    async def list_things(db: Session) -> list[Thing]: ...
"""

import uuid
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, PermissionGrantKey
from app.core.trace import get_trace_id
from app.models.enums import Permission
from app.services.sessions import (
    get_session_by_access_token,
    principal_from_session,
    revoke_session,
)

Session = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


async def get_current_principal(
    db: Session,
    credentials: BearerCredentials,
) -> AuthenticatedPrincipal:
    if credentials is None:
        raise APIError(
            "missing_access_token",
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    session = await get_session_by_access_token(db, credentials.credentials)
    if session is None:
        raise APIError(
            "invalid_access_token",
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    principal = await principal_from_session(db, session, trace_id=get_trace_id())
    if principal is None:
        await revoke_session(db, session.id)
        raise APIError(
            "invalid_access_token",
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return principal


Principal = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]


async def get_account_ready_principal(principal: Principal) -> AuthenticatedPrincipal:
    if principal.password_reset_required:
        raise APIError(
            "password_reset_required",
            "Password change required",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return principal


AccountReadyPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(get_account_ready_principal),
]


def has_permission(
    principal: AuthenticatedPrincipal,
    permission: Permission,
    branch_id: uuid.UUID,
) -> bool:
    return PermissionGrantKey(permission=permission, branch_id=branch_id) in principal.grants
