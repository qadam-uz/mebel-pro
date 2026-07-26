import uuid
from datetime import UTC, datetime, timedelta

from app.core.security import hash_password
from app.models.enums import AuthenticatedPrincipalType, Permission, UserStatus
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial
from app.modules.inventory.contracts import StockItem, StockTransaction, Supplier
from app.modules.support.api import InMemoryFileStorage, file_storage
from app.modules.support.contracts import ActionLog, File, Notification
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _default_working_hours() -> dict[str, dict[str, str | None]]:
    return {
        "monday": {"open": "09:00", "close": "18:00"},
        "tuesday": {"open": "09:00", "close": "18:00"},
        "wednesday": {"open": "09:00", "close": "18:00"},
        "thursday": {"open": "09:00", "close": "18:00"},
        "friday": {"open": "09:00", "close": "18:00"},
        "saturday": {"open": "10:00", "close": "16:00"},
        "sunday": {"open": None, "close": None},
    }


async def _platform_access(db_session: AsyncSession) -> str:
    platform = await seed_platform_user(
        db_session,
        login=f"platform-{uuid.uuid4().hex[:8]}",
        password_reset_required=False,
    )
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=platform.id,
    )
    return tokens.access_token


async def _owner_fixture(db_session: AsyncSession) -> tuple[str, uuid.UUID, uuid.UUID, uuid.UUID]:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, workshop.id, branch.id, owner.id


async def _staff_access(
    db_session: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    permission: Permission,
) -> str:
    staff = WorkshopUser(
        workshop_id=workshop_id,
        login=f"staff-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("StaffTemp123"),
        full_name="Scoped Staff",
        phone="+998901234111",
        is_owner=False,
        home_branch_id=branch_id,
        status=UserStatus.ACTIVE,
        password_reset_required=False,
    )
    db_session.add(staff)
    await db_session.flush()
    db_session.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=permission,
            branch_id=branch_id,
            granted_by_user_id=staff.id,
            granted_at=datetime.now(UTC),
        )
    )
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=staff.id,
    )
    return tokens.access_token


async def _create_catalog_material(client: AsyncClient, access: str) -> tuple[str, str]:
    manufacturer = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(access),
        json={"name": f"Egger {uuid.uuid4().hex[:6]}", "country": "AT"},
    )
    assert manufacturer.status_code == 201
    manufacturer_id = manufacturer.json()["id"]
    material = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(access),
        json={
            "kind": "panel",
            "manufacturer_id": manufacturer_id,
            "type": "dsp",
            "name": "H1334 ST9 18 mm 2800x2070",
            "thickness_mm": "18",
            "color": "Light oak",
            "decor_code": "H1334",
            "panel_length_mm": 2800,
            "panel_width_mm": 2070,
            "grain_direction": True,
        },
    )
    assert material.status_code == 201
    return manufacturer_id, material.json()["id"]


