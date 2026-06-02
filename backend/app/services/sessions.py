"""Opaque DB-backed session service primitives."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import AuthenticatedPrincipal, PermissionGrantKey
from app.core.security import generate_token, hash_token
from app.models.enums import (
    AuthenticatedPrincipalType,
    BranchStatus,
    Permission,
    UserStatus,
    WorkshopStatus,
)
from app.models.identity import Client, PermissionGrant, PlatformUser, Session, WorkshopUser
from app.models.workshop import Branch, Workshop

ACCESS_TTL = timedelta(hours=24)
REFRESH_TTL = timedelta(days=7)
MAX_SESSIONS_PER_PRINCIPAL = 5


@dataclass(frozen=True)
class PlainSessionTokens:
    session_id: uuid.UUID
    access_token: str
    refresh_token: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _current_time(now: datetime | None) -> datetime:
    return _coerce_utc(now) if now is not None else datetime.now(UTC)


async def create_session(
    db: AsyncSession,
    *,
    principal_type: AuthenticatedPrincipalType,
    principal_id: uuid.UUID,
    device_info: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> PlainSessionTokens:
    current = _current_time(now)
    access_token = generate_token()
    refresh_token = generate_token()
    row = Session(
        principal_type=principal_type,
        principal_id=principal_id,
        access_token_hash=hash_token(access_token),
        refresh_token_hash=hash_token(refresh_token),
        access_token_expires_at=current + ACCESS_TTL,
        refresh_token_expires_at=current + REFRESH_TTL,
        device_info=device_info or {},
        created_at=current,
        last_used_at=current,
    )
    db.add(row)
    await db.flush()
    await _enforce_session_cap(db, principal_type=principal_type, principal_id=principal_id)
    return PlainSessionTokens(
        session_id=row.id,
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_at=_coerce_utc(row.access_token_expires_at),
        refresh_token_expires_at=_coerce_utc(row.refresh_token_expires_at),
    )


async def get_session_by_access_token(
    db: AsyncSession,
    token: str,
    *,
    now: datetime | None = None,
) -> Session | None:
    current = _current_time(now)
    row = await db.scalar(select(Session).where(Session.access_token_hash == hash_token(token)))
    if row is None or _coerce_utc(row.access_token_expires_at) <= current:
        return None
    row.last_used_at = current
    return row


async def get_session_by_refresh_token(
    db: AsyncSession,
    token: str,
    *,
    now: datetime | None = None,
) -> Session | None:
    current = _current_time(now)
    row = await db.scalar(select(Session).where(Session.refresh_token_hash == hash_token(token)))
    if row is None or _coerce_utc(row.refresh_token_expires_at) <= current:
        return None
    return row


async def principal_from_session(
    db: AsyncSession,
    session: Session,
    *,
    trace_id: str,
) -> AuthenticatedPrincipal | None:
    if session.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        platform_user = await db.get(PlatformUser, session.principal_id)
        if platform_user is None or platform_user.status is not UserStatus.ACTIVE:
            return None
        return AuthenticatedPrincipal(
            principal_type=session.principal_type,
            principal_id=platform_user.id,
            trace_id=trace_id,
        )
    if session.principal_type is AuthenticatedPrincipalType.CLIENT:
        client = await db.get(Client, session.principal_id)
        if client is None or client.status is not UserStatus.ACTIVE:
            return None
        return AuthenticatedPrincipal(
            principal_type=session.principal_type,
            principal_id=client.id,
            trace_id=trace_id,
        )
    workshop_user = await db.get(WorkshopUser, session.principal_id)
    if workshop_user is None or workshop_user.status is not UserStatus.ACTIVE:
        return None
    workshop = await db.get(Workshop, workshop_user.workshop_id)
    if workshop is None or workshop.status is not WorkshopStatus.ACTIVE:
        return None
    grants = await _load_active_grants(db, workshop_user)
    return AuthenticatedPrincipal(
        principal_type=session.principal_type,
        principal_id=workshop_user.id,
        workshop_id=workshop_user.workshop_id,
        is_owner=workshop_user.is_owner,
        grants=grants,
        trace_id=trace_id,
    )


async def refresh_session(
    db: AsyncSession,
    refresh_token: str,
    *,
    now: datetime | None = None,
) -> PlainSessionTokens | None:
    current = _current_time(now)
    row = await get_session_by_refresh_token(db, refresh_token, now=current)
    if row is None:
        return None
    if await principal_from_session(db, row, trace_id="refresh") is None:
        await revoke_session(db, row.id)
        return None
    access_token = generate_token()
    new_refresh = generate_token()
    row.access_token_hash = hash_token(access_token)
    row.refresh_token_hash = hash_token(new_refresh)
    row.access_token_expires_at = current + ACCESS_TTL
    row.refresh_token_expires_at = current + REFRESH_TTL
    row.last_used_at = current
    await db.flush()
    return PlainSessionTokens(
        session_id=row.id,
        access_token=access_token,
        refresh_token=new_refresh,
        access_token_expires_at=_coerce_utc(row.access_token_expires_at),
        refresh_token_expires_at=_coerce_utc(row.refresh_token_expires_at),
    )


async def revoke_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    await db.execute(delete(Session).where(Session.id == session_id))


async def revoke_other_sessions(
    db: AsyncSession,
    *,
    principal_type: AuthenticatedPrincipalType,
    principal_id: uuid.UUID,
    keep_session_id: uuid.UUID,
) -> None:
    await db.execute(
        delete(Session).where(
            Session.principal_type == principal_type,
            Session.principal_id == principal_id,
            Session.id != keep_session_id,
        )
    )


async def revoke_for_principal(
    db: AsyncSession,
    *,
    principal_type: AuthenticatedPrincipalType,
    principal_id: uuid.UUID,
) -> None:
    await db.execute(
        delete(Session).where(
            Session.principal_type == principal_type,
            Session.principal_id == principal_id,
        )
    )


async def revoke_for_workshop(db: AsyncSession, workshop_id: uuid.UUID) -> None:
    user_ids = select(WorkshopUser.id).where(WorkshopUser.workshop_id == workshop_id)
    await db.execute(
        delete(Session).where(
            Session.principal_type == AuthenticatedPrincipalType.WORKSHOP_USER,
            Session.principal_id.in_(user_ids),
        )
    )


async def prune_expired_sessions(db: AsyncSession, *, now: datetime | None = None) -> int:
    current = _current_time(now)
    expired_ids = (
        await db.scalars(select(Session.id).where(Session.refresh_token_expires_at <= current))
    ).all()
    if expired_ids:
        await db.execute(delete(Session).where(Session.id.in_(expired_ids)))
    return len(expired_ids)


async def _enforce_session_cap(
    db: AsyncSession,
    *,
    principal_type: AuthenticatedPrincipalType,
    principal_id: uuid.UUID,
) -> None:
    rows = (
        await db.scalars(
            select(Session)
            .where(Session.principal_type == principal_type, Session.principal_id == principal_id)
            .order_by(Session.created_at.desc())
        )
    ).all()
    for stale in rows[MAX_SESSIONS_PER_PRINCIPAL:]:
        await db.delete(stale)


async def _load_active_grants(
    db: AsyncSession, user: WorkshopUser
) -> frozenset[PermissionGrantKey]:
    if user.is_owner:
        branch_ids = (
            await db.scalars(
                select(Branch.id).where(
                    Branch.workshop_id == user.workshop_id,
                    Branch.status != BranchStatus.INACTIVE,
                )
            )
        ).all()
        return frozenset(
            PermissionGrantKey(permission, branch_id)
            for branch_id in branch_ids
            for permission in Permission
        )
    rows = (
        await db.scalars(
            select(PermissionGrant)
            .join(Branch, Branch.id == PermissionGrant.branch_id)
            .where(
                PermissionGrant.workshop_user_id == user.id,
                Branch.status != BranchStatus.INACTIVE,
            )
        )
    ).all()
    return frozenset(PermissionGrantKey(row.permission, row.branch_id) for row in rows)
