"""Session lifecycle — opaque DB-backed tokens with instant revocation.

Access TTL 24 h, refresh TTL 7 d, ≤ 5 concurrent sessions per principal (a 6th
login evicts the oldest). Revoking is deleting the row
(docs/ref/features/access-management.md → Sessions).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.core.security import generate_token, hash_token
from app.models.enums import PrincipalType, UserStatus
from app.models.identity import (
    Client,
    PermissionGrant,
    PlatformUser,
    Session,
    WorkshopUser,
)
from app.models.workshop import Workshop

ACCESS_TTL = timedelta(hours=24)
REFRESH_TTL = timedelta(days=7)
MAX_SESSIONS = 5


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    session: Session


def _now() -> datetime:
    return datetime.now(UTC)


async def create_session(
    db: AsyncSession,
    principal_type: PrincipalType,
    principal_id: uuid.UUID,
    device_info: dict[str, Any] | None = None,
) -> IssuedTokens:
    """Mint a session, enforcing the 5-session cap (oldest evicted)."""
    await _enforce_session_cap(db, principal_type, principal_id)
    access_token = generate_token()
    refresh_token = generate_token()
    now = _now()
    session = Session(
        principal_type=principal_type,
        principal_id=principal_id,
        access_token_hash=hash_token(access_token),
        refresh_token_hash=hash_token(refresh_token),
        access_token_expires_at=now + ACCESS_TTL,
        refresh_token_expires_at=now + REFRESH_TTL,
        device_info=device_info or {},
        created_at=now,
        last_used_at=now,
    )
    db.add(session)
    await db.flush()
    return IssuedTokens(access_token, refresh_token, session)


async def _enforce_session_cap(
    db: AsyncSession, principal_type: PrincipalType, principal_id: uuid.UUID
) -> None:
    rows = (
        (
            await db.execute(
                select(Session)
                .where(
                    Session.principal_type == principal_type,
                    Session.principal_id == principal_id,
                )
                .order_by(Session.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    excess = len(rows) - (MAX_SESSIONS - 1)
    for old in rows[: max(0, excess)]:
        await db.delete(old)


async def get_session_by_access_token(db: AsyncSession, token: str) -> Session | None:
    return (
        await db.execute(select(Session).where(Session.access_token_hash == hash_token(token)))
    ).scalar_one_or_none()


async def get_session_by_refresh_token(db: AsyncSession, token: str) -> Session | None:
    return (
        await db.execute(select(Session).where(Session.refresh_token_hash == hash_token(token)))
    ).scalar_one_or_none()


async def rotate_access_token(db: AsyncSession, session: Session) -> str:
    """Issue a fresh access token on the existing session (refresh path)."""
    access_token = generate_token()
    session.access_token_hash = hash_token(access_token)
    session.access_token_expires_at = _now() + ACCESS_TTL
    session.last_used_at = _now()
    await db.flush()
    return access_token


async def touch(db: AsyncSession, session: Session) -> None:
    session.last_used_at = _now()


async def revoke(db: AsyncSession, session: Session) -> None:
    await db.delete(session)


async def revoke_all(
    db: AsyncSession,
    principal_type: PrincipalType,
    principal_id: uuid.UUID,
    *,
    except_session_id: uuid.UUID | None = None,
) -> None:
    stmt = delete(Session).where(
        Session.principal_type == principal_type,
        Session.principal_id == principal_id,
    )
    if except_session_id is not None:
        stmt = stmt.where(Session.id != except_session_id)
    await db.execute(stmt)


async def revoke_workshop_sessions(db: AsyncSession, workshop_id: uuid.UUID) -> None:
    """Block-cascade: drop every workshop user's session for this workshop."""
    user_ids = (
        (await db.execute(select(WorkshopUser.id).where(WorkshopUser.workshop_id == workshop_id)))
        .scalars()
        .all()
    )
    if not user_ids:
        return
    await db.execute(
        delete(Session).where(
            Session.principal_type == PrincipalType.WORKSHOP_USER,
            Session.principal_id.in_(user_ids),
        )
    )


async def prune_expired(db: AsyncSession) -> int:
    """Delete sessions past refresh expiry; returns the count removed."""
    result = await db.execute(delete(Session).where(Session.refresh_token_expires_at < _now()))
    return int(getattr(result, "rowcount", 0) or 0)


async def count_active(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(Session))).scalar_one()


async def load_principal(db: AsyncSession, session: Session) -> Principal | None:
    """Resolve a session into a full principal context (or None if not loadable)."""
    if session.principal_type is PrincipalType.PLATFORM_USER:
        pu = await db.get(PlatformUser, session.principal_id)
        if pu is None:
            return None
        return Principal(
            type=PrincipalType.PLATFORM_USER,
            id=pu.id,
            session_id=session.id,
            status=pu.status,
            force_password_change=pu.force_password_change,
        )

    if session.principal_type is PrincipalType.WORKSHOP_USER:
        wu = await db.get(WorkshopUser, session.principal_id)
        if wu is None:
            return None
        grants: frozenset[tuple[Any, uuid.UUID]] = frozenset()
        if not wu.is_owner:
            grant_rows = (
                await db.execute(
                    select(PermissionGrant.permission, PermissionGrant.branch_id).where(
                        PermissionGrant.workshop_user_id == wu.id
                    )
                )
            ).all()
            grants = frozenset((p, b) for (p, b) in grant_rows)
        return Principal(
            type=PrincipalType.WORKSHOP_USER,
            id=wu.id,
            session_id=session.id,
            status=wu.status,
            force_password_change=wu.force_password_change,
            workshop_id=wu.workshop_id,
            is_owner=wu.is_owner,
            grants=grants,
        )

    client = await db.get(Client, session.principal_id)
    if client is None:
        return None
    return Principal(
        type=PrincipalType.CLIENT,
        id=client.id,
        session_id=session.id,
        status=client.status,
    )


async def principal_is_active(db: AsyncSession, session: Session) -> bool:
    """Re-check the principal (and workshop, for workshop users) is still active."""
    if session.principal_type is PrincipalType.PLATFORM_USER:
        user = await db.get(PlatformUser, session.principal_id)
        return user is not None and user.status is UserStatus.ACTIVE
    if session.principal_type is PrincipalType.WORKSHOP_USER:
        wu = await db.get(WorkshopUser, session.principal_id)
        if wu is None or wu.status is not UserStatus.ACTIVE:
            return False
        ws = await db.get(Workshop, wu.workshop_id)
        return ws is not None and ws.status.value == "active"
    client = await db.get(Client, session.principal_id)
    return client is not None and client.status is UserStatus.ACTIVE
