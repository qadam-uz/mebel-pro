import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    Currency,
    CuttingResultStatus,
    MaterialKind,
    OrderStatus,
    PanelMaterialType,
    Permission,
    UserStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, Manufacturer, Material
from app.modules.cutting.contracts import (
    CuttingDraft,
    CuttingPanel,
    CuttingPlacement,
    CuttingResult,
)
from app.modules.sales.contracts import Order
from app.modules.support.contracts import ActionLog
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _client_access(
    db: AsyncSession,
    *,
    phone: str = "+998901111000",
    preferred_branch_id: uuid.UUID | None = None,
) -> tuple[str, Client]:
    client = Client(phone=phone, name="Client", preferred_branch_id=preferred_branch_id)
    db.add(client)
    await db.flush()
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client.id,
    )
    return tokens.access_token, client


async def _platform_access(db: AsyncSession) -> str:
    platform = await seed_platform_user(
        db,
        login=f"platform-{uuid.uuid4().hex[:8]}",
        password_reset_required=False,
    )
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=platform.id,
    )
    return tokens.access_token


async def _workshop_owner_access(
    db: AsyncSession,
) -> tuple[str, uuid.UUID, uuid.UUID, uuid.UUID]:
    workshop, branch, owner = await seed_workshop_with_owner(db)
    owner.password_reset_required = False
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, workshop.id, branch.id, owner.id


async def _staff_access(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    permission: Permission,
) -> str:
    access, _ = await _staff_user_access(
        db,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=permission,
    )
    return access


async def _staff_user_access(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    permission: Permission,
) -> tuple[str, WorkshopUser]:
    staff = WorkshopUser(
        workshop_id=workshop_id,
        login=f"staff-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("StaffTemp123"),
        full_name="Scoped Staff",
        phone="+998901234222",
        is_owner=False,
        home_branch_id=branch_id,
        status=UserStatus.ACTIVE,
        password_reset_required=False,
    )
    db.add(staff)
    await db.flush()
    db.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=permission,
            branch_id=branch_id,
            granted_by_user_id=staff.id,
            granted_at=datetime.now(UTC),
        )
    )
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=staff.id,
    )
    return tokens.access_token, staff


async def _materials(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID | None = None,
) -> tuple[Material, Material, Material]:
    manufacturer = Manufacturer(name=f"Egger {uuid.uuid4().hex[:6]}", country="AT")
    db.add(manufacturer)
    await db.flush()
    panel = Material(
        kind=MaterialKind.PANEL,
        manufacturer_id=manufacturer.id,
        type=PanelMaterialType.DSP,
        name="Oak DSP 18",
        thickness_mm=Decimal("18"),
        color="Oak",
        decor_code="H1334",
        panel_length_mm=600,
        panel_width_mm=400,
        grain_direction=False,
    )
    other_panel = Material(
        kind=MaterialKind.PANEL,
        manufacturer_id=manufacturer.id,
        type=PanelMaterialType.MDF,
        name="White MDF 16",
        thickness_mm=Decimal("16"),
        color="White",
        decor_code="W980",
        panel_length_mm=600,
        panel_width_mm=400,
        grain_direction=True,
    )
    edge = Material(
        kind=MaterialKind.EDGE,
        manufacturer_id=manufacturer.id,
        name="Oak edge 0.4",
        thickness_mm=Decimal("0.4"),
        color="Oak",
        decor_code="H1334",
    )
    db.add_all([panel, other_panel, edge])
    await db.flush()
    if branch_id is not None:
        db.add(
            BranchMaterial(
                branch_id=branch_id,
                material_id=panel.id,
                price_tiyin=250000,
                min_stock=1,
            )
        )
    await db.flush()
    return panel, edge, other_panel


def _parts(panel_id: uuid.UUID, edge_id: uuid.UUID) -> list[dict[str, object]]:
    return [
        {
            "part_ref": "shelf",
            "material_id": str(panel_id),
            "material_source": "shop",
            "length_mm": 220,
            "width_mm": 120,
            "quantity": 2,
            "edge_top": {"material_id": str(edge_id), "source": "shop"},
            "edge_left": {"material_id": str(edge_id), "source": "own"},
        }
    ]


