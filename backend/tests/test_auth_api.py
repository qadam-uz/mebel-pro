from http.cookies import SimpleCookie

import pytest
from app.core.security import hash_password
from app.models.enums import UserStatus
from app.modules.access.routes import REFRESH_COOKIE_NAME
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _refresh_cookie(response_headers: str) -> str:
    cookie = SimpleCookie()
    cookie.load(response_headers)
    morsel = cookie[REFRESH_COOKIE_NAME]
    assert morsel["httponly"]
    assert morsel["secure"]
    assert morsel["samesite"].lower() == "lax"
    return morsel.value


async def test_platform_login_sets_refresh_cookie_and_returns_me(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await seed_platform_user(db_session, login="admin-auth", password="Admin123")

    response = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "ADMIN-AUTH", "password": "Admin123"},
    )

    assert response.status_code == 200
    refresh_token = _refresh_cookie(response.headers["set-cookie"])
    body = response.json()
    assert body["access_token"]
    assert refresh_token
    assert body["me"] == {
        "principal_type": "platform_user",
        "principal_id": str(user.id),
        "session_id": body["me"]["session_id"],
        "password_reset_required": True,
        "workshop_id": None,
        "is_owner": False,
        "grants": [],
        "login": "admin-auth",
        "full_name": "Platform Admin",
        "phone": "+998901234567",
        "name": None,
        "preferred_branch_id": None,
        "status": "active",
    }

    me_response = await client.get("/api/v1/auth/me", headers=_auth(body["access_token"]))

    assert me_response.status_code == 200
    assert me_response.json()["principal_id"] == str(user.id)


async def test_workshop_login_resolves_by_login_and_password(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)

    # Login is case-insensitive and resolves with the submitted password.
    response = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "OWNER", "password": "Owner123"},
    )
    wrong = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "owner", "password": "Nope123"},
    )

    assert response.status_code == 200
    me = response.json()["me"]
    assert me["principal_type"] == "workshop_user"
    assert me["principal_id"] == str(owner.id)
    assert me["workshop_id"] == str(workshop.id)
    assert me["is_owner"] is True
    assert {grant["branch_id"] for grant in me["grants"]} == {str(branch.id)}
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "invalid_credentials"


async def test_workshop_login_is_globally_unique(db_session: AsyncSession) -> None:
    # The login alone names the account platform-wide: a second workshop cannot
    # take a login another workshop already uses.
    await seed_workshop_with_owner(db_session, login="owner")

    with pytest.raises(IntegrityError):
        await seed_workshop_with_owner(db_session, login="OWNER")


async def test_workshop_login_resolves_one_account_across_workshops(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Two workshops, two distinct logins — each resolves to its own workshop
    # from the login alone, with no password-driven candidate scan.
    ws_a, _, owner_a = await seed_workshop_with_owner(db_session, login="owner_a")
    ws_b, _, owner_b = await seed_workshop_with_owner(db_session, login="owner_b")
    owner_b.password_hash = hash_password("Different456")
    await db_session.flush()

    a = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "owner_a", "password": "Owner123"},
    )
    b = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "OWNER_B", "password": "Different456"},
    )
    # Another workshop's password is never accepted for this login.
    crossed = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "owner_a", "password": "Different456"},
    )

    assert a.status_code == 200
    assert a.json()["me"]["principal_id"] == str(owner_a.id)
    assert a.json()["me"]["workshop_id"] == str(ws_a.id)
    assert b.status_code == 200
    assert b.json()["me"]["principal_id"] == str(owner_b.id)
    assert b.json()["me"]["workshop_id"] == str(ws_b.id)
    assert crossed.status_code == 401
    assert crossed.json()["code"] == "invalid_credentials"


