"""Identity & access: sign-in, sessions, me, staff + grants, client OAuth."""

from app.core.security import hash_password
from app.models.identity import WorkshopUser
from app.models.workshop import Branch, Workshop
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

GOOD_PW = "Passw0rd!"


async def _platform_user(db: AsyncSession, login: str = "admin", *, force_change: bool = False):
    from app.models.identity import PlatformUser

    user = PlatformUser(
        login=login,
        password_hash=hash_password(GOOD_PW),
        full_name="Operator",
        phone="+998901112233",
        force_password_change=force_change,
    )
    db.add(user)
    await db.commit()
    return user


async def _workshop_with_owner(db: AsyncSession) -> tuple[Workshop, WorkshopUser, Branch]:
    ws = Workshop(name="Mebel Test", phone="+998900000000")
    db.add(ws)
    await db.flush()
    branch = Branch(workshop_id=ws.id, name="Yunusobod", address="Tashkent", phone="+998900000001")
    db.add(branch)
    owner = WorkshopUser(
        workshop_id=ws.id,
        login="owner",
        password_hash=hash_password(GOOD_PW),
        full_name="Owner",
        phone="+998900000002",
        is_owner=True,
        force_password_change=False,
    )
    db.add(owner)
    await db.flush()
    ws.owner_user_id = owner.id
    await db.commit()
    return ws, owner, branch


async def test_platform_login_me_and_change_password(client: AsyncClient, db_session):
    await _platform_user(db_session, force_change=True)

    r = await client.post(
        "/api/v1/auth/platform/login", json={"login": "ADMIN", "password": GOOD_PW}
    )
    assert r.status_code == 200, r.text
    tokens = r.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["force_password_change"] is True
    assert me.json()["principal_type"] == "platform_user"

    # gated: a normal endpoint refuses until the password is changed
    gated = await client.get("/api/v1/platform/users", headers=headers)
    assert gated.status_code == 403
    assert gated.json()["code"] == "password_change_required"

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": GOOD_PW, "new_password": "NewPass1"},
    )
    assert changed.status_code == 204

    # now the gate is lifted
    ok = await client.get("/api/v1/platform/users", headers=headers)
    assert ok.status_code == 200


async def test_login_generic_error_and_lockout(client: AsyncClient, db_session):
    await _platform_user(db_session)
    for _ in range(5):
        bad = await client.post(
            "/api/v1/auth/platform/login", json={"login": "admin", "password": "wrong"}
        )
        assert bad.status_code == 401
        assert bad.json()["code"] == "invalid_credentials"
    locked = await client.post(
        "/api/v1/auth/platform/login", json={"login": "admin", "password": GOOD_PW}
    )
    assert locked.status_code == 429
    assert locked.json()["code"] == "account_locked"


async def test_owner_creates_staff_with_grants(client: AsyncClient, db_session):
    ws, _owner, branch = await _workshop_with_owner(db_session)

    login = await client.post(
        "/api/v1/auth/workshop/login", json={"login": "owner", "password": GOOD_PW}
    )
    assert login.status_code == 200
    owner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = await client.post(
        "/api/v1/workshop/users",
        headers=owner_headers,
        json={
            "full_name": "Cutter Bob",
            "login": "bob",
            "phone": "+998901234567",
            "home_branch_id": str(branch.id),
            "grants": [{"permission": "process_production", "branch_id": str(branch.id)}],
        },
    )
    assert created.status_code == 201, created.text
    temp = created.json()["temp_password"]
    assert len(temp) >= 8

    # staff logs in, must change password, then me shows the grant
    staff_login = await client.post(
        "/api/v1/auth/workshop/login", json={"login": "bob", "password": temp}
    )
    assert staff_login.status_code == 200
    staff_headers = {"Authorization": f"Bearer {staff_login.json()['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=staff_headers)
    assert me.json()["force_password_change"] is True
    assert me.json()["grants"] == [
        {"permission": "process_production", "branch_id": str(branch.id)}
    ]


async def test_owner_only_guard(client: AsyncClient, db_session):
    """A non-owner cannot reach owner-only staff management."""
    ws, owner, branch = await _workshop_with_owner(db_session)
    staff = WorkshopUser(
        workshop_id=ws.id,
        login="staff",
        password_hash=hash_password(GOOD_PW),
        full_name="Staff",
        phone="+998900000009",
        is_owner=False,
        force_password_change=False,
    )
    db_session.add(staff)
    await db_session.commit()

    login = await client.post(
        "/api/v1/auth/workshop/login", json={"login": "staff", "password": GOOD_PW}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = await client.get("/api/v1/workshop/users", headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


async def test_client_telegram_login_creates_then_reuses(client: AsyncClient, db_session):
    payload = {
        "id": 555001,
        "first_name": "Aziz",
        "phone_number": "+998901234567",
        "auth_date": 1900000000,
    }
    r1 = await client.post("/api/v1/auth/client/telegram", json=payload)
    assert r1.status_code == 200, r1.text
    assert r1.json()["is_new"] is True

    r2 = await client.post("/api/v1/auth/client/telegram", json=payload)
    assert r2.status_code == 200
    assert r2.json()["is_new"] is False


async def test_client_telegram_missing_phone(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/client/telegram", json={"id": 9, "first_name": "X", "auth_date": 1}
    )
    assert r.status_code == 400
    assert r.json()["code"] == "missing_phone_number"


async def test_sessions_list_and_revoke(client: AsyncClient, db_session):
    await _platform_user(db_session)
    login = await client.post(
        "/api/v1/auth/platform/login", json={"login": "admin", "password": GOOD_PW}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    sessions = await client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions.status_code == 200
    rows = sessions.json()
    assert len(rows) == 1
    assert rows[0]["current"] is True

    logout = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 204
    after = await client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401


async def test_unauthenticated_is_401(client: AsyncClient):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