async def test_platform_catalog_crud_and_branch_material_stock_sync(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    manufacturer_id, material_id = await _create_catalog_material(client, platform_access)
    second_manufacturer = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(platform_access),
        json={"name": f"Kronospan {uuid.uuid4().hex[:6]}", "country": "PL"},
    )
    assert second_manufacturer.status_code == 201
    second_material = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(platform_access),
        json={
            "kind": "panel",
            "manufacturer_id": second_manufacturer.json()["id"],
            "type": "mdf",
            "name": "MDF White 18 mm 2800x2070",
            "thickness_mm": "18",
            "color": "White",
            "decor_code": "MDF-W",
            "panel_length_mm": 2800,
            "panel_width_mm": 2070,
            "grain_direction": False,
        },
    )
    assert second_material.status_code == 201
    manufacturer = await client.get(
        f"/api/v1/platform/catalog/manufacturers/{manufacturer_id}",
        headers=_auth(platform_access),
    )

    duplicate = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(platform_access),
        json={"name": manufacturer.json()["name"].lower(), "country": "AT"},
    )
    picker = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/materials",
        headers=_auth(owner_access),
    )
    branch_material = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"material_id": material_id, "price_tiyin": 25500000, "min_stock": 2},
    )
    second_branch_material = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "material_id": second_material.json()["id"],
            "price_tiyin": 18800000,
            "min_stock": 1,
        },
    )
    stock_item = await db_session.scalar(
        select(StockItem).where(
            StockItem.branch_id == branch_id,
            StockItem.material_id == uuid.UUID(material_id),
        )
    )
    assert stock_item is not None
    assert stock_item.on_hand == 0
    assert stock_item.min_stock == 2

    edited = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{branch_material.json()['id']}",
        headers=_auth(owner_access),
        json={"min_stock": 4},
    )
    manufacturer_filter = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?manufacturer_id={manufacturer_id}",
        headers=_auth(owner_access),
    )
    type_filter = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?material_type=mdf",
        headers=_auth(owner_access),
    )
    picker_type_filter = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/materials?material_type=dsp",
        headers=_auth(owner_access),
    )

    assert duplicate.status_code == 409
    assert picker.status_code == 200
    assert picker.json()["items"][0]["material"]["id"] == material_id
    assert picker.json()["total"] == len(picker.json()["items"])
    assert branch_material.status_code == 201
    assert second_branch_material.status_code == 201
    assert branch_material.json()["min_stock"] == 2
    assert edited.status_code == 200
    assert stock_item.min_stock == 4
    assert manufacturer_filter.status_code == 200
    assert [row["material"]["id"] for row in manufacturer_filter.json()] == [material_id]
    assert type_filter.status_code == 200
    assert [row["material"]["id"] for row in type_filter.json()] == [second_material.json()["id"]]
    assert picker_type_filter.status_code == 200
    # QAD-159: the picker excludes materials the branch already carries, and
    # `material_id` was attached above — so the dsp filter now comes back empty.
    assert picker_type_filter.json() == {"items": [], "total": 0}


async def test_material_validation_and_non_platform_rejection(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, _, _ = await _owner_fixture(db_session)
    manufacturer_id, _ = await _create_catalog_material(client, platform_access)

    bad_edge = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(platform_access),
        json={
            "kind": "edge",
            "manufacturer_id": manufacturer_id,
            "type": "dsp",
            "name": "Edge tape",
            "thickness_mm": "0.4",
            "color": "Oak",
        },
    )
    forbidden = await client.get(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(owner_access),
    )

    assert bad_edge.status_code == 400
    assert bad_edge.json()["code"] == "invalid_edge_material"
    assert forbidden.status_code == 403


