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
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


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


PANEL_FORMAT = {"qalinlik_mm": "18", "uzunlik_mm": 2800, "eni_mm": 2070}
KROMKA_FORMAT = {"qalinlik_mm": "2", "kromka_eni_mm": 19}


async def _create_manufacturer(client: AsyncClient, access: str, name: str | None = None) -> str:
    created = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(access),
        json={"name": name or f"Egger {uuid.uuid4().hex[:6]}", "country": "AT"},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def _create_dekor(
    client: AsyncClient,
    access: str,
    *,
    manufacturer_id: str,
    tur: str = "ldsp",
    kod: str | None = "H1334",
    nomi: str | None = None,
    tolali: bool = True,
    image_file_id: str | None = None,
) -> str:
    """Create one platform dekor — identity only, never a format or a price."""
    body: dict[str, object] = {
        "manufacturer_id": manufacturer_id,
        "tur": tur,
        "kod": kod,
        "nomi": nomi or f"Colour {uuid.uuid4().hex[:6]}",
        "tolali": tolali,
    }
    if image_file_id is not None:
        body["image_file_id"] = image_file_id
    created = await client.post(
        "/api/v1/platform/catalog/dekorlar", headers=_auth(access), json=body
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def _create_catalog_dekor(client: AsyncClient, access: str) -> tuple[str, str]:
    """A fresh manufacturer plus one panel-shaped dekor of it."""
    manufacturer_id = await _create_manufacturer(client, access)
    dekor_id = await _create_dekor(
        client, access, manufacturer_id=manufacturer_id, nomi="Light oak"
    )
    return manufacturer_id, dekor_id


async def _attach(
    client: AsyncClient,
    access: str,
    branch_id: uuid.UUID,
    dekor_id: str,
    *,
    formats: list[dict[str, object]] | None = None,
    price_tiyin: int | None = None,
    min_stock: int | None = None,
) -> Response:
    """POST the batch-attach body. Defaults to a single standard panel format."""
    if formats is None:
        fmt: dict[str, object] = dict(PANEL_FORMAT)
        if price_tiyin is not None:
            fmt["price_tiyin"] = price_tiyin
        if min_stock is not None:
            fmt["min_stock"] = min_stock
        formats = [fmt]
    return await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(access),
        json={"items": [{"dekor_id": dekor_id, "formats": formats}]},
    )


async def _attach_one(
    client: AsyncClient,
    access: str,
    branch_id: uuid.UUID,
    dekor_id: str,
    *,
    formats: list[dict[str, object]] | None = None,
    price_tiyin: int | None = None,
    min_stock: int | None = None,
) -> dict[str, object]:
    """Attach a single format and return the one created branch material."""
    response = await _attach(
        client,
        access,
        branch_id,
        dekor_id,
        formats=formats,
        price_tiyin=price_tiyin,
        min_stock=min_stock,
    )
    assert response.status_code == 201, response.text
    created = response.json()["created"]
    assert len(created) == 1, created
    row: dict[str, object] = created[0]
    return row


