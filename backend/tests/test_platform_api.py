import uuid

from app.models.catalog import BranchPricing
from app.models.enums import AuthenticatedPrincipalType, WorkshopStatus
from app.models.identity import Client, Session, WorkshopUser
from app.models.support import ActionLog, StatusChangeLog
from app.services.seed import seed_platform_user, seed_workshop_with_owner
from app.services.sessions import create_session
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _platform_access_token(client: AsyncClient, db_session: AsyncSession) -> str:
    await seed_platform_user(
        db_session,
        login="platformer",
        password="Admin123",
        password_reset_required=False,
    )
    response = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "platformer", "password": "Admin123"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _provision_payload(code: str | None = None) -> dict[str, object]:
    return {
        "workshop": {
            "name": "Atlas Mebel",
            "code": code,
            "phone": "+998901010101",
            "address": "Tashkent",
        },
        "branch": {
            "name": "Main",
            "address": "Tashkent, Chilonzor",
            "phone": "+998902020202",
            "latitude": "41.2995",
            "longitude": "69.2401",
            "working_hours": {"mon": {"open": "09:00", "close": "18:00"}},
        },
        "owner": {
            "full_name": "Atlas Owner",
            "login": "owner",
            "phone": "+998903030303",
        },
    }


async def test_platform_can_provision_workshop_owner_and_first_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)

    response = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json=_provision_payload(code="atlas"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["workshop"]["code"] == "atlas"
    assert body["workshop"]["status"] == "active"
    assert body["branch"]["status"] == "active"
    assert body["owner"]["login"] == "owner"
    assert body["owner"]["is_owner"] is True
    assert body["owner"]["home_branch_id"] == body["branch"]["id"]
    assert body["owner"]["password_reset_required"] is True
    assert body["temp_password"]
    branch_pricing_count = await db_session.scalar(select(func.count()).select_from(BranchPricing))
    action_count = await db_session.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(ActionLog.action == "platform.workshop.provision")
    )
    owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": "ATLAS",
            "login": "owner",
            "password": body["temp_password"],
        },
    )
    listed = await client.get("/api/v1/platform/workshops", headers=_auth(access_token))
    detail = await client.get(
        f"/api/v1/platform/workshops/{body['workshop']['id']}",
        headers=_auth(access_token),
    )

    assert branch_pricing_count == 1
    assert action_count == 1
    assert owner_login.status_code == 200
    assert owner_login.json()["me"]["workshop_id"] == body["workshop"]["id"]
    assert owner_login.json()["me"]["password_reset_required"] is True
    assert listed.status_code == 200
    assert [row["code"] for row in listed.json()] == ["atlas"]
    assert detail.status_code == 200
    assert detail.json()["owner"]["login"] == "owner"


async def test_block_and_unblock_workshop_revoke_staff_sessions_but_not_client_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)
    provisioned = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={**_provision_payload(code="blockable"), "temp_password": "OwnerTemp123"},
    )
    assert provisioned.status_code == 201
    workshop_id = provisioned.json()["workshop"]["id"]
    workshop_uuid = uuid.UUID(workshop_id)
    owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": "blockable",
            "login": "owner",
            "password": "OwnerTemp123",
        },
    )
    owner_access = owner_login.json()["access_token"]
    client_row = Client(phone="+998904040404", name="Client User")
    db_session.add(client_row)
    await db_session.flush()
    client_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client_row.id,
    )

    block = await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/block",
        headers=_auth(access_token),
        json={"reason": "Contract paused"},
    )
    blocked_owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": "blockable",
            "login": "owner",
            "password": "OwnerTemp123",
        },
    )
    client_me = await client.get("/api/v1/auth/me", headers=_auth(client_tokens.access_token))
    unblock = await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/unblock",
        headers=_auth(access_token),
    )
    unblocked_owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": "blockable",
            "login": "owner",
            "password": "OwnerTemp123",
        },
    )
    status_logs = (
        await db_session.scalars(
            select(StatusChangeLog).where(StatusChangeLog.entity_id == workshop_uuid)
        )
    ).all()
    remaining_owner_sessions = await db_session.scalar(
        select(func.count())
        .select_from(Session)
        .join(WorkshopUser, WorkshopUser.id == Session.principal_id)
        .where(WorkshopUser.workshop_id == workshop_uuid)
    )

    assert block.status_code == 200
    assert block.json()["status"] == WorkshopStatus.BLOCKED.value
    assert (await client.get("/api/v1/auth/me", headers=_auth(owner_access))).status_code == 401
    assert blocked_owner_login.status_code == 403
    assert blocked_owner_login.json()["code"] == "account_blocked"
    assert client_me.status_code == 200
    assert unblock.status_code == 200
    assert unblock.json()["status"] == WorkshopStatus.ACTIVE.value
    assert unblocked_owner_login.status_code == 200
    assert [(row.from_status, row.to_status) for row in status_logs] == [
        ("active", "blocked"),
        ("blocked", "active"),
    ]
    assert remaining_owner_sessions == 1


async def test_platform_routes_reject_non_platform_principals(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )

    response = await client.get("/api/v1/platform/workshops", headers=_auth(tokens.access_token))

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