async def test_client_cutting_draft_crud_optimize_choose_and_render(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    access, client_row = await _client_access(db_session, preferred_branch_id=branch_id)

    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    draft_id = created.json()["id"]
    updated = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": _parts(panel.id, edge.id)},
    )
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft_id}/optimize",
        headers=_auth(access),
    )
    results = optimized.json()["results"]
    chosen_result_id = optimized.json()["chosen_result_id"]
    chosen = await client.post(
        f"/api/v1/client/cutting-drafts/{draft_id}/chosen-result",
        headers=_auth(access),
        json={"result_id": chosen_result_id},
    )
    svg = await client.get(
        f"/api/v1/client/cutting-results/{chosen_result_id}/svg",
        headers=_auth(access),
    )
    pdf = await client.get(
        f"/api/v1/client/cutting-results/{chosen_result_id}/pdf",
        headers=_auth(access),
    )
    deleted = await client.delete(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
    )
    action_count = await db_session.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(ActionLog.actor_client_id == client_row.id)
    )

    assert created.status_code == 201
    assert created.json()["preferred_branch_id"] == str(branch_id)
    assert updated.status_code == 200
    assert updated.json()["parts_snapshot"][0]["part_ref"] == "shelf"
    assert optimized.status_code == 200
    assert [row["algorithm_name"] for row in results] == ["cutting-engine-best"]
    assert optimized.json()["chosen_result_id"] in {row["id"] for row in results}
    first_result = results[0]
    assert first_result["parts_snapshot"][0]["quantity"] == 2
    assert str(panel.id) in first_result["material_snapshots"]
    assert first_result["edge_length_shop_by_material"] == {str(edge.id): 440}
    assert first_result["edge_length_own_by_material"] == {str(edge.id): 240}
    assert first_result["edge_consumed_shop_by_material"] == {str(edge.id): 500}
    assert first_result["edge_banded_sides_by_material"] == {str(edge.id): {"shop": 2, "own": 2}}
    assert chosen.status_code == 200
    assert chosen.json()["chosen_result_id"] == chosen_result_id
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in svg.content
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert deleted.status_code == 204
    assert action_count == 5


async def test_cutting_draft_ownership_validation_and_limit(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    panel, edge, _ = await _materials(db_session)
    first_access, first_client = await _client_access(db_session, phone="+998901111001")
    second_access, second_client = await _client_access(db_session, phone="+998901111002")
    draft = await client.post("/api/v1/client/cutting-drafts", headers=_auth(first_access))
    draft_id = draft.json()["id"]

    leaked = await client.get(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(second_access),
    )
    bad_parts = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(first_access),
        json={"parts_snapshot": _parts(edge.id, panel.id)},
    )
    owner_access, _, _, _ = await _workshop_owner_access(db_session)
    workshop_create = await client.post(
        "/api/v1/client/cutting-drafts",
        headers=_auth(owner_access),
    )
    for _ in range(50):
        db_session.add(CuttingDraft(client_id=second_client.id, parts_snapshot=[]))
    await db_session.flush()
    capped = await client.post("/api/v1/client/cutting-drafts", headers=_auth(second_access))

    assert leaked.status_code == 404
    assert bad_parts.status_code == 400
    assert bad_parts.json()["code"] == "invalid_cutting_parts"
    assert bad_parts.json()["details"]["errors"][0]["code"] == "invalid_panel_material"
    assert workshop_create.status_code == 403
    assert capped.status_code == 409
    assert capped.json()["code"] == "draft_limit_exceeded"
    assert first_client.id != second_client.id


async def test_cutting_draft_rejects_duplicate_part_refs(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    panel, edge, _ = await _materials(db_session)
    access, _ = await _client_access(db_session, phone="+998901111010")
    draft = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    parts = _parts(panel.id, edge.id)
    parts.append({**parts[0]})

    response = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft.json()['id']}",
        headers=_auth(access),
        json={"parts_snapshot": parts},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_cutting_parts"
    assert response.json()["details"]["errors"][0]["code"] == "duplicate_part_ref"