async def test_platform_catalog_crud_and_branch_material_stock_row(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    manufacturer_id, dekor_id = await _create_catalog_dekor(client, platform_access)
    second_manufacturer_id = await _create_manufacturer(
        client, platform_access, f"Kronospan {uuid.uuid4().hex[:6]}"
    )
    second_dekor_id = await _create_dekor(
        client,
        platform_access,
        manufacturer_id=second_manufacturer_id,
        tur="mdf",
        kod="MDF-W",
        nomi="White",
        tolali=False,
    )
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
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar",
        headers=_auth(owner_access),
    )
    branch_material = await _attach_one(
        client, owner_access, branch_id, dekor_id, price_tiyin=25500000, min_stock=2
    )
    second_branch_material = await _attach(
        client, owner_access, branch_id, second_dekor_id, price_tiyin=18800000, min_stock=1
    )
    stock_item = await db_session.scalar(
        select(StockItem).where(
            StockItem.branch_id == branch_id,
            StockItem.branch_material_id == uuid.UUID(str(branch_material["id"])),
        )
    )
    assert stock_item is not None
    assert stock_item.on_hand == 0
    # The threshold is NOT mirrored here — `stock_items` is only the balance.
    # The value the operator typed lives once, on the branch material.
    assert not hasattr(stock_item, "min_stock")
    assert branch_material["min_stock"] == 2

    edited = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{branch_material['id']}",
        headers=_auth(owner_access),
        json={"min_stock": 4},
    )
    manufacturer_filter = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?manufacturer_id={manufacturer_id}",
        headers=_auth(owner_access),
    )
    tur_filter = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?tur=mdf",
        headers=_auth(owner_access),
    )
    picker_tur_filter = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar?tur=ldsp",
        headers=_auth(owner_access),
    )

    assert duplicate.status_code == 409
    assert picker.status_code == 200
    assert picker.json()["items"][0]["dekor"]["id"] == dekor_id
    assert picker.json()["total"] == len(picker.json()["items"])
    assert second_branch_material.status_code == 201
    assert branch_material["min_stock"] == 2
    assert edited.status_code == 200
    # Editing the threshold is a single write to the branch material — there is
    # no second copy to propagate to, which is the point of dropping the mirror.
    assert edited.json()["min_stock"] == 4
    assert manufacturer_filter.status_code == 200
    assert [row["dekor"]["id"] for row in manufacturer_filter.json()] == [dekor_id]
    assert tur_filter.status_code == 200
    assert [row["dekor"]["id"] for row in tur_filter.json()] == [second_dekor_id]
    # The picker hides nothing now: carrying an 18 mm sheet of a dekor must not
    # stop the operator adding the 16 mm one. The attached dekor is still listed,
    # with the count of formats already carried.
    assert picker_tur_filter.status_code == 200
    assert [row["dekor"]["id"] for row in picker_tur_filter.json()["items"]] == [dekor_id]
    assert picker_tur_filter.json()["items"][0]["carried_format_count"] == 1


