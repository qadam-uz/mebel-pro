from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.support.contracts import ActionLog
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def test_client_profile_updates_name_and_preferred_branch_without_phone_patch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, branch, _ = await seed_workshop_with_owner(db_session)
    client_row = Client(phone="+998909090909", name="Old Name", preferred_branch_id=branch.id)
    db_session.add(client_row)
    await db_session.flush()
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client_row.id,
    )

    options = await client.get("/api/v1/client/branch-options", headers=_auth(tokens.access_token))
    updated = await client.patch(
        "/api/v1/client/profile",
        headers=_auth(tokens.access_token),
        json={"name": "New Name", "phone": "+998900000000"},
    )
    cleared = await client.patch(
        "/api/v1/client/profile",
        headers=_auth(tokens.access_token),
        json={"preferred_branch_id": None},
    )
    action_count = await db_session.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(ActionLog.action == "client.profile.update")
    )

    assert options.status_code == 200
    assert options.json()[0]["branch_id"] == str(branch.id)
    # CB-112: branch-options carries today's working hours for the picker.
    assert set(options.json()[0]["today_hours"]) == {"open", "close"}
    assert updated.status_code == 200
    assert updated.json()["name"] == "New Name"
    assert updated.json()["phone"] == "+998909090909"
    assert updated.json()["preferred_branch_id"] == str(branch.id)
    assert cleared.status_code == 200
    assert cleared.json()["preferred_branch_id"] is None
    assert action_count == 2
