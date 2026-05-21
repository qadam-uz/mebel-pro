"""Notifications inbox — list / unread-count / mark-read / mark-all + isolation."""

from app.core.security import hash_password
from app.models.enums import PrincipalType
from app.models.identity import Client, PlatformUser
from app.services import notifications as notif_service
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _client(db: AsyncSession, tg: int = 1) -> Client:
    c = Client(telegram_id=tg, phone=f"+99890000{tg:04d}", first_name="C")
    db.add(c)
    await db.commit()
    return c


async def test_list_unread_and_mark(client: AsyncClient, db_session, auth_headers):
    c = await _client(db_session)
    for i in range(3):
        await notif_service.notify(
            db_session,
            recipient_type=PrincipalType.CLIENT,
            recipient_id=c.id,
            event_code="order.status_changed",
            payload={"n": i},
        )
    await db_session.commit()
    headers = await auth_headers(PrincipalType.CLIENT, c.id)

    listed = await client.get("/api/v1/notifications", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 3
    # all three for this principal are returned (created within the same tick,
    # so we don't assert a strict order among equal timestamps)
    assert {r["payload"]["n"] for r in rows} == {0, 1, 2}

    count = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert count.json()["unread"] == 3

    one = rows[0]["id"]
    marked = await client.post(f"/api/v1/notifications/{one}/mark-read", headers=headers)
    assert marked.status_code == 204
    assert (await client.get("/api/v1/notifications/unread-count", headers=headers)).json()[
        "unread"
    ] == 2

    unread_only = await client.get("/api/v1/notifications?unread_only=true", headers=headers)
    assert len(unread_only.json()) == 2

    all_read = await client.post("/api/v1/notifications/mark-all-read", headers=headers)
    assert all_read.status_code == 200
    assert all_read.json()["unread"] == 0
    assert (await client.get("/api/v1/notifications/unread-count", headers=headers)).json()[
        "unread"
    ] == 0


async def test_inbox_isolation_between_principals(client, db_session, auth_headers):
    alice = await _client(db_session, tg=1)
    bob = await _client(db_session, tg=2)
    await notif_service.notify(
        db_session,
        recipient_type=PrincipalType.CLIENT,
        recipient_id=alice.id,
        event_code="order.status_changed",
    )
    await db_session.commit()

    bob_headers = await auth_headers(PrincipalType.CLIENT, bob.id)
    listed = await client.get("/api/v1/notifications", headers=bob_headers)
    assert listed.json() == []
    assert (await client.get("/api/v1/notifications/unread-count", headers=bob_headers)).json()[
        "unread"
    ] == 0


async def test_mark_read_other_principal_is_404(client, db_session, auth_headers):
    alice = await _client(db_session, tg=1)
    bob = await _client(db_session, tg=2)
    n = await notif_service.notify(
        db_session,
        recipient_type=PrincipalType.CLIENT,
        recipient_id=alice.id,
        event_code="order.status_changed",
    )
    await db_session.commit()
    bob_headers = await auth_headers(PrincipalType.CLIENT, bob.id)
    r = await client.post(f"/api/v1/notifications/{n.id}/mark-read", headers=bob_headers)
    assert r.status_code == 404


async def test_platform_user_has_own_inbox(client, db_session, auth_headers):
    op = PlatformUser(
        login="op",
        password_hash=hash_password("Passw0rd!"),
        full_name="Op",
        phone="+998900000001",
        force_password_change=False,
    )
    db_session.add(op)
    await db_session.commit()
    await notif_service.notify(
        db_session,
        recipient_type=PrincipalType.PLATFORM_USER,
        recipient_id=op.id,
        event_code="platform.error_spike",
    )
    await db_session.commit()
    headers = await auth_headers(PrincipalType.PLATFORM_USER, op.id)
    assert (await client.get("/api/v1/notifications/unread-count", headers=headers)).json()[
        "unread"
    ] == 1