async def test_format_shape_validation_and_non_platform_rejection(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The panel/tape shape rule moved to attach time, where the format is typed.

    A dekor carries no dimensions at all now, so there is nothing to reject on
    the platform surface — the shape rule fires when a branch says what format
    its supplier sells. The DB cannot express it (`tur` lives on `dekorlar`), so
    these are service-layer 400s, not IntegrityErrors.
    """
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    manufacturer_id, panel_dekor_id = await _create_catalog_dekor(client, platform_access)
    kromka_dekor_id = await _create_dekor(
        client, platform_access, manufacturer_id=manufacturer_id, tur="kromka", nomi="Oak"
    )

    kromka_without_width = await _attach(
        client, owner_access, branch_id, kromka_dekor_id, formats=[{"qalinlik_mm": "0.4"}]
    )
    kromka_with_panel_size = await _attach(
        client, owner_access, branch_id, kromka_dekor_id, formats=[PANEL_FORMAT]
    )
    panel_without_size = await _attach(
        client, owner_access, branch_id, panel_dekor_id, formats=[{"qalinlik_mm": "18"}]
    )
    panel_with_kromka_width = await _attach(
        client, owner_access, branch_id, panel_dekor_id, formats=[KROMKA_FORMAT]
    )
    zero_thickness = await _attach(
        client,
        owner_access,
        branch_id,
        panel_dekor_id,
        formats=[{**PANEL_FORMAT, "qalinlik_mm": "0"}],
    )
    forbidden = await client.get(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(owner_access),
    )

    assert kromka_without_width.status_code == 400
    assert kromka_without_width.json()["code"] == "invalid_kromka_format"
    assert kromka_with_panel_size.status_code == 400
    assert kromka_with_panel_size.json()["code"] == "invalid_kromka_format"
    assert panel_without_size.status_code == 400
    assert panel_without_size.json()["code"] == "invalid_panel_format"
    assert panel_with_kromka_width.status_code == 400
    assert panel_with_kromka_width.json()["code"] == "invalid_panel_format"
    assert zero_thickness.status_code == 400
    assert zero_thickness.json()["code"] == "invalid_thickness"
    assert forbidden.status_code == 403
    # Nothing partially landed: one bad row rejects the whole batch.
    assert (
        await db_session.scalar(
            select(func.count(BranchMaterial.id)).where(BranchMaterial.branch_id == branch_id)
        )
        == 0
    )


async def test_panel_orientation_is_normalized_not_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """`1830x2750` and `2750x1830` are the same sheet.

    The unique index compares the columns literally, so an un-normalized second
    attach would slip past it and give the branch two rows for one format.
    """
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    _, dekor_id = await _create_catalog_dekor(client, platform_access)

    swapped = await _attach_one(
        client,
        owner_access,
        branch_id,
        dekor_id,
        formats=[{"qalinlik_mm": "18", "uzunlik_mm": 1830, "eni_mm": 2750}],
    )
    assert swapped["uzunlik_mm"] == 2750
    assert swapped["eni_mm"] == 1830

    replay = await _attach(
        client,
        owner_access,
        branch_id,
        dekor_id,
        formats=[{"qalinlik_mm": "18", "uzunlik_mm": 2750, "eni_mm": 1830}],
    )
    assert replay.status_code == 201
    assert replay.json()["created"] == []
    assert [key["uzunlik_mm"] for key in replay.json()["skipped"]] == [2750]


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
    for key in ["active_orders_count", "material_count", "low_stock_count", "staff_count"]:
        assert key not in created.json()
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
    _, dekor_id = await _create_catalog_dekor(client, platform_access)
    material = await _attach_one(
        client, owner_access, branch_id, dekor_id, price_tiyin=100000, min_stock=2
    )
    branch_material_id = material["id"]
    stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "branch_material_id": branch_material_id,
            "quantity": 3,
            "unit_price_tiyin": 51500000,
            "supplier": {"name": "Wood Supplier"},
        },
    )
    adjustment = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-adjustments",
        headers=_auth(owner_access),
        json={"branch_material_id": branch_material_id, "quantity": -1, "note": "Stock take"},
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
    # Stock movement raises no notification of its own any more: low stock is a
    # badge on the Ombor row, not a bell entry (QAD-182). Only a balance that
    # actually went negative still notifies.
    assert notification_count == 0
    assert supplier_count == 1
    assert transaction_count == 2
    assert action_count >= 3


async def test_branch_scoped_staff_authorization(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, workshop_id, branch_id, _ = await _owner_fixture(db_session)
    _, dekor_id = await _create_catalog_dekor(client, platform_access)
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

    add_material = await _attach_one(
        client, catalog_staff, branch_id, dekor_id, price_tiyin=150000, min_stock=1
    )
    branch_material_id = add_material["id"]
    catalog_stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(catalog_staff),
        json={
            "branch_material_id": branch_material_id,
            "quantity": 1,
            "unit_price_tiyin": 100000,
            "supplier": {"name": "Nope"},
        },
    )
    inventory_edit_catalog = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{branch_material_id}",
        headers=_auth(inventory_staff),
        json={"min_stock": 3},
    )
    inventory_stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(inventory_staff),
        json={
            "branch_material_id": branch_material_id,
            "quantity": 2,
            "unit_price_tiyin": 100000,
            "supplier": {"name": "Allowed"},
        },
    )
    # Re-attaching the same (dekor, format) is a skip, not a 409: the picker
    # shows what is carried, so a repeat is a race rather than user error.
    duplicate_owner_add = await _attach(
        client, owner_access, branch_id, dekor_id, price_tiyin=150000, min_stock=1
    )
    deactivated = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/{branch_material_id}/deactivate",
        headers=_auth(owner_access),
    )
    stock_in_after_deactivate = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(inventory_staff),
        json={
            "branch_material_id": branch_material_id,
            "quantity": 1,
            "unit_price_tiyin": 100000,
            "supplier": {"name": "After deactivate"},
        },
    )

    assert catalog_stock_in.status_code == 403
    assert inventory_edit_catalog.status_code == 403
    assert inventory_stock_in.status_code == 201
    assert duplicate_owner_add.status_code == 201
    assert duplicate_owner_add.json()["created"] == []
    assert len(duplicate_owner_add.json()["skipped"]) == 1
    assert deactivated.status_code == 200
    assert stock_in_after_deactivate.status_code == 201


async def test_supplier_list_is_readable_by_finance_but_writable_only_by_inventory(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """QAD-169: the expense form attributes spending to a supplier, so the
    accountant must be able to read the names. Only the read opens up."""
    owner_access, workshop_id, branch_id, _ = await _owner_fixture(db_session)
    finance_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_FINANCE,
    )
    catalog_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    created = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(owner_access),
        json={"name": "Panel Trade MChJ", "phone": "+998712300010"},
    )
    assert created.status_code == 201

    finance_read = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(finance_staff),
    )
    finance_write = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(finance_staff),
        json={"name": "Not mine to add"},
    )
    catalog_read = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(catalog_staff),
    )

    assert finance_read.status_code == 200
    assert [row["name"] for row in finance_read.json()] == ["Panel Trade MChJ"]
    assert finance_write.status_code == 403
    assert catalog_read.status_code == 403


async def test_stock_in_pricing_math_last_price_and_validation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    manufacturer_id, panel_dekor_id = await _create_catalog_dekor(client, platform_access)
    edge_dekor_id = await _create_dekor(
        client,
        platform_access,
        manufacturer_id=manufacturer_id,
        tur="kromka",
        kod="H1334",
        nomi="Light oak",
    )
    unpriced_dekor_id = await _create_dekor(
        client,
        platform_access,
        manufacturer_id=manufacturer_id,
        tur="kromka",
        kod=None,
        nomi="White",
    )
    panel_id = (
        await _attach_one(
            client, owner_access, branch_id, panel_dekor_id, price_tiyin=100000, min_stock=0
        )
    )["id"]
    edge_id = (
        await _attach_one(
            client,
            owner_access,
            branch_id,
            edge_dekor_id,
            formats=[{**KROMKA_FORMAT, "price_tiyin": 100000}],
        )
    )["id"]
    unpriced_id = (
        await _attach_one(
            client,
            owner_access,
            branch_id,
            unpriced_dekor_id,
            formats=[{"qalinlik_mm": "0.4", "kromka_eni_mm": 19, "price_tiyin": 100000}],
        )
    )["id"]

    first = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "branch_material_id": panel_id,
            "quantity": 20,
            "unit_price_tiyin": 51500000,
            "supplier": {"name": "Panel Trade"},
        },
    )
    assert first.status_code == 201, first.text
    first_supplier_id = first.json()["supplier_id"]
    second = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "branch_material_id": panel_id,
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
            "branch_material_id": edge_id,
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
        json={"branch_material_id": panel_id, "quantity": 1, "supplier_id": first_supplier_id},
    )
    negative_price = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "branch_material_id": panel_id,
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
    _, dekor_id = await _create_catalog_dekor(client, platform_access)
    material = await _attach_one(
        client, owner_access, branch_id, dekor_id, price_tiyin=250000, min_stock=5
    )
    branch_material_id = material["id"]
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
        f"/api/v1/workshop/branches/{branch_id}/materials/{branch_material_id}/deactivate",
        headers=_auth(owner_access),
    )
    hidden = await client.get(
        f"/api/v1/client/branches/{branch_id}/materials",
        headers=_auth(tokens.access_token),
    )

    assert branches.status_code == 200
    branch_row = branches.json()[0]
    assert branch_row["branch_id"] == str(branch_id)
    # The client branch page publishes the full contact block: address, the
    # primary number, and the extras (QAD-158).
    assert branch_row["address"]
    assert branch_row["phone"]
    assert branch_row["additional_phones"] == []
    assert materials.status_code == 200
    listed = materials.json()[0]
    # The client sees the BRANCH material — the format it can actually order —
    # with the dekor's identity flattened onto it, never the platform dekor id.
    assert listed["id"] == branch_material_id
    assert listed["price_tiyin"] == 250000
    assert listed["qalinlik_mm"] == "18"
    assert listed["uzunlik_mm"] == 2800
    assert listed["eni_mm"] == 2070
    assert listed["kromka_eni_mm"] is None
    assert listed["nomi"] == "Light oak"
    assert listed["tur"] == "ldsp"
    assert "on_hand" not in listed
    assert "supplier_id" not in listed
    assert "min_stock" not in listed
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
    manufacturer_id, _ = await _create_catalog_dekor(client, platform_access)
    image = await client.post(
        "/api/v1/files",
        headers=_auth(platform_access),
        files={"upload": ("material.png", b"material-image", "image/png")},
    )
    # One photo serves every format of the dekor, so visibility is a dekor-level
    # question answered by "does any branch the client can see carry it".
    image_dekor_id = await _create_dekor(
        client,
        platform_access,
        manufacturer_id=manufacturer_id,
        kod=None,
        nomi="White",
        image_file_id=image.json()["id"],
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
    selection = await _attach_one(
        client, owner_access, branch_id, image_dekor_id, price_tiyin=250000, min_stock=1
    )
    visible_image = await client.get(
        f"/api/v1/files/{image.json()['id']}",
        headers=_auth(client_tokens.access_token),
    )
    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/{selection['id']}/deactivate",
        headers=_auth(owner_access),
    )
    hidden_after_deactivate = await client.get(
        f"/api/v1/files/{image.json()['id']}",
        headers=_auth(client_tokens.access_token),
    )

    assert image.status_code == 200
    assert hidden_image.status_code == 403
    assert visible_image.status_code == 200
    assert visible_image.content == b"material-image"
    assert hidden_after_deactivate.status_code == 403


async def test_platform_dekorlar_list_reports_branch_usage_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # AB-22: the platform dekor list reports how many distinct branches carry any
    # format of the dekor — 0 before any branch attaches one, 1 after.
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    _, dekor_id = await _create_catalog_dekor(client, platform_access)

    before = await client.get("/api/v1/platform/catalog/dekorlar", headers=_auth(platform_access))
    assert before.status_code == 200
    row_before = next(m for m in before.json() if m["id"] == dekor_id)
    assert row_before["branch_usage_count"] == 0

    # Two formats of the SAME dekor in ONE branch is still one branch using it.
    attached = await _attach(
        client,
        owner_access,
        branch_id,
        dekor_id,
        formats=[
            {**PANEL_FORMAT, "price_tiyin": 25_500_000, "min_stock": 2},
            {**PANEL_FORMAT, "qalinlik_mm": "16", "price_tiyin": 20_000_000},
        ],
    )
    assert attached.status_code == 201
    assert len(attached.json()["created"]) == 2

    after = await client.get("/api/v1/platform/catalog/dekorlar", headers=_auth(platform_access))
    row_after = next(m for m in after.json() if m["id"] == dekor_id)
    assert row_after["branch_usage_count"] == 1


async def test_platform_dekorlar_list_paginates_with_limit_offset(
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
        await _create_catalog_dekor(client, platform_access)

    full = await client.get("/api/v1/platform/catalog/dekorlar", headers=headers)
    assert full.status_code == 200
    all_ids = [row["id"] for row in full.json()]
    assert len(all_ids) == 5

    first = await client.get("/api/v1/platform/catalog/dekorlar?limit=2", headers=headers)
    assert first.status_code == 200
    assert [row["id"] for row in first.json()] == all_ids[:2]

    second = await client.get("/api/v1/platform/catalog/dekorlar?limit=2&offset=2", headers=headers)
    assert [row["id"] for row in second.json()] == all_ids[2:4]

    last = await client.get("/api/v1/platform/catalog/dekorlar?limit=2&offset=4", headers=headers)
    assert [row["id"] for row in last.json()] == all_ids[4:]
    assert len(last.json()) == 1  # short page → the client knows there is no more

    # Bounds are enforced by the query params (ge=1, le=200).
    too_small = await client.get("/api/v1/platform/catalog/dekorlar?limit=0", headers=headers)
    assert too_small.status_code == 422
    too_large = await client.get("/api/v1/platform/catalog/dekorlar?limit=201", headers=headers)
    assert too_large.status_code == 422


async def test_workshop_material_lists_paginate(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Both workshop lists page the same way: the attach picker caps how many
    # dekor options it returns, and a branch's carried-formats list slices
    # deterministically so its "load more" button can append.
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    owner_headers = _auth(owner_access)
    dekor_ids: list[str] = []
    for _ in range(3):
        _, dekor_id = await _create_catalog_dekor(client, platform_access)
        dekor_ids.append(dekor_id)

    picker_page = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar?limit=2",
        headers=owner_headers,
    )
    assert picker_page.status_code == 200
    assert len(picker_page.json()["items"]) == 2
    assert picker_page.json()["total"] == 3

    for dekor_id in dekor_ids:
        await _attach_one(
            client, owner_access, branch_id, dekor_id, price_tiyin=1_000_000, min_stock=1
        )

    full = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials", headers=owner_headers
    )
    assert full.status_code == 200
    carried_ids = [row["id"] for row in full.json()]
    assert len(carried_ids) == 3

    first = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?limit=2", headers=owner_headers
    )
    assert [row["id"] for row in first.json()] == carried_ids[:2]
    second = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?limit=2&offset=2", headers=owner_headers
    )
    assert [row["id"] for row in second.json()] == carried_ids[2:]


async def test_branch_catalog_picker_keeps_attached_dekorlar_and_reports_total(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The picker hides nothing: a second format of a carried dekor must stay addable.

    Thickness is no longer a facet — it is a per-branch value the operator types,
    so there is nothing to enumerate. `tur` is a fixed enum the client renders.
    """
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    owner_headers = _auth(owner_access)
    manufacturer_id, first_dekor_id = await _create_catalog_dekor(client, platform_access)
    other_manufacturer_id = await _create_manufacturer(
        client, platform_access, f"Kronospan {uuid.uuid4().hex[:6]}"
    )
    second_panel = await _create_dekor(
        client, platform_access, manufacturer_id=manufacturer_id, kod="H3303"
    )
    edge = await _create_dekor(
        client, platform_access, manufacturer_id=other_manufacturer_id, tur="kromka"
    )

    everything = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar", headers=owner_headers
    )
    assert everything.status_code == 200
    assert everything.json()["total"] == 3
    assert {row["dekor"]["id"] for row in everything.json()["items"]} == {
        first_dekor_id,
        second_panel,
        edge,
    }

    by_manufacturer = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar?manufacturer_id={manufacturer_id}",
        headers=owner_headers,
    )
    assert by_manufacturer.json()["total"] == 2
    by_tur = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar?tur=kromka",
        headers=owner_headers,
    )
    assert [row["dekor"]["id"] for row in by_tur.json()["items"]] == [edge]

    # The total counts the whole filtered set, not the requested page — the
    # picker's "Filtrdagi hammasi (N)" master checkbox depends on that.
    first_page = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar?limit=1", headers=owner_headers
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
    assert "thicknesses" not in facets.json()

    await _attach_one(
        client, owner_access, branch_id, first_dekor_id, price_tiyin=500_000, min_stock=5
    )
    after = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar", headers=owner_headers
    )
    assert after.json()["total"] == 3
    attached_row = next(
        row for row in after.json()["items"] if row["dekor"]["id"] == first_dekor_id
    )
    assert attached_row["carried_format_count"] == 1


