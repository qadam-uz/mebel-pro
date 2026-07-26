"""Workshop walk-in client resolve/lookup API tests."""

import uuid
from datetime import UTC, datetime

from app.core.security import hash_password
from app.models.enums import (
    ActorType,
    AuthenticatedPrincipalType,
    Permission,
    UserStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.access.workshop_clients import (
    CLIENT_RESOLVE_ACTION,
    CLIENT_RESOLVES_PER_STAFF_PER_HOUR,
)
from app.modules.cutting.contracts import CuttingDraft
from app.modules.sales.contracts import Order
from app.modules.support.contracts import ActionLog
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner

RESOLVE_URL = "/api/v1/workshop/clients/resolve"


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _workshop_owner_access(
    db: AsyncSession,
    *,
    login: str = "owner",
) -> tuple[str, uuid.UUID, uuid.UUID, uuid.UUID]:
    workshop, branch, owner = await seed_workshop_with_owner(db, login=login)
    owner.password_reset_required = False
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, workshop.id, branch.id, owner.id


async def _staff_user_access(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    permission: Permission,
) -> tuple[str, WorkshopUser]:
    staff = WorkshopUser(
        workshop_id=workshop_id,
        login=f"staff-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("StaffTemp123"),
        full_name="Scoped Staff",
        phone="+998901234222",
        is_owner=False,
        home_branch_id=branch_id,
        status=UserStatus.ACTIVE,
        password_reset_required=False,
    )
    db.add(staff)
    await db.flush()
    db.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=permission,
            branch_id=branch_id,
            granted_by_user_id=staff.id,
            granted_at=datetime.now(UTC),
        )
    )
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=staff.id,
    )
    return tokens.access_token, staff


async def _client_access(db: AsyncSession, *, phone: str = "+998901111000") -> tuple[str, Client]:
    client = Client(phone=phone, name="Client")
    db.add(client)
    await db.flush()
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client.id,
    )
    return tokens.access_token, client


async def _platform_access(db: AsyncSession) -> str:
    admin = await seed_platform_user(db, password_reset_required=False)
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=admin.id,
    )
    return tokens.access_token


def _seed_resolve_audit_rows(
    db: AsyncSession,
    *,
    staff_user_id: uuid.UUID,
    count: int,
) -> None:
    now = datetime.now(UTC)
    for _ in range(count):
        db.add(
            ActionLog(
                actor_type=ActorType.WORKSHOP_USER,
                actor_user_id=staff_user_id,
                action=CLIENT_RESOLVE_ACTION,
                entity_type="client",
                trace_id="test-trace",
                created_at=now,
            )
        )


