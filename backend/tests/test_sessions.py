from datetime import UTC, datetime, timedelta

from app.models.enums import AuthenticatedPrincipalType, Permission, UserStatus
from app.models.identity import Session, WorkshopUser
from app.services.seed import seed_workshop_with_owner
from app.services.sessions import (
    MAX_SESSIONS_PER_PRINCIPAL,
    create_session,
    get_session_by_access_token,
    principal_from_session,
    refresh_session,
    revoke_for_workshop,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_session_access_token_resolves_active_workshop_principal(
    db_session: AsyncSession,
) -> None:
    _, branch, owner = await seed_workshop_with_owner(db_session)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )

    row = await get_session_by_access_token(
        db_session,
        tokens.access_token,
        now=datetime(2026, 1, 1, 1, tzinfo=UTC),
    )

    assert row is not None
    principal = await principal_from_session(db_session, row, trace_id="trace-1")
    assert principal is not None
    assert principal.principal_id == owner.id
    assert principal.workshop_id == owner.workshop_id
    assert principal.is_owner
    assert any(
        grant.permission is Permission.MANAGE_ORDERS and grant.branch_id == branch.id
        for grant in principal.grants
    )


async def test_expired_access_token_is_not_accepted(db_session: AsyncSession) -> None:
    _, _, owner = await seed_workshop_with_owner(db_session)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )

    row = await get_session_by_access_token(
        db_session,
        tokens.access_token,
        now=tokens.access_token_expires_at + timedelta(seconds=1),
    )

    assert row is None


async def test_refresh_rejects_inactive_principal_and_revokes_session(
    db_session: AsyncSession,
) -> None:
    _, _, owner = await seed_workshop_with_owner(db_session)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    owner.status = UserStatus.BLOCKED

    refreshed = await refresh_session(db_session, tokens.refresh_token)

    assert refreshed is None
    remaining = await db_session.scalar(select(func.count()).select_from(Session))
    assert remaining == 0


async def test_session_cap_keeps_latest_five_sessions(db_session: AsyncSession) -> None:
    _, _, owner = await seed_workshop_with_owner(db_session)
    created_ids = []
    for offset in range(MAX_SESSIONS_PER_PRINCIPAL + 1):
        tokens = await create_session(
            db_session,
            principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
            principal_id=owner.id,
            now=datetime(2026, 1, 1, offset, tzinfo=UTC),
        )
        created_ids.append(tokens.session_id)

    rows = (await db_session.scalars(select(Session).order_by(Session.created_at))).all()

    assert len(rows) == MAX_SESSIONS_PER_PRINCIPAL
    assert created_ids[0] not in {row.id for row in rows}


async def test_workshop_session_revocation_deletes_all_workshop_user_sessions(
    db_session: AsyncSession,
) -> None:
    workshop, _, owner = await seed_workshop_with_owner(db_session)
    staff = WorkshopUser(
        workshop_id=workshop.id,
        login="staff",
        password_hash=owner.password_hash,
        full_name="Staff",
        phone="+998904444444",
    )
    db_session.add(staff)
    await db_session.flush()
    await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=staff.id,
    )

    await revoke_for_workshop(db_session, workshop.id)

    remaining = await db_session.scalar(select(func.count()).select_from(Session))
    assert remaining == 0