async def test_owner_branch_setup_pricing_status_and_logo_upload(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    storage = InMemoryFileStorage()
    from app.main import app

    app.dependency_overrides[file_storage] = lambda: storage
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)

    logo = await client.post(
        "/api/v1/files",
        headers=_auth(owner_access),
        files={"upload": ("logo.png", b"fake-png", "image/png")},
    )
    replacement_logo = await client.post(
        "/api/v1/files",
        headers=_auth(owner_access),
        files={"upload": ("logo-2.png", b"fake-png-2", "image/png")},
    )
    settings = await client.patch(
        "/api/v1/workshop/settings",
        headers=_auth(owner_access),
        json={"name": "New Workshop Name", "logo_file_id": logo.json()["id"]},
    )
    replacement_settings = await client.patch(
        "/api/v1/workshop/settings",
        headers=_auth(owner_access),
        json={"logo_file_id": replacement_logo.json()["id"]},
    )
    stale_contact_settings = await client.patch(
        "/api/v1/workshop/settings",
        headers=_auth(owner_access),
        json={"phone": "+998901010100", "address": "Tashkent"},
    )
    created = await client.post(
        "/api/v1/workshop/branches",
        headers=_auth(owner_access),
        json={
            "name": "Chilonzor",
            "address": "Tashkent, Chilonzor",
            "phone": "+998901010101",
            "latitude": "41.28",
            "longitude": "69.20",
            "working_hours": _default_working_hours(),
        },
    )
    bad_hours = await client.post(
        "/api/v1/workshop/branches",
        headers=_auth(owner_access),
        json={
            "name": "Bad hours",
            "address": "Tashkent",
            "phone": "+998901010102",
            "latitude": "41.28",
            "longitude": "69.20",
            "working_hours": {
                **_default_working_hours(),
                "monday": {"open": "18:00", "close": "09:00"},
            },
        },
    )
    pricing = await client.put(
        f"/api/v1/workshop/branches/{created.json()['id']}/pricing",
        headers=_auth(owner_access),
        json={"cutting_rate_tiyin": 120000, "edge_banding_rate_tiyin": 45000},
    )
    bad_status = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/status",
        headers=_auth(owner_access),
        json={"status": "inactive"},
    )
    status_change = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/status",
        headers=_auth(owner_access),
        json={"status": "temporarily_closed", "reason": "Renovation"},
    )

    assert logo.status_code == 200
    assert settings.status_code == 200
    assert settings.json()["logo_file_id"] == logo.json()["id"]
    assert "phone" not in settings.json()
    assert "address" not in settings.json()
    assert replacement_settings.status_code == 200
    assert replacement_settings.json()["logo_file_id"] == replacement_logo.json()["id"]
    assert stale_contact_settings.status_code == 422
    old_logo = await db_session.get(File, uuid.UUID(logo.json()["id"]))
    assert old_logo is not None
    assert old_logo.entity_type is None
    assert old_logo.entity_id is None
    assert created.status_code == 201
    assert created.json()["working_hours"]["sunday"] == {"open": None, "close": None}
    for key in ["active_orders_count", "material_count", "low_stock_count", "staff_count"]:
        assert key not in created.json()
    assert bad_hours.status_code == 422
    assert pricing.status_code == 200
    assert pricing.json()["cutting_rate_tiyin"] == 120000
    assert bad_status.status_code == 400
    assert bad_status.json()["code"] == "reason_required"
    assert status_change.status_code == 200
    assert status_change.json()["closed_reason"] == "Renovation"


async def test_inventory_stock_in_adjustment_notifications_and_pricing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, workshop_id, branch_id, _ = await _owner_fixture(db_session)
    _, material_id = await _create_catalog_material(client, platform_access)
    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"material_id": material_id, "price_tiyin": 100000, "min_stock": 2},
    )
    stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "material_id": material_id,
            "quantity": 3,
            "unit_price_tiyin": 51500000,
            "supplier": {"name": "Wood Supplier"},
        },
    )
    adjustment = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-adjustments",
        headers=_auth(owner_access),
        json={"material_id": material_id, "quantity": -1, "note": "Stock take"},
    )
    stock = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock",
        headers=_auth(owner_access),
    )
    transactions = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions",
        headers=_auth(owner_access),
    )
    transactions_page_one = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions?limit=1&offset=0",
        headers=_auth(owner_access),
    )
    transactions_page_two = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions?limit=1&offset=1",
        headers=_auth(owner_access),
    )
    today = datetime.now(UTC).date().isoformat()
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    transactions_today = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions?date_from={today}&date_to={today}",
        headers=_auth(owner_access),
    )
    transactions_before_today = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions?date_to={yesterday}",
        headers=_auth(owner_access),
    )
    notification_count = await db_session.scalar(select(func.count()).select_from(Notification))
    supplier_count = await db_session.scalar(select(func.count()).select_from(Supplier))
    transaction_count = await db_session.scalar(select(func.count()).select_from(StockTransaction))
    action_count = await db_session.scalar(
        select(func.count()).select_from(ActionLog).where(ActionLog.workshop_id == workshop_id)
    )

    assert stock_in.status_code == 201
    assert stock_in.json()["unit_price_tiyin"] == 51500000
    assert stock_in.json()["total_price_tiyin"] == 154500000
    assert adjustment.status_code == 201
    assert adjustment.json()["unit_price_tiyin"] is None
    assert adjustment.json()["total_price_tiyin"] is None
    assert adjustment.json()["balance_after"] == 2
    assert stock.status_code == 200
    assert stock.json()[0]["on_hand"] == 2
    assert stock.json()[0]["is_low_stock"] is True
    assert transactions.status_code == 200
    assert [row["type"] for row in transactions.json()] == ["adjust", "stock_in"]
    assert transactions.json()[0]["actor_name"] == "Workshop Owner"
    assert transactions.json()[0]["note"] == "Stock take"
    assert transactions.json()[1]["actor_name"] == "Workshop Owner"
    assert transactions_page_one.status_code == 200
    assert [row["type"] for row in transactions_page_one.json()] == ["adjust"]
    assert transactions_page_two.status_code == 200
    assert [row["type"] for row in transactions_page_two.json()] == ["stock_in"]
    assert transactions_today.status_code == 200
    assert [row["type"] for row in transactions_today.json()] == ["adjust", "stock_in"]
    assert transactions_before_today.status_code == 200
    assert transactions_before_today.json() == []
    assert notification_count == 1
    assert supplier_count == 1
    assert transaction_count == 2
    assert action_count >= 3