async def test_resolve_creates_then_finds_and_audits_every_call(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, workshop_id, _, owner_id = await _workshop_owner_access(db_session)

    created = await client.post(
        RESOLVE_URL,
        headers=_auth(access),
        json={"phone": " +998901111333 ", "name": "  Walk  In "},
    )
    found = await client.post(
        RESOLVE_URL,
        headers=_auth(access),
        json={"phone": "+998901111333"},
    )
    audit_rows = (
        (
            await db_session.execute(
                select(ActionLog)
                .where(
                    ActionLog.action == CLIENT_RESOLVE_ACTION,
                    ActionLog.actor_user_id == owner_id,
                )
                .order_by(ActionLog.created_at)
            )
        )
        .scalars()
        .all()
    )

    assert created.status_code == 200
    assert created.json()["created"] is True
    assert created.json()["phone"] == "+998901111333"
    assert created.json()["name"] == "Walk In"
    assert found.status_code == 200
    assert found.json()["created"] is False
    assert found.json()["id"] == created.json()["id"]
    assert found.json()["name"] == "Walk In"
    row = await db_session.scalar(select(Client).where(Client.phone == "+998901111333"))
    assert row is not None and str(row.id) == created.json()["id"]
    assert len(audit_rows) == 2
    assert audit_rows[0].workshop_id == workshop_id
    assert audit_rows[0].details == {
        "phone": "+998901111333",
        "created": True,
        "outcome": "created",
    }
    assert audit_rows[1].details == {
        "phone": "+998901111333",
        "created": False,
        "outcome": "found",
    }


async def test_resolve_requires_name_only_when_creating(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, _, _ = await _workshop_owner_access(db_session)

    missing = await client.post(
        RESOLVE_URL,
        headers=_auth(access),
        json={"phone": "+998901111444"},
    )
    blank = await client.post(
        RESOLVE_URL,
        headers=_auth(access),
        json={"phone": "+998901111444", "name": "   "},
    )
    bad_phone = await client.post(
        RESOLVE_URL,
        headers=_auth(access),
        json={"phone": "998901111444", "name": "Walk In"},
    )

    assert missing.status_code == 400
    assert missing.json()["code"] == "client_name_required"
    assert blank.status_code == 400
    assert blank.json()["code"] == "client_name_required"
    assert bad_phone.status_code == 400
    assert bad_phone.json()["code"] == "invalid_phone"
    assert await db_session.scalar(select(Client).where(Client.phone == "+998901111444")) is None


async def test_resolve_blocked_client_returns_account_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, _, _ = await _workshop_owner_access(db_session)
    blocked = Client(phone="+998901111555", name="Blocked", status=UserStatus.BLOCKED)
    db_session.add(blocked)
    await db_session.flush()

    response = await client.post(
        RESOLVE_URL,
        headers=_auth(access),
        json={"phone": "+998901111555"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "account_blocked"


async def test_resolve_rate_limit_is_per_staff_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, workshop_id, branch_id, owner_id = await _workshop_owner_access(db_session)
    _seed_resolve_audit_rows(
        db_session,
        staff_user_id=owner_id,
        count=CLIENT_RESOLVES_PER_STAFF_PER_HOUR - 1,
    )
    await db_session.flush()

    last_allowed = await client.post(
        RESOLVE_URL,
        headers=_auth(access),
        json={"phone": "+998901111666", "name": "Walk In"},
    )
    limited = await client.post(
        RESOLVE_URL,
        headers=_auth(access),
        json={"phone": "+998901111667", "name": "Walk In"},
    )
    other_access, _ = await _staff_user_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_ORDERS,
    )
    other_staff_ok = await client.post(
        RESOLVE_URL,
        headers=_auth(other_access),
        json={"phone": "+998901111668", "name": "Walk In"},
    )

    assert last_allowed.status_code == 200
    assert limited.status_code == 429
    assert limited.json()["code"] == "client_resolve_rate_limited"
    assert limited.json()["details"]["retry_after_seconds"] >= 1
    assert other_staff_ok.status_code == 200


async def test_workshop_client_endpoints_reject_wrong_principals(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, workshop_id, branch_id, _ = await _workshop_owner_access(db_session)
    production_access, _ = await _staff_user_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.PROCESS_PRODUCTION,
    )
    client_access, client_row = await _client_access(db_session)
    platform_access = await _platform_access(db_session)
    payload = {"phone": "+998901111777", "name": "Walk In"}

    production_resolve = await client.post(
        RESOLVE_URL, headers=_auth(production_access), json=payload
    )
    client_resolve = await client.post(RESOLVE_URL, headers=_auth(client_access), json=payload)
    platform_resolve = await client.post(RESOLVE_URL, headers=_auth(platform_access), json=payload)
    production_get = await client.get(
        f"/api/v1/workshop/clients/{client_row.id}",
        headers=_auth(production_access),
    )
    client_get = await client.get(
        f"/api/v1/workshop/clients/{client_row.id}",
        headers=_auth(client_access),
    )
    platform_get = await client.get(
        f"/api/v1/workshop/clients/{client_row.id}",
        headers=_auth(platform_access),
    )

    assert production_resolve.status_code == 403
    assert client_resolve.status_code == 403
    assert platform_resolve.status_code == 403
    assert production_get.status_code == 403
    assert client_get.status_code == 403
    assert platform_get.status_code == 403
    assert await db_session.scalar(select(Client).where(Client.phone == "+998901111777")) is None


async def test_get_workshop_client_requires_a_draft_or_order_with_this_workshop(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, workshop_id, branch_id, _ = await _workshop_owner_access(db_session)
    other_access, other_workshop_id, _, _ = await _workshop_owner_access(
        db_session,
        login="owner_b",
    )

    drafted = Client(phone="+998901111881", name="Drafted Walk In")
    ordered = Client(phone="+998901111882", name="Ordered Walk In")
    untied = Client(phone="+998901111883", name="Untied")
    db_session.add_all([drafted, ordered, untied])
    await db_session.flush()
    db_session.add(
        CuttingDraft(
            client_id=drafted.id,
            created_via_workshop_id=workshop_id,
            parts_snapshot=[],
        )
    )
    db_session.add(
        Order(
            order_number=f"ORD-{uuid.uuid4().hex[:10]}",
            client_id=ordered.id,
            workshop_id=workshop_id,
            branch_id=branch_id,
            cutting_result_id=uuid.uuid4(),
            contact_name="Ordered Walk In",
            contact_phone="+998901111882",
        )
    )
    await db_session.flush()

    drafted_ok = await client.get(
        f"/api/v1/workshop/clients/{drafted.id}",
        headers=_auth(access),
    )
    ordered_ok = await client.get(
        f"/api/v1/workshop/clients/{ordered.id}",
        headers=_auth(access),
    )
    untied_missing = await client.get(
        f"/api/v1/workshop/clients/{untied.id}",
        headers=_auth(access),
    )
    foreign_missing = await client.get(
        f"/api/v1/workshop/clients/{drafted.id}",
        headers=_auth(other_access),
    )
    unknown_missing = await client.get(
        f"/api/v1/workshop/clients/{uuid.uuid4()}",
        headers=_auth(access),
    )

    assert drafted_ok.status_code == 200
    assert drafted_ok.json() == {
        "id": str(drafted.id),
        "name": "Drafted Walk In",
        "phone": "+998901111881",
    }
    assert ordered_ok.status_code == 200
    assert ordered_ok.json()["name"] == "Ordered Walk In"
    assert untied_missing.status_code == 404
    assert untied_missing.json()["code"] == "client_not_found"
    assert foreign_missing.status_code == 404
    assert unknown_missing.status_code == 404
    assert other_workshop_id != workshop_id
