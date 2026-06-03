import uuid
from datetime import UTC, datetime

from app.core.security import hash_password
from app.models.catalog import BranchMaterial
from app.models.enums import AuthenticatedPrincipalType, Permission, UserStatus
from app.models.identity import Client, PermissionGrant, WorkshopUser
from app.models.inventory import StockItem, StockTransaction, Supplier
from app.models.support import ActionLog, File, Notification
from app.services.files import InMemoryFileStorage, file_storage
from app.services.seed import seed_platform_user, seed_workshop_with_owner
from app.services.sessions import create_session
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


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

    assert duplicate.status_code == 409
    assert picker.status_code == 200
    assert picker.json()[0]["material"]["id"] == material_id
    assert picker.json()[0]["already_selected"] is False
    assert branch_material.status_code == 201
    assert branch_material.json()["min_stock"] == 2
    assert edited.status_code == 200
    assert stock_item.min_stock == 4


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
    assert replacement_settings.status_code == 200
    assert replacement_settings.json()["logo_file_id"] == replacement_logo.json()["id"]
    old_logo = await db_session.get(File, uuid.UUID(logo.json()["id"]))
    assert old_logo is not None
    assert old_logo.entity_type is None
    assert old_logo.entity_id is None
    assert created.status_code == 201
    assert created.json()["working_hours"]["sunday"] == {"open": None, "close": None}
    assert created.json()["active_orders_count"] == 0
    assert bad_hours.status_code == 422
    assert pricing.status_code == 200
    assert pricing.json()["cutting_rate_tiyin"] == 120000
    assert bad_status.status_code == 400
    assert bad_status.json()["code"] == "reason_required"
    assert status_change.status_code == 200
    assert status_change.json()["closed_reason"] == "Renovation"


async def test_inventory_stock_in_adjustment_notifications_and_receipt_access(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    storage = InMemoryFileStorage()
    from app.main import app

    app.dependency_overrides[file_storage] = lambda: storage
    platform_access = await _platform_access(db_session)
    owner_access, workshop_id, branch_id, _ = await _owner_fixture(db_session)
    _, material_id = await _create_catalog_material(client, platform_access)
    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"material_id": material_id, "price_tiyin": 100000, "min_stock": 2},
    )
    receipt = await client.post(
        "/api/v1/files",
        headers=_auth(owner_access),
        files={"upload": ("receipt.pdf", b"receipt", "application/pdf")},
    )
    stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "material_id": material_id,
            "quantity": 3,
            "supplier": {"name": "Wood Supplier"},
            "receipt_file_id": receipt.json()["id"],
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
    owner_receipt = await client.get(
        f"/api/v1/files/{receipt.json()['id']}",
        headers=_auth(owner_access),
    )
    client_row = Client(phone="+998909999999", name="Client")
    db_session.add(client_row)
    await db_session.flush()
    client_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client_row.id,
    )
    leaked_receipt = await client.get(
        f"/api/v1/files/{receipt.json()['id']}",
        headers=_auth(client_tokens.access_token),
    )
    notification_count = await db_session.scalar(select(func.count()).select_from(Notification))
    supplier_count = await db_session.scalar(select(func.count()).select_from(Supplier))
    transaction_count = await db_session.scalar(select(func.count()).select_from(StockTransaction))
    action_count = await db_session.scalar(
        select(func.count()).select_from(ActionLog).where(ActionLog.workshop_id == workshop_id)
    )

    assert stock_in.status_code == 201
    assert stock_in.json()["receipt_file_id"] == receipt.json()["id"]
    assert adjustment.status_code == 201
    assert adjustment.json()["balance_after"] == 2
    assert stock.status_code == 200
    assert stock.json()[0]["on_hand"] == 2
    assert stock.json()[0]["is_low_stock"] is True
    assert transactions.status_code == 200
    assert [row["type"] for row in transactions.json()] == ["adjust", "stock_in"]
    assert owner_receipt.status_code == 200
    assert owner_receipt.content == b"receipt"
    assert leaked_receipt.status_code == 403
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
        json={"material_id": material_id, "quantity": 1, "supplier": {"name": "Nope"}},
    )
    inventory_edit_catalog = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{add_material.json()['id']}",
        headers=_auth(inventory_staff),
        json={"min_stock": 3},
    )
    inventory_stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(inventory_staff),
        json={"material_id": material_id, "quantity": 2, "supplier": {"name": "Allowed"}},
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
        json={"material_id": material_id, "quantity": 1, "supplier": {"name": "After deactivate"}},
    )

    assert add_material.status_code == 201
    assert catalog_stock_in.status_code == 403
    assert inventory_edit_catalog.status_code == 403
    assert inventory_stock_in.status_code == 201
    assert duplicate_owner_add.status_code == 409
    assert deactivated.status_code == 200
    assert stock_in_after_deactivate.status_code == 201


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