async def test_branch_scoped_staff_authorization(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, workshop_id, branch_id, _ = await _owner_fixture(db_session)
    _, material_id = await _create_catalog_material(client, platform_access)
    catalog_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    inventory_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_INVENTORY,
    )

    add_material = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(catalog_staff),
        json={"material_id": material_id, "price_tiyin": 150000, "min_stock": 1},
    )
    catalog_stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(catalog_staff),
        json={
            "material_id": material_id,
            "quantity": 1,
            "unit_price_tiyin": 100000,
            "supplier": {"name": "Nope"},
        },
    )
    inventory_edit_catalog = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{add_material.json()['id']}",
        headers=_auth(inventory_staff),
        json={"min_stock": 3},
    )
    inventory_stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(inventory_staff),
        json={
            "material_id": material_id,
            "quantity": 2,
            "unit_price_tiyin": 100000,
            "supplier": {"name": "Allowed"},
        },
    )
    duplicate_owner_add = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"material_id": material_id, "price_tiyin": 150000, "min_stock": 1},
    )
    deactivated = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/{add_material.json()['id']}/deactivate",
        headers=_auth(owner_access),
    )
    stock_in_after_deactivate = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(inventory_staff),
        json={
            "material_id": material_id,
            "quantity": 1,
            "unit_price_tiyin": 100000,
            "supplier": {"name": "After deactivate"},
        },
    )

    assert add_material.status_code == 201
    assert catalog_stock_in.status_code == 403
    assert inventory_edit_catalog.status_code == 403
    assert inventory_stock_in.status_code == 201
    assert duplicate_owner_add.status_code == 409
    assert deactivated.status_code == 200
    assert stock_in_after_deactivate.status_code == 201


