from datetime import UTC, datetime

import pytest
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.models.enums import AuthenticatedPrincipalType, Permission
from app.modules.access.api import (
    create_session,
    principal_from_session,
    resolve_branch_scope,
    visible_branch_ids,
    visible_workshop_ids,
)
from app.modules.access.contracts import PermissionGrant, Session, WorkshopUser
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner


async def _principal_for_owner(
    db_session: AsyncSession,
    owner: WorkshopUser,
) -> AuthenticatedPrincipal:
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    session = await db_session.get(Session, tokens.session_id)
    assert session is not None
    principal = await principal_from_session(db_session, session, trace_id="trace-authz")
    assert principal is not None
    return principal


async def test_owner_scope_resolves_branch_from_stored_data(db_session: AsyncSession) -> None:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)
    principal = await _principal_for_owner(db_session, owner)

    scope = await resolve_branch_scope(
        db_session,
        principal,
        branch_id=branch.id,
        permission=Permission.MANAGE_ORDERS,
        claimed_workshop_id=workshop.id,
    )

    assert scope.workshop_id == workshop.id
    assert scope.branch_id == branch.id
    assert visible_workshop_ids(principal) == frozenset({workshop.id})
    assert visible_branch_ids(principal) == frozenset({branch.id})


async def test_claimed_workshop_spoofing_is_rejected(db_session: AsyncSession) -> None:
    _, branch, owner = await seed_workshop_with_owner(db_session)
    other_workshop, _, _ = await seed_workshop_with_owner(db_session)
    principal = await _principal_for_owner(db_session, owner)

    with pytest.raises(APIError) as exc_info:
        await resolve_branch_scope(
            db_session,
            principal,
            branch_id=branch.id,
            permission=Permission.MANAGE_ORDERS,
            claimed_workshop_id=other_workshop.id,
        )

    assert exc_info.value.code == "scope_mismatch"


async def test_staff_needs_branch_permission_grant(db_session: AsyncSession) -> None:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)
    staff = WorkshopUser(
        workshop_id=workshop.id,
        login="staff-authz",
        password_hash=owner.password_hash,
        full_name="Staff Authz",
        phone="+998905555555",
    )
    db_session.add(staff)
    await db_session.flush()
    principal_without_grant = await _principal_for_owner(db_session, staff)

    with pytest.raises(APIError) as exc_info:
        await resolve_branch_scope(
            db_session,
            principal_without_grant,
            branch_id=branch.id,
            permission=Permission.MANAGE_ORDERS,
        )

    assert exc_info.value.code == "forbidden"

    db_session.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=Permission.MANAGE_ORDERS,
            branch_id=branch.id,
            granted_by_user_id=owner.id,
            granted_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()
    principal_with_grant = await _principal_for_owner(db_session, staff)

    scope = await resolve_branch_scope(
        db_session,
        principal_with_grant,
        branch_id=branch.id,
        permission=Permission.MANAGE_ORDERS,
    )

    assert scope.branch_id == branch.id
    assert visible_branch_ids(principal_with_grant) == frozenset({branch.id})


async def test_cross_workshop_branch_is_forbidden(db_session: AsyncSession) -> None:
    _, _, owner = await seed_workshop_with_owner(db_session)
    _, other_branch, _ = await seed_workshop_with_owner(db_session)
    principal = await _principal_for_owner(db_session, owner)

    with pytest.raises(APIError) as exc_info:
        await resolve_branch_scope(
            db_session,
            principal,
            branch_id=other_branch.id,
            permission=Permission.MANAGE_ORDERS,
        )

    assert exc_info.value.code == "forbidden"
