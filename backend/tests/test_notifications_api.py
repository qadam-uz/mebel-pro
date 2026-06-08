from datetime import UTC, datetime

from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from app.modules.support.contracts import Notification
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def test_principal_notification_inbox_count_and_read_actions(
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
    notification = Notification(
        recipient_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        recipient_id=owner.id,
        event_code="order.created",
        entity_type="order",
        payload={"summary": "New order"},
        created_at=datetime.now(UTC),
    )
    other = Notification(
        recipient_type=AuthenticatedPrincipalType.CLIENT,
        recipient_id=owner.id,
        event_code="client.only",
        payload={},
        created_at=datetime.now(UTC),
    )
    db_session.add_all([notification, other])
    await db_session.flush()

    unread = await client.get(
        "/api/v1/notifications/unread-count",
        headers=_auth(tokens.access_token),
    )
    listed = await client.get("/api/v1/notifications", headers=_auth(tokens.access_token))
    marked = await client.post(
        f"/api/v1/notifications/{notification.id}/read",
        headers=_auth(tokens.access_token),
    )
    unread_after_one = await client.get(
        "/api/v1/notifications/unread-count",
        headers=_auth(tokens.access_token),
    )
    db_session.add_all(
        Notification(
            recipient_type=AuthenticatedPrincipalType.WORKSHOP_USER,
            recipient_id=owner.id,
            event_code=f"bulk.{index}",
            payload={},
            created_at=datetime.now(UTC),
        )
        for index in range(125)
    )
    await db_session.flush()
    unread_before_all = await client.get(
        "/api/v1/notifications/unread-count",
        headers=_auth(tokens.access_token),
    )
    mark_all = await client.post(
        "/api/v1/notifications/read-all",
        headers=_auth(tokens.access_token),
    )
    unread_after_all = await client.get(
        "/api/v1/notifications/unread-count",
        headers=_auth(tokens.access_token),
    )

    assert unread.status_code == 200
    assert unread.json()["unread"] == 1
    assert listed.status_code == 200
    assert [row["event_code"] for row in listed.json()] == ["order.created"]
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None
    assert unread_after_one.json()["unread"] == 0
    assert unread_before_all.json()["unread"] == 125
    assert mark_all.status_code == 204
    assert unread_after_all.json()["unread"] == 0