async def test_stock_in_pricing_math_last_price_and_validation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    manufacturer_id, panel_id = await _create_catalog_material(client, platform_access)
    edge = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(platform_access),
        json={
            "kind": "edge",
            "manufacturer_id": manufacturer_id,
            "thickness_mm": "2",
            "color": "Light oak",
            "decor_code": "H1334",
            "edge_width_mm": 19,
        },
    )
    assert edge.status_code == 201
    edge_id = edge.json()["id"]
    unpriced = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(platform_access),
        json={
            "kind": "edge",
            "manufacturer_id": manufacturer_id,
            "thickness_mm": "0.4",
            "color": "White",
            "edge_width_mm": 19,
        },
    )
    unpriced_id = unpriced.json()["id"]
    for material_id in (panel_id, edge_id, unpriced_id):
        added = await client.post(
            f"/api/v1/workshop/branches/{branch_id}/materials",
            headers=_auth(owner_access),
            json={"material_id": material_id, "price_tiyin": 100000, "min_stock": 0},
        )
        assert added.status_code == 201

    first = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "material_id": panel_id,
            "quantity": 20,
            "unit_price_tiyin": 51500000,
            "supplier": {"name": "Panel Trade"},
        },
    )
    assert first.status_code == 201
    first_supplier_id = first.json()["supplier_id"]
    second = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "material_id": panel_id,
            "quantity": 5,
            "unit_price_tiyin": 52000000,
            "supplier": {"name": "Boshqa Trade"},
        },
    )
    assert second.status_code == 201
    edge_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "material_id": edge_id,
            "quantity": 1234,
            "unit_price_tiyin": 55,
            "supplier_id": first_supplier_id,
        },
    )
    last_overall = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials/{panel_id}/last-price",
        headers=_auth(owner_access),
    )
    last_for_first_supplier = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials/{panel_id}/last-price"
        f"?supplier_id={first_supplier_id}",
        headers=_auth(owner_access),
    )
    last_unknown_supplier_falls_back = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials/{panel_id}/last-price"
        f"?supplier_id={uuid.uuid4()}",
        headers=_auth(owner_access),
    )
    last_never_priced = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials/{unpriced_id}/last-price",
        headers=_auth(owner_access),
    )
    missing_price = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={"material_id": panel_id, "quantity": 1, "supplier_id": first_supplier_id},
    )
    negative_price = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "material_id": panel_id,
            "quantity": 1,
            "unit_price_tiyin": -1,
            "supplier_id": first_supplier_id,
        },
    )

    # Panel: total = quantity x unit price.
    assert first.json()["total_price_tiyin"] == 20 * 51500000
    # Edge: quantity is millimetres, price is per metre — floor division, sale-side mirror.
    assert edge_in.status_code == 201
    assert edge_in.json()["unit_price_tiyin"] == 55
    assert edge_in.json()["total_price_tiyin"] == 1234 * 55 // 1000
    assert last_overall.status_code == 200
    assert last_overall.json()["unit_price_tiyin"] == 52000000
    assert last_overall.json()["supplier_name"] == "Boshqa Trade"
    assert last_overall.json()["recorded_at"] is not None
    assert last_for_first_supplier.json()["unit_price_tiyin"] == 51500000
    assert last_for_first_supplier.json()["supplier_id"] == first_supplier_id
    assert last_unknown_supplier_falls_back.json()["unit_price_tiyin"] == 52000000
    assert last_never_priced.status_code == 200
    assert last_never_priced.json() == {
        "unit_price_tiyin": None,
        "recorded_at": None,
        "supplier_id": None,
        "supplier_name": None,
    }
    assert missing_price.status_code == 422
    assert negative_price.status_code == 400
    assert negative_price.json()["code"] == "invalid_price"

    # Inventory value: on-hand at the LATEST purchase price, derived at read
    # time — 25 panels at the newer 52M price plus the edge mm at per-metre.
    value = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-value",
        headers=_auth(owner_access),
    )
    assert value.status_code == 200
    assert value.json()["value_tiyin"] == 25 * 52000000 + 1234 * 55 // 1000


async def test_client_catalog_is_public_shape_and_visibility_filtered(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    _, material_id = await _create_catalog_material(client, platform_access)
    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"material_id": material_id, "price_tiyin": 250000, "min_stock": 5},
    )
    client_row = Client(phone="+998908888888", name="Client")
    db_session.add(client_row)
    await db_session.flush()
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client_row.id,
    )

    branches = await client.get("/api/v1/client/branches", headers=_auth(tokens.access_token))
    materials = await client.get(
        f"/api/v1/client/branches/{branch_id}/materials",
        headers=_auth(tokens.access_token),
    )
    deactivated = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/"
        f"{(await db_session.scalar(select(BranchMaterial.id))).hex}/deactivate",
        headers=_auth(owner_access),
    )
    hidden = await client.get(
        f"/api/v1/client/branches/{branch_id}/materials",
        headers=_auth(tokens.access_token),
    )

    assert branches.status_code == 200
    assert branches.json()[0]["branch_id"] == str(branch_id)
    assert materials.status_code == 200
    material = materials.json()[0]
    assert material["id"] == material_id
    assert material["price_tiyin"] == 250000
    assert "on_hand" not in material
    assert "supplier_id" not in material
    assert "min_stock" not in material
    assert deactivated.status_code == 200
    assert hidden.status_code == 200
    assert hidden.json() == []


