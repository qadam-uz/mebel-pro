import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    MaterialKind,
    PanelMaterialType,
    Permission,
    UserStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import Manufacturer, Material
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _owner_login(client: AsyncClient, db_session: AsyncSession) -> tuple[str, str]:
    _workshop, branch, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    response = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "owner", "password": "Owner123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"], str(branch.id)


async def _seed_platform_material(db_session: AsyncSession) -> uuid.UUID:
    manufacturer = Manufacturer(name=f"Egger {uuid.uuid4().hex[:6]}", country="AT")
    db_session.add(manufacturer)
    await db_session.flush()
    material = Material(
        kind=MaterialKind.PANEL,
        manufacturer_id=manufacturer.id,
        type=PanelMaterialType.DSP,
        name="H1334 ST9 18 mm 2800x2070",
        thickness_mm=Decimal("18"),
        color="Light oak",
        decor_code="H1334",
        panel_length_mm=2800,
        panel_width_mm=2070,
        grain_direction=True,
    )
    db_session.add(material)
    await db_session.flush()
    return material.id


async def test_onboarding_status_derives_from_setup_progress(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id = await _owner_login(client, db_session)

    fresh = await client.get("/api/v1/workshop/onboarding", headers=_auth(owner_access))
    assert fresh.status_code == 200
    assert fresh.json() == {
        "branch_configured": False,
        "materials_added": False,
        "setup_complete": False,
        "first_branch_id": branch_id,
    }

    one_rate = await client.put(
        f"/api/v1/workshop/branches/{branch_id}/pricing",
        headers=_auth(owner_access),
        json={"cutting_rate_tiyin": 500000, "edge_banding_rate_tiyin": None},
    )
    assert one_rate.status_code == 200
    partial = await client.get("/api/v1/workshop/onboarding", headers=_auth(owner_access))
    assert partial.json()["branch_configured"] is False
    assert partial.json()["setup_complete"] is False

    both_rates = await client.put(
        f"/api/v1/workshop/branches/{branch_id}/pricing",
        headers=_auth(owner_access),
        json={"cutting_rate_tiyin": 500000, "edge_banding_rate_tiyin": 300000},
    )
    assert both_rates.status_code == 200
    priced = await client.get("/api/v1/workshop/onboarding", headers=_auth(owner_access))
    assert priced.json()["branch_configured"] is True
    assert priced.json()["materials_added"] is False
    assert priced.json()["setup_complete"] is False

    material_id = await _seed_platform_material(db_session)
    added = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"material_id": str(material_id), "price_tiyin": 25500000, "min_stock": 2},
    )
    assert added.status_code == 201
    complete = await client.get("/api/v1/workshop/onboarding", headers=_auth(owner_access))
    assert complete.json() == {
        "branch_configured": True,
        "materials_added": True,
        "setup_complete": True,
        "first_branch_id": branch_id,
    }


async def test_onboarding_ignores_branches_without_active_status(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id = await _owner_login(client, db_session)

    both_rates = await client.put(
        f"/api/v1/workshop/branches/{branch_id}/pricing",
        headers=_auth(owner_access),
        json={"cutting_rate_tiyin": 500000, "edge_banding_rate_tiyin": 300000},
    )
    assert both_rates.status_code == 200

    deactivated = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/status",
        headers=_auth(owner_access),
        json={"status": "inactive", "reason": "Closed for the season"},
    )
    assert deactivated.status_code == 200

    status_view = await client.get("/api/v1/workshop/onboarding", headers=_auth(owner_access))
    assert status_view.status_code == 200
    assert status_view.json()["branch_configured"] is False
    assert status_view.json()["setup_complete"] is False
    assert status_view.json()["first_branch_id"] is None


async def test_onboarding_is_owner_only(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _workshop, branch, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    staff = WorkshopUser(
        workshop_id=branch.workshop_id,
        login=f"staff-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("StaffTemp123"),
        full_name="Scoped Staff",
        phone="+998901234111",
        is_owner=False,
        home_branch_id=branch.id,
        status=UserStatus.ACTIVE,
        password_reset_required=False,
    )
    db_session.add(staff)
    await db_session.flush()
    db_session.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=Permission.MANAGE_CATALOG,
            branch_id=branch.id,
            granted_by_user_id=staff.id,
            granted_at=datetime.now(UTC),
        )
    )
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=staff.id,
    )

    response = await client.get("/api/v1/workshop/onboarding", headers=_auth(tokens.access_token))
    assert response.status_code == 403
