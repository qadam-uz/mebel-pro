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
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, Manufacturer, Material
from app.modules.cutting.contracts import (
    CuttingDraft,
)
from app.modules.support.contracts import ActionLog
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner


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


def _rotated_only_part(panel_id: uuid.UUID, *, follow_grain: bool) -> dict[str, object]:
    return {
        "part_ref": f"rotated-{uuid.uuid4().hex[:8]}",
        "material_id": str(panel_id),
        "material_source": "shop",
        "follow_grain": follow_grain,
        "length_mm": 360,
        "width_mm": 500,
        "quantity": 1,
        "edge_top": None,
        "edge_bottom": None,
        "edge_left": None,
        "edge_right": None,
    }


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


async def test_grained_part_follow_grain_controls_rotation_validation_and_result(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, grained_panel = await _materials(db_session)
    access, client_row = await _client_access(db_session, phone="+998901111020")

    locked_draft = CuttingDraft(
        client_id=client_row.id,
        parts_snapshot=[_rotated_only_part(grained_panel.id, follow_grain=True)],
    )
    db_session.add(locked_draft)
    await db_session.flush()
    locked = await client.post(
        f"/api/v1/client/cutting-drafts/{locked_draft.id}/optimize",
        headers=_auth(access),
    )

    unlocked = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    unlocked_draft_id = unlocked.json()["id"]
    updated = await client.patch(
        f"/api/v1/client/cutting-drafts/{unlocked_draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": [_rotated_only_part(grained_panel.id, follow_grain=False)]},
    )
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{unlocked_draft_id}/optimize",
        headers=_auth(access),
    )
    result = optimized.json()["results"][0]
    placements = [placement for panel in result["panels"] for placement in panel["placements"]]

    assert locked.status_code == 400
    assert locked.json()["code"] == "invalid_cutting_parts"
    assert locked.json()["details"]["errors"][0]["code"] == "impossible_grain"
    assert updated.status_code == 200
    assert updated.json()["parts_snapshot"][0]["follow_grain"] is False
    assert optimized.status_code == 200
    assert result["parts_snapshot"][0]["follow_grain"] is False
    assert placements[0]["rotated"] is True


async def test_old_cutting_part_snapshots_default_to_follow_grain_true(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    panel, edge, _ = await _materials(db_session)
    access, client_row = await _client_access(db_session, phone="+998901111021")
    old_part = _parts(panel.id, edge.id)[0]
    old_part.pop("follow_grain", None)
    draft = CuttingDraft(client_id=client_row.id, parts_snapshot=[old_part])
    db_session.add(draft)
    await db_session.flush()

    loaded = await client.get(
        f"/api/v1/client/cutting-drafts/{draft.id}",
        headers=_auth(access),
    )
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft.id}/optimize",
        headers=_auth(access),
    )

    assert loaded.status_code == 200
    assert loaded.json()["parts_snapshot"][0]["follow_grain"] is True
    assert optimized.status_code == 200
    assert optimized.json()["parts_snapshot"][0]["follow_grain"] is True
    assert optimized.json()["results"][0]["parts_snapshot"][0]["follow_grain"] is True


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


async def test_client_surface_hides_staff_minted_drafts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, workshop_id, _, _ = await _workshop_owner_access(db_session)
    access, client_row = await _client_access(db_session)
    own = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    staff_minted = CuttingDraft(
        client_id=client_row.id,
        created_via_workshop_id=workshop_id,
        parts_snapshot=[],
    )
    db_session.add(staff_minted)
    await db_session.flush()

    listed = await client.get("/api/v1/client/cutting-drafts", headers=_auth(access))
    hidden_get = await client.get(
        f"/api/v1/client/cutting-drafts/{staff_minted.id}",
        headers=_auth(access),
    )
    hidden_delete = await client.delete(
        f"/api/v1/client/cutting-drafts/{staff_minted.id}",
        headers=_auth(access),
    )

    assert own.status_code == 201
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [own.json()["id"]]
    assert hidden_get.status_code == 404
    assert hidden_get.json()["code"] == "cutting_draft_not_found"
    assert hidden_delete.status_code == 404


async def test_draft_limit_count_excludes_staff_minted_drafts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, workshop_id, _, _ = await _workshop_owner_access(db_session)
    access, client_row = await _client_access(db_session)
    for _ in range(49):
        db_session.add(CuttingDraft(client_id=client_row.id, parts_snapshot=[]))
    db_session.add(
        CuttingDraft(
            client_id=client_row.id,
            created_via_workshop_id=workshop_id,
            parts_snapshot=[],
        )
    )
    await db_session.flush()

    fits = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    capped = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))

    assert fits.status_code == 201
    assert capped.status_code == 409
    assert capped.json()["code"] == "draft_limit_exceeded"


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