async def test_material_image_visibility_follows_client_branch_visibility(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    storage = InMemoryFileStorage()
    from app.main import app

    app.dependency_overrides[file_storage] = lambda: storage
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    manufacturer_id, _ = await _create_catalog_material(client, platform_access)
    image = await client.post(
        "/api/v1/files",
        headers=_auth(platform_access),
        files={"upload": ("material.png", b"material-image", "image/png")},
    )
    material = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(platform_access),
        json={
            "kind": "panel",
            "manufacturer_id": manufacturer_id,
            "type": "dsp",
            "name": "Image material",
            "thickness_mm": "18",
            "color": "White",
            "panel_length_mm": 2800,
            "panel_width_mm": 2070,
            "grain_direction": True,
            "image_file_id": image.json()["id"],
        },
    )
    client_row = Client(phone="+998907777777", name="Client")
    db_session.add(client_row)
    await db_session.flush()
    client_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client_row.id,
    )
    hidden_image = await client.get(
        f"/api/v1/files/{image.json()['id']}",
        headers=_auth(client_tokens.access_token),
    )
    selection = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"material_id": material.json()["id"], "price_tiyin": 250000, "min_stock": 1},
    )
    visible_image = await client.get(
        f"/api/v1/files/{image.json()['id']}",
        headers=_auth(client_tokens.access_token),
    )
    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/{selection.json()['id']}/deactivate",
        headers=_auth(owner_access),
    )
    hidden_after_deactivate = await client.get(
        f"/api/v1/files/{image.json()['id']}",
        headers=_auth(client_tokens.access_token),
    )

    assert image.status_code == 200
    assert material.status_code == 201
    assert hidden_image.status_code == 403
    assert selection.status_code == 201
    assert visible_image.status_code == 200
    assert visible_image.content == b"material-image"
    assert hidden_after_deactivate.status_code == 403


async def test_platform_materials_list_reports_branch_usage_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # AB-22: the platform materials list reports how many distinct branches carry
    # each material — 0 before any branch selects it, 1 after one branch does.
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    _, material_id = await _create_catalog_material(client, platform_access)

    before = await client.get("/api/v1/platform/catalog/materials", headers=_auth(platform_access))
    assert before.status_code == 200
    row_before = next(m for m in before.json() if m["id"] == material_id)
    assert row_before["branch_usage_count"] == 0

    selection = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"material_id": material_id, "price_tiyin": 25_500_000, "min_stock": 2},
    )
    assert selection.status_code == 201

    after = await client.get("/api/v1/platform/catalog/materials", headers=_auth(platform_access))
    row_after = next(m for m in after.json() if m["id"] == material_id)
    assert row_after["branch_usage_count"] == 1