async def test_workshop_login_lockout_holds_for_every_login(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Lockout used to be defeatable by sharing a login across workshops: a failed
    # attempt recorded against nobody. With one account per login it always lands.
    await seed_workshop_with_owner(db_session, login="owner")
    await seed_workshop_with_owner(db_session, login="admin")

    for _ in range(5):
        miss = await client.post(
            "/api/v1/auth/workshop/login",
            json={"login": "admin", "password": "Wrong123"},
        )
        assert miss.status_code == 401
        assert miss.json()["code"] == "invalid_credentials"

    locked = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "admin", "password": "Owner123"},
    )

    assert locked.status_code == 423
    assert locked.json()["code"] == "account_locked"


async def test_bad_credentials_lockout_discloses_status_only_after_valid_password(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_platform_user(db_session, login="lockme", password="Admin123")

    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/platform/login",
            json={"login": "lockme", "password": "Wrong123"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "invalid_credentials"

    still_wrong = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "lockme", "password": "Wrong123"},
    )
    correct_but_locked = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "lockme", "password": "Admin123"},
    )

    assert still_wrong.status_code == 401
    assert still_wrong.json()["code"] == "invalid_credentials"
    assert correct_but_locked.status_code == 423
    assert correct_but_locked.json()["code"] == "account_locked"


async def test_blocked_status_is_hidden_until_password_is_valid(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await seed_platform_user(db_session, login="blocked", password="Admin123")
    user.status = UserStatus.BLOCKED
    await db_session.flush()

    wrong = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "blocked", "password": "Wrong123"},
    )
    correct = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "blocked", "password": "Admin123"},
    )

    assert wrong.status_code == 401
    assert wrong.json()["code"] == "invalid_credentials"
    assert correct.status_code == 403
    assert correct.json()["code"] == "account_blocked"


async def test_refresh_rotates_cookie_and_access_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_platform_user(db_session, login="refresh", password="Admin123")
    login = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "refresh", "password": "Admin123"},
    )
    old_access = login.json()["access_token"]
    refresh_token = _refresh_cookie(login.headers["set-cookie"])

    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": f"{REFRESH_COOKIE_NAME}={refresh_token}"},
    )

    assert response.status_code == 200
    new_access = response.json()["access_token"]
    assert new_access != old_access
    assert _refresh_cookie(response.headers["set-cookie"]) != refresh_token
    assert (await client.get("/api/v1/auth/me", headers=_auth(old_access))).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=_auth(new_access))).status_code == 200


async def test_password_change_clears_reset_gate_and_revokes_other_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_platform_user(db_session, login="changeme", password="Admin123")
    first = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "changeme", "password": "Admin123"},
    )
    second = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "changeme", "password": "Admin123"},
    )
    first_access = first.json()["access_token"]
    second_access = second.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/password/change",
        headers=_auth(first_access),
        json={"current_password": "Admin123", "new_password": "NewAdmin123"},
    )

    assert response.status_code == 204
    me = (await client.get("/api/v1/auth/me", headers=_auth(first_access))).json()
    assert me["password_reset_required"] is False
    assert (await client.get("/api/v1/auth/me", headers=_auth(second_access))).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/platform/login",
            json={"login": "changeme", "password": "Admin123"},
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/platform/login",
            json={"login": "changeme", "password": "NewAdmin123"},
        )
    ).status_code == 200


async def test_session_listing_and_deletion_are_scoped_to_current_principal(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_platform_user(db_session, login="sessions", password="Admin123")
    first = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "sessions", "password": "Admin123"},
    )
    second = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "sessions", "password": "Admin123"},
    )
    first_session_id = first.json()["me"]["session_id"]
    second_access = second.json()["access_token"]

    listed = await client.get("/api/v1/auth/sessions", headers=_auth(second_access))

    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert sum(1 for session in listed.json() if session["is_current"]) == 1

    deleted_other = await client.delete(
        f"/api/v1/auth/sessions/{first_session_id}",
        headers=_auth(second_access),
    )
    listed_again = await client.get("/api/v1/auth/sessions", headers=_auth(second_access))
    logout = await client.delete("/api/v1/auth/sessions/current", headers=_auth(second_access))

    assert deleted_other.status_code == 204
    assert len(listed_again.json()) == 1
    assert logout.status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=_auth(second_access))).status_code == 401