async def test_client_cutting_material_picker_marks_branch_carried_materials(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, _, other_panel = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(db_session)

    carried = await client.get(
        f"/api/v1/client/catalog/materials?kind=panel&branch_id={branch_id}",
        headers=_auth(access),
    )
    all_catalog = await client.get(
        f"/api/v1/client/catalog/materials?kind=panel&branch_id={branch_id}&carried_only=false",
        headers=_auth(access),
    )

    assert carried.status_code == 200
    assert [row["id"] for row in carried.json()] == [str(panel.id)]
    assert carried.json()[0]["branch_carried"] is True
    assert carried.json()[0]["price_tiyin"] == 250000
    assert all_catalog.status_code == 200
    assert {row["id"] for row in all_catalog.json()} == {str(panel.id), str(other_panel.id)}
    by_id = {row["id"]: row for row in all_catalog.json()}
    assert by_id[str(other_panel.id)]["branch_carried"] is False
    assert by_id[str(other_panel.id)]["price_tiyin"] is None


async def test_client_catalog_materials_limit_caps_the_no_branch_load(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # CB-40: a no-preferred-branch load can be capped so a fresh draft does not pull
    # the whole catalog; the cap is deterministic (ordered by manufacturer, name).
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, _, other_panel = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(db_session)

    uncapped = await client.get(
        "/api/v1/client/catalog/materials?kind=panel",
        headers=_auth(access),
    )
    capped = await client.get(
        "/api/v1/client/catalog/materials?kind=panel&limit=1",
        headers=_auth(access),
    )
    bad_limit = await client.get(
        "/api/v1/client/catalog/materials?kind=panel&limit=0",
        headers=_auth(access),
    )

    assert uncapped.status_code == 200
    assert {row["id"] for row in uncapped.json()} == {str(panel.id), str(other_panel.id)}
    assert capped.status_code == 200
    assert len(capped.json()) == 1
    assert bad_limit.status_code == 422


async def test_workshop_cutting_plans_are_order_bound_and_branch_scoped(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, workshop_id, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    _, client_row = await _client_access(db_session, phone="+998901111003")
    result = await _confirmed_result(db_session, client_row.id, workshop_id, branch_id, panel, edge)
    scoped_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.VIEW_DASHBOARD,
    )
    catalog_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    client_access, _ = await _client_access(db_session, phone="+998901111004")
    platform_access = await _platform_access(db_session)

    owner_list = await client.get("/api/v1/workshop/cutting-plans", headers=_auth(owner_access))
    staff_detail = await client.get(
        f"/api/v1/workshop/cutting-plans/{result.id}",
        headers=_auth(scoped_staff),
    )
    staff_svg = await client.get(
        f"/api/v1/workshop/cutting-plans/{result.id}/svg",
        headers=_auth(scoped_staff),
    )
    staff_pdf = await client.get(
        f"/api/v1/workshop/cutting-plans/{result.id}/pdf",
        headers=_auth(scoped_staff),
    )
    denied_staff = await client.get(
        f"/api/v1/workshop/cutting-plans/{result.id}",
        headers=_auth(catalog_staff),
    )
    denied_client = await client.get(
        "/api/v1/workshop/cutting-plans",
        headers=_auth(client_access),
    )
    denied_platform = await client.get(
        "/api/v1/workshop/cutting-plans",
        headers=_auth(platform_access),
    )

    assert owner_list.status_code == 200
    assert owner_list.json()[0]["id"] == str(result.id)
    assert staff_detail.status_code == 200
    assert staff_detail.json()["result"]["order_id"] == str(result.order_id)
    assert staff_svg.status_code == 200
    assert b"<svg" in staff_svg.content
    assert staff_pdf.status_code == 200
    assert staff_pdf.content.startswith(b"%PDF")
    assert denied_staff.status_code == 404
    assert denied_client.status_code == 403
    assert denied_platform.status_code == 403


async def test_production_staff_sees_only_assigned_cutting_plans(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, workshop_id, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    _, first_client = await _client_access(db_session, phone="+998901111031")
    _, second_client = await _client_access(db_session, phone="+998901111032")
    assigned_result = await _confirmed_result(
        db_session,
        first_client.id,
        workshop_id,
        branch_id,
        panel,
        edge,
    )
    unassigned_result = await _confirmed_result(
        db_session,
        second_client.id,
        workshop_id,
        branch_id,
        panel,
        edge,
    )
    production_access, worker = await _staff_user_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.PROCESS_PRODUCTION,
    )
    assert assigned_result.order_id is not None
    assigned_order = await db_session.get(Order, assigned_result.order_id)
    assert assigned_order is not None
    assigned_order.assigned_cutter_user_id = worker.id
    await db_session.flush()

    owner_list = await client.get("/api/v1/workshop/cutting-plans", headers=_auth(owner_access))
    production_list = await client.get(
        "/api/v1/workshop/cutting-plans",
        headers=_auth(production_access),
    )
    assigned_detail = await client.get(
        f"/api/v1/workshop/cutting-plans/{assigned_result.id}",
        headers=_auth(production_access),
    )
    unassigned_detail = await client.get(
        f"/api/v1/workshop/cutting-plans/{unassigned_result.id}",
        headers=_auth(production_access),
    )

    assert owner_list.status_code == 200
    assert {row["id"] for row in owner_list.json()} == {
        str(assigned_result.id),
        str(unassigned_result.id),
    }
    assert production_list.status_code == 200
    assert [row["id"] for row in production_list.json()] == [str(assigned_result.id)]
    assert assigned_detail.status_code == 200
    assert unassigned_detail.status_code == 404


async def _confirmed_result(
    db: AsyncSession,
    client_id: uuid.UUID,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    panel: Material,
    edge: Material,
) -> CuttingResult:
    now = datetime.now(UTC)
    result = CuttingResult(
        algorithm_name="ffd-guillotine",
        algorithm_version="1.0",
        status=CuttingResultStatus.CONFIRMED,
        kerf_mm=4,
        edge_trim_mm=10,
        panels_used_by_material={str(panel.id): 1},
        waste_percentage=Decimal("0.25"),
        total_cut_length_mm=640,
        total_edge_length_mm=220,
        edge_length_by_material={str(edge.id): 220},
        parts_snapshot=[],
        material_snapshots={
            str(panel.id): {
                "id": str(panel.id),
                "kind": "panel",
                "manufacturer_name": "Egger",
                "name": panel.name,
                "panel_length_mm": panel.panel_length_mm,
                "panel_width_mm": panel.panel_width_mm,
            },
            str(edge.id): {
                "id": str(edge.id),
                "kind": "edge",
                "manufacturer_name": "Egger",
                "name": edge.name,
            },
        },
        edge_length_shop_by_material={str(edge.id): 220},
        edge_length_own_by_material={},
        edge_consumed_shop_by_material={str(edge.id): 280},
        edge_consumed_own_by_material={},
        edge_banded_sides_by_material={str(edge.id): {"shop": 2, "own": 0}},
        created_at=now,
        confirmed_at=now,
    )
    db.add(result)
    await db.flush()
    order = Order(
        order_number=f"ORD-{uuid.uuid4().hex[:8]}",
        client_id=client_id,
        workshop_id=workshop_id,
        branch_id=branch_id,
        cutting_result_id=result.id,
        status=OrderStatus.NEW,
        version=1,
        contact_name="Client",
        contact_phone="+998901111003",
        subtotal_cutting_tiyin=0,
        subtotal_materials_tiyin=0,
        subtotal_edge_banding_tiyin=0,
        discount_tiyin=0,
        total_tiyin=0,
        currency=Currency.UZS,
    )
    db.add(order)
    await db.flush()
    result.order_id = order.id
    panel_row = CuttingPanel(
        cutting_result_id=result.id,
        material_id=panel.id,
        panel_index=1,
        waste_area_mm2=1000,
    )
    db.add(panel_row)
    await db.flush()
    db.add(
        CuttingPlacement(
            cutting_panel_id=panel_row.id,
            part_ref="shelf",
            part_quantity_index=1,
            x_mm=10,
            y_mm=10,
            length_mm=220,
            width_mm=120,
            rotated=False,
        )
    )
    await db.flush()
    return result