async def test_platform_materials_list_paginates_with_limit_offset(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # The platform catalog freezes the admin table once it holds hundreds of rows,
    # so the list opts into the house limit/offset paging: a bare-list page whose
    # slices line up with the full ordered list, and the client stops when a page
    # comes back short. Omitting limit still returns the whole list (unchanged).
    platform_access = await _platform_access(db_session)
    headers = _auth(platform_access)
    for _ in range(5):
        await _create_catalog_material(client, platform_access)

    full = await client.get("/api/v1/platform/catalog/materials", headers=headers)
    assert full.status_code == 200
    all_ids = [row["id"] for row in full.json()]
    assert len(all_ids) == 5

    first = await client.get("/api/v1/platform/catalog/materials?limit=2", headers=headers)
    assert first.status_code == 200
    assert [row["id"] for row in first.json()] == all_ids[:2]

    second = await client.get(
        "/api/v1/platform/catalog/materials?limit=2&offset=2", headers=headers
    )
    assert [row["id"] for row in second.json()] == all_ids[2:4]

    last = await client.get("/api/v1/platform/catalog/materials?limit=2&offset=4", headers=headers)
    assert [row["id"] for row in last.json()] == all_ids[4:]
    assert len(last.json()) == 1  # short page → the client knows there is no more

    # Bounds are enforced by the query params (ge=1, le=200).
    too_small = await client.get("/api/v1/platform/catalog/materials?limit=0", headers=headers)
    assert too_small.status_code == 422
    too_large = await client.get("/api/v1/platform/catalog/materials?limit=201", headers=headers)
    assert too_large.status_code == 422


async def test_workshop_material_lists_paginate(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Both workshop material lists page the same way: the add-material picker caps
    # how many catalog options it returns, and a branch's carried-materials list
    # slices deterministically so its "load more" button can append.
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    owner_headers = _auth(owner_access)
    material_ids: list[str] = []
    for _ in range(3):
        _, material_id = await _create_catalog_material(client, platform_access)
        material_ids.append(material_id)

    picker_page = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/materials?limit=2",
        headers=owner_headers,
    )
    assert picker_page.status_code == 200
    assert len(picker_page.json()) == 2

    for material_id in material_ids:
        carried = await client.post(
            f"/api/v1/workshop/branches/{branch_id}/materials",
            headers=owner_headers,
            json={"material_id": material_id, "price_tiyin": 1_000_000, "min_stock": 1},
        )
        assert carried.status_code == 201

    full = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials", headers=owner_headers
    )
    assert full.status_code == 200
    carried_ids = [row["material"]["id"] for row in full.json()]
    assert len(carried_ids) == 3

    first = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?limit=2", headers=owner_headers
    )
    assert [row["material"]["id"] for row in first.json()] == carried_ids[:2]
    second = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?limit=2&offset=2", headers=owner_headers
    )
    assert [row["material"]["id"] for row in second.json()] == carried_ids[2:]


async def _create_material(
    client: AsyncClient,
    access: str,
    *,
    manufacturer_id: str,
    thickness_mm: str = "18",
    color: str | None = None,
    kind: str = "panel",
) -> str:
    body: dict[str, object] = {
        "kind": kind,
        "manufacturer_id": manufacturer_id,
        "thickness_mm": thickness_mm,
        "color": color or f"Colour {uuid.uuid4().hex[:6]}",
    }
    if kind == "panel":
        body |= {
            "type": "dsp",
            "panel_length_mm": 2800,
            "panel_width_mm": 2070,
            "grain_direction": True,
        }
    else:
        body |= {"edge_width_mm": 22}
    created = await client.post(
        "/api/v1/platform/catalog/materials", headers=_auth(access), json=body
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def test_branch_catalog_picker_filters_exclude_attached_and_report_total(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    owner_headers = _auth(owner_access)
    manufacturer_id, first_material_id = await _create_catalog_material(client, platform_access)
    other_manufacturer = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(platform_access),
        json={"name": f"Kronospan {uuid.uuid4().hex[:6]}"},
    )
    other_manufacturer_id = str(other_manufacturer.json()["id"])
    thin_panel = await _create_material(
        client, platform_access, manufacturer_id=manufacturer_id, thickness_mm="16"
    )
    edge = await _create_material(
        client, platform_access, manufacturer_id=other_manufacturer_id, kind="edge"
    )

    everything = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/materials", headers=owner_headers
    )
    assert everything.status_code == 200
    assert everything.json()["total"] == 3
    assert {row["material"]["id"] for row in everything.json()["items"]} == {
        first_material_id,
        thin_panel,
        edge,
    }

    by_manufacturer = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/materials"
        f"?manufacturer_id={manufacturer_id}",
        headers=owner_headers,
    )
    assert by_manufacturer.json()["total"] == 2
    by_thickness = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/materials?thickness_mm=16",
        headers=owner_headers,
    )
    assert [row["material"]["id"] for row in by_thickness.json()["items"]] == [thin_panel]
    by_kind = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/materials?kind=edge",
        headers=owner_headers,
    )
    assert [row["material"]["id"] for row in by_kind.json()["items"]] == [edge]

    # The total counts the whole filtered set, not the requested page — the
    # picker's "Filtrdagi hammasi (N)" master checkbox depends on that.
    first_page = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/materials?limit=1", headers=owner_headers
    )
    assert first_page.json()["total"] == 3
    assert len(first_page.json()["items"]) == 1

    facets = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/filters", headers=owner_headers
    )
    assert facets.status_code == 200
    assert {row["id"] for row in facets.json()["manufacturers"]} == {
        manufacturer_id,
        other_manufacturer_id,
    }
    assert facets.json()["thicknesses"] == ["16", "18"]

    attached = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=owner_headers,
        json={"material_id": first_material_id, "price_tiyin": 500_000, "min_stock": 5},
    )
    assert attached.status_code == 201
    after = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/materials", headers=owner_headers
    )
    assert after.json()["total"] == 2
    assert first_material_id not in {row["material"]["id"] for row in after.json()["items"]}