async def test_attach_spans_dekorlar_of_different_turlar_in_one_transaction(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The real onboarding shape: many dekorlar, each in its own o'lcham axis.

    87% of carried dekorlar exist in exactly one o'lcham, so a branch registering
    its supplier list picks many dekorlar at once. A board and its matching kromka
    have different o'lcham axes (panel size vs tape width) and must still land in
    one save — that is why the request is a list of per-dekor items.
    """
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    manufacturer_id = await _create_manufacturer(client, platform_access)
    panel_a = await _create_dekor(
        client, platform_access, manufacturer_id=manufacturer_id, kod="P-A", nomi="Oak A"
    )
    panel_b = await _create_dekor(
        client, platform_access, manufacturer_id=manufacturer_id, kod="P-B", nomi="Oak B"
    )
    tape = await _create_dekor(
        client,
        platform_access,
        manufacturer_id=manufacturer_id,
        tur="kromka",
        kod="P-A",
        nomi="Oak A",
        tolali=False,
    )

    created = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "items": [
                {"dekor_id": panel_a, "formats": [dict(PANEL_FORMAT)]},
                {"dekor_id": panel_b, "formats": [dict(PANEL_FORMAT)]},
                {"dekor_id": tape, "formats": [dict(KROMKA_FORMAT)]},
            ]
        },
    )
    assert created.status_code == 201, created.text
    rows = created.json()["created"]
    assert len(rows) == 3
    assert {row["dekor"]["id"] for row in rows} == {panel_a, panel_b, tape}
    # Each row took the o'lcham axis of its own dekor's tur.
    by_dekor = {row["dekor"]["id"]: row for row in rows}
    assert by_dekor[panel_a]["uzunlik_mm"] == 2800
    assert by_dekor[panel_a]["kromka_eni_mm"] is None
    assert by_dekor[tape]["kromka_eni_mm"] == 19
    assert by_dekor[tape]["uzunlik_mm"] is None

    # Atomic across dekorlar: one bad o'lcham anywhere in the batch writes nothing.
    before = await db_session.scalar(
        select(func.count(BranchMaterial.id)).where(BranchMaterial.branch_id == branch_id)
    )
    rejected = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "items": [
                {
                    "dekor_id": panel_a,
                    "formats": [{"qalinlik_mm": "16", "uzunlik_mm": 2750, "eni_mm": 1830}],
                },
                # A panel dekor given a tape o'lcham — invalid for its tur.
                {"dekor_id": panel_b, "formats": [dict(KROMKA_FORMAT)]},
            ]
        },
    )
    assert rejected.status_code == 400, rejected.text
    after = await db_session.scalar(
        select(func.count(BranchMaterial.id)).where(BranchMaterial.branch_id == branch_id)
    )
    assert after == before

    # A skip names the dekor it belongs to, since a batch spans several.
    replayed = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"items": [{"dekor_id": panel_a, "formats": [dict(PANEL_FORMAT)]}]},
    )
    assert replayed.status_code == 201
    assert replayed.json()["created"] == []
    assert [row["dekor_id"] for row in replayed.json()["skipped"]] == [panel_a]


async def test_branch_materials_attach_is_atomic_and_skips_races(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    _, panel_dekor_id = await _create_catalog_dekor(client, platform_access)

    # A single invalid row rejects the whole batch and names the offender.
    rejected = await _attach(
        client,
        owner_access,
        branch_id,
        panel_dekor_id,
        formats=[
            {**PANEL_FORMAT, "price_tiyin": 500_000, "min_stock": 5},
            {**PANEL_FORMAT, "qalinlik_mm": "16", "price_tiyin": -1},
        ],
    )
    assert rejected.status_code == 400
    body = rejected.json()
    assert body["code"] == "invalid_price"
    assert (
        await db_session.scalar(
            select(func.count(BranchMaterial.id)).where(BranchMaterial.branch_id == branch_id)
        )
        == 0
    )

    # Three formats of one dekor in one call — this is what "the batch" means now.
    created = await _attach(
        client,
        owner_access,
        branch_id,
        panel_dekor_id,
        formats=[
            {**PANEL_FORMAT, "price_tiyin": 500_000, "min_stock": 5},
            {**PANEL_FORMAT, "qalinlik_mm": "16", "price_tiyin": 12_000, "min_stock": 50_000},
            {**PANEL_FORMAT, "uzunlik_mm": 2750, "eni_mm": 1830, "price_tiyin": 700_000},
        ],
    )
    assert created.status_code == 201
    assert created.json()["skipped"] == []
    rows = created.json()["created"]
    assert {(row["qalinlik_mm"], row["uzunlik_mm"]) for row in rows} == {
        ("18", 2800),
        ("16", 2800),
        ("18", 2750),
    }
    # Each attach opens the branch's stock row at zero. The threshold is the
    # branch material's alone, so there is nothing on the stock row to compare.
    thin = next(row for row in rows if row["qalinlik_mm"] == "16")
    thin_stock = await db_session.scalar(
        select(StockItem).where(StockItem.branch_material_id == uuid.UUID(str(thin["id"])))
    )
    assert thin_stock is not None
    assert thin_stock.on_hand == 0
    assert thin_stock.branch_id == branch_id
    assert thin["min_stock"] == 50_000

    # A format a concurrent attach already registered is skipped, not an error,
    # and the existing row keeps its price.
    replayed = await _attach(
        client,
        owner_access,
        branch_id,
        panel_dekor_id,
        formats=[{**PANEL_FORMAT, "price_tiyin": 900_000, "min_stock": 9}],
    )
    assert replayed.status_code == 201
    assert replayed.json()["created"] == []
    assert [key["qalinlik_mm"] for key in replayed.json()["skipped"]] == ["18"]
    unchanged = await db_session.scalar(
        select(BranchMaterial.price_tiyin).where(
            BranchMaterial.branch_id == branch_id,
            BranchMaterial.qalinlik_mm == 18,
            BranchMaterial.uzunlik_mm == 2800,
        )
    )
    assert unchanged == 500_000

    empty = await _attach(client, owner_access, branch_id, panel_dekor_id, formats=[])
    assert empty.status_code == 400
    assert empty.json()["code"] == "branch_materials_empty"


async def test_price_is_optional_on_attach_and_flags_the_gap(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A branch registers its whole format list before it knows prices.

    `price_tiyin` used to be required on attach and a 0 was rejected. It now
    defaults to 0, meaning "not priced yet" — the row is flagged `price_unset`
    for staff and dropped entirely from client-facing listings, so an unpriced
    format can never become a free order line.
    """
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id, _ = await _owner_fixture(db_session)
    _, dekor_id = await _create_catalog_dekor(client, platform_access)

    attached = await _attach_one(
        client, owner_access, branch_id, dekor_id, formats=[dict(PANEL_FORMAT)]
    )
    assert attached["price_tiyin"] == 0
    assert attached["price_unset"] is True
    assert attached["min_stock"] == 0

    client_row = Client(phone="+998909999111", name="Client")
    db_session.add(client_row)
    await db_session.flush()
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client_row.id,
    )
    client_view = await client.get(
        f"/api/v1/client/branches/{branch_id}/materials",
        headers=_auth(tokens.access_token),
    )
    assert client_view.status_code == 200
    assert client_view.json() == []

    priced = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{attached['id']}",
        headers=_auth(owner_access),
        json={"price_tiyin": 250_000},
    )
    assert priced.status_code == 200
    assert priced.json()["price_unset"] is False
    now_visible = await client.get(
        f"/api/v1/client/branches/{branch_id}/materials",
        headers=_auth(tokens.access_token),
    )
    assert [row["id"] for row in now_visible.json()] == [attached["id"]]

    negative = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{attached['id']}",
        headers=_auth(owner_access),
        json={"price_tiyin": -1},
    )
    assert negative.status_code == 400
    assert negative.json()["code"] == "invalid_price"