async def test_branch_materials_bulk_attach_is_atomic_and_skips_races(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    owner_headers = _auth(owner_access)
    manufacturer_id, panel_id = await _create_catalog_material(client, platform_access)
    edge_id = await _create_material(
        client, platform_access, manufacturer_id=manufacturer_id, kind="edge"
    )
    spare_id = await _create_material(client, platform_access, manufacturer_id=manufacturer_id)

    # A single invalid row rejects the whole batch and names the offender.
    rejected = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/bulk",
        headers=owner_headers,
        json={
            "items": [
                {"material_id": panel_id, "price_tiyin": 500_000, "min_stock": 5},
                {"material_id": edge_id, "price_tiyin": 0, "min_stock": 50_000},
            ]
        },
    )
    assert rejected.status_code == 400
    body = rejected.json()
    assert body["code"] == "invalid_price"
    assert "Kromka" in body["message"]
    assert (
        await db_session.scalar(
            select(func.count(BranchMaterial.id)).where(BranchMaterial.branch_id == branch_id)
        )
        == 0
    )

    created = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/bulk",
        headers=owner_headers,
        json={
            "items": [
                {"material_id": panel_id, "price_tiyin": 500_000, "min_stock": 5},
                {"material_id": edge_id, "price_tiyin": 12_000, "min_stock": 50_000},
                {"material_id": spare_id, "price_tiyin": 700_000, "min_stock": 5},
            ]
        },
    )
    assert created.status_code == 201
    assert created.json()["skipped_material_ids"] == []
    assert {row["material_id"] for row in created.json()["created"]} == {
        panel_id,
        edge_id,
        spare_id,
    }
    # Each attach creates the branch's stock item carrying the same threshold.
    edge_stock = await db_session.scalar(
        select(StockItem).where(
            StockItem.branch_id == branch_id,
            StockItem.material_id == uuid.UUID(edge_id),
        )
    )
    assert edge_stock is not None
    assert edge_stock.min_stock == 50_000

    # A material a concurrent attach already linked is skipped, not an error.
    replayed = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/bulk",
        headers=owner_headers,
        json={"items": [{"material_id": panel_id, "price_tiyin": 900_000, "min_stock": 9}]},
    )
    assert replayed.status_code == 201
    assert replayed.json()["created"] == []
    assert replayed.json()["skipped_material_ids"] == [panel_id]
    unchanged = await db_session.scalar(
        select(BranchMaterial.price_tiyin).where(
            BranchMaterial.branch_id == branch_id,
            BranchMaterial.material_id == uuid.UUID(panel_id),
        )
    )
    assert unchanged == 500_000

    empty = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/bulk",
        headers=owner_headers,
        json={"items": []},
    )
    assert empty.status_code == 400
    assert empty.json()["code"] == "branch_materials_empty"
