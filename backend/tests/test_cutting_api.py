import uuid
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
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
    CuttingPanel,
)
from app.modules.cutting.imports.parser import parse_import_file
from app.modules.support.contracts import ActionLog
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import default_working_hours, seed_workshop_with_owner


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
        edge_width_mm=19,
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
            "name": "  Shelf  ",
            "material_id": str(panel_id),
            "material_source": "shop",
            "length_mm": 220,
            "width_mm": 120,
            "quantity": 2,
            "edge_top": {"material_id": str(edge_id), "source": "shop"},
            "edge_left": {"material_id": str(edge_id), "source": "own"},
        }
    ]


async def _map_materials(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
) -> tuple[Material, Material]:
    manufacturer = Manufacturer(name=f"Map Panels {uuid.uuid4().hex[:6]}", country="UZ")
    db.add(manufacturer)
    await db.flush()
    panel = Material(
        kind=MaterialKind.PANEL,
        manufacturer_id=manufacturer.id,
        type=PanelMaterialType.DSP,
        name="Map panel 2750x1830",
        thickness_mm=Decimal("18"),
        color="White",
        decor_code="MAP",
        panel_length_mm=2750,
        panel_width_mm=1830,
        grain_direction=False,
    )
    edge = Material(
        kind=MaterialKind.EDGE,
        manufacturer_id=manufacturer.id,
        name="Map edge",
        thickness_mm=Decimal("0.4"),
        color="White",
        decor_code="MAP",
        edge_width_mm=19,
    )
    db.add_all([panel, edge])
    await db.flush()
    db.add(
        BranchMaterial(
            branch_id=branch_id,
            material_id=panel.id,
            price_tiyin=350000,
            min_stock=1,
        )
    )
    await db.flush()
    return panel, edge


def _map_commit_parts(
    parsed: dict[str, object],
    panel_id: uuid.UUID,
    edge_id: uuid.UUID,
) -> list[dict[str, object]]:
    layout = parsed["map_layout"]
    assert isinstance(layout, dict)
    rows = layout["part_rows"]
    assert isinstance(rows, list)
    parts: list[dict[str, object]] = []
    for row in rows:
        assert isinstance(row, dict)
        edges = row["edges"]
        assert isinstance(edges, dict)
        parts.append(
            {
                "part_ref": row["part_ref"],
                "name": str(row.get("name") or "").strip() or None,
                "material_id": str(panel_id),
                "material_source": "shop",
                "follow_grain": True,
                "length_mm": row["length_mm"],
                "width_mm": row["width_mm"],
                "quantity": row["quantity"],
                "edge_top": {"material_id": str(edge_id), "source": "shop"}
                if edges.get("top")
                else None,
                "edge_bottom": {"material_id": str(edge_id), "source": "shop"}
                if edges.get("bottom")
                else None,
                "edge_left": {"material_id": str(edge_id), "source": "shop"}
                if edges.get("left")
                else None,
                "edge_right": {"material_id": str(edge_id), "source": "shop"}
                if edges.get("right")
                else None,
            }
        )
    return parts


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
    pdf = await client.get(
        f"/api/v1/client/cutting-results/{chosen_result_id}/pdf",
        headers=_auth(access),
    )
    await db_session.execute(update(CuttingPanel).values(offcuts=None))
    await db_session.flush()
    loaded_old_panel = await client.get(
        f"/api/v1/client/cutting-drafts/{draft_id}",
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
    assert updated.json()["parts_snapshot"][0]["name"] == "Shelf"
    assert optimized.status_code == 200
    assert [row["algorithm_name"] for row in results] == ["cutting-engine-best"]
    assert optimized.json()["chosen_result_id"] in {row["id"] for row in results}
    first_result = results[0]
    assert first_result["parts_snapshot"][0]["quantity"] == 2
    assert first_result["parts_snapshot"][0]["name"] == "Shelf"
    assert first_result["panels"][0]["offcuts"]
    assert str(panel.id) in first_result["material_snapshots"]
    assert first_result["edge_length_shop_by_material"] == {str(edge.id): 440}
    assert first_result["edge_length_own_by_material"] == {str(edge.id): 240}
    assert first_result["edge_consumed_shop_by_material"] == {str(edge.id): 500}
    assert first_result["edge_banded_sides_by_material"] == {str(edge.id): {"shop": 2, "own": 2}}
    assert chosen.status_code == 200
    assert chosen.json()["chosen_result_id"] == chosen_result_id
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert loaded_old_panel.status_code == 200
    assert loaded_old_panel.json()["results"][0]["panels"][0]["offcuts"] == []
    assert deleted.status_code == 204
    assert action_count == 5


async def _big_panel(db: AsyncSession) -> Material:
    """A panel generous enough that different branch edge-trims still leave room
    to place the parts (per-branch kerf/trim, cutting.md)."""
    manufacturer = Manufacturer(name=f"BigPanels {uuid.uuid4().hex[:6]}", country="UZ")
    db.add(manufacturer)
    await db.flush()
    panel = Material(
        kind=MaterialKind.PANEL,
        manufacturer_id=manufacturer.id,
        type=PanelMaterialType.DSP,
        name="Big DSP 18",
        thickness_mm=Decimal("18"),
        color="White",
        decor_code="H1000",
        panel_length_mm=1000,
        panel_width_mm=800,
        grain_direction=False,
    )
    db.add(panel)
    await db.flush()
    return panel


async def test_optimize_resolves_kerf_and_trim_from_the_draft_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same parts, two branches with different cutting settings, must resolve to
    different kerf/trim on the persisted result and a different waste % — the
    whole point of per-branch settings (cutting.md)."""
    owner_access, _workshop_id, branch1_id, _ = await _workshop_owner_access(db_session)
    branch2 = await client.post(
        "/api/v1/workshop/branches",
        headers=_auth(owner_access),
        json={
            "name": "Second branch",
            "address": "Tashkent, Second",
            "phone": "+998907654321",
            "working_hours": default_working_hours(),
        },
    )
    assert branch2.status_code == 201
    branch2_id = branch2.json()["id"]
    patched_branch2 = await client.patch(
        f"/api/v1/workshop/branches/{branch2_id}",
        headers=_auth(owner_access),
        json={"kerf_mm": 3, "edge_trim_mm": 50},
    )
    assert patched_branch2.status_code == 200
    panel = await _big_panel(db_session)
    parts = [
        {
            "part_ref": "shelf",
            "material_id": str(panel.id),
            "material_source": "shop",
            "length_mm": 480,
            "width_mm": 380,
            "quantity": 3,
            "edge_top": None,
            "edge_bottom": None,
            "edge_left": None,
            "edge_right": None,
        }
    ]

    access1, _ = await _client_access(
        db_session, phone="+998901111051", preferred_branch_id=branch1_id
    )
    draft1 = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access1))
    await client.patch(
        f"/api/v1/client/cutting-drafts/{draft1.json()['id']}",
        headers=_auth(access1),
        json={"parts_snapshot": parts},
    )
    optimized1 = await client.post(
        f"/api/v1/client/cutting-drafts/{draft1.json()['id']}/optimize",
        headers=_auth(access1),
    )

    access2, _ = await _client_access(
        db_session, phone="+998901111052", preferred_branch_id=uuid.UUID(branch2_id)
    )
    draft2 = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access2))
    await client.patch(
        f"/api/v1/client/cutting-drafts/{draft2.json()['id']}",
        headers=_auth(access2),
        json={"parts_snapshot": parts},
    )
    optimized2 = await client.post(
        f"/api/v1/client/cutting-drafts/{draft2.json()['id']}/optimize",
        headers=_auth(access2),
    )

    assert optimized1.status_code == 200
    assert optimized2.status_code == 200
    result1 = optimized1.json()["results"][0]
    result2 = optimized2.json()["results"][0]
    assert result1["kerf_mm"] == 4
    assert result1["edge_trim_mm"] == 5
    assert result2["kerf_mm"] == 3
    assert result2["edge_trim_mm"] == 50
    assert result1["waste_percentage"] != result2["waste_percentage"]


async def test_optimize_falls_back_to_platform_defaults_without_a_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    panel = await _big_panel(db_session)
    access, _ = await _client_access(db_session, phone="+998901111053", preferred_branch_id=None)
    draft = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    draft_id = draft.json()["id"]
    loaded = await client.get(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
    )
    await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={
            "parts_snapshot": [
                {
                    "part_ref": "shelf",
                    "material_id": str(panel.id),
                    "material_source": "shop",
                    "length_mm": 480,
                    "width_mm": 380,
                    "quantity": 1,
                    "edge_top": None,
                    "edge_bottom": None,
                    "edge_left": None,
                    "edge_right": None,
                }
            ]
        },
    )
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft_id}/optimize",
        headers=_auth(access),
    )

    assert draft.json()["preferred_branch_id"] is None
    assert draft.json()["kerf_mm"] == 4
    assert draft.json()["edge_trim_mm"] == 5
    assert loaded.json()["kerf_mm"] == 4
    assert loaded.json()["edge_trim_mm"] == 5
    assert optimized.status_code == 200
    result = optimized.json()["results"][0]
    assert result["kerf_mm"] == 4
    assert result["edge_trim_mm"] == 5


async def test_neutral_parts_edit_keeps_candidate_result_and_refreshes_edges(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(db_session, preferred_branch_id=branch_id)
    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    draft_id = created.json()["id"]
    parts = _parts(panel.id, edge.id)
    await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": parts},
    )
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft_id}/optimize", headers=_auth(access)
    )
    result = optimized.json()["results"][0]
    before_panels = result["panels"]

    neutral = deepcopy(parts)
    neutral[0]["name"] = "Renamed shelf"
    neutral[0]["edge_top"] = None
    neutral[0]["material_source"] = "own"
    patched = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": neutral},
    )

    assert patched.status_code == 200
    assert patched.json()["chosen_result_id"] == result["id"]
    refreshed = patched.json()["results"][0]
    assert refreshed["id"] == result["id"]
    assert refreshed["parts_snapshot"][0]["name"] == "Renamed shelf"
    assert refreshed["edge_length_by_material"] == {str(edge.id): 240}
    assert refreshed["panels"] == before_panels


@pytest.mark.parametrize(
    "change",
    ["quantity", "length_mm", "width_mm", "material_id", "follow_grain", "add_ref", "remove_ref"],
)
async def test_geometry_parts_edits_delete_candidate_results(
    client: AsyncClient,
    db_session: AsyncSession,
    change: str,
) -> None:
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, other_panel = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(db_session, preferred_branch_id=branch_id)
    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    draft_id = created.json()["id"]
    parts = _parts(panel.id, edge.id)
    await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": parts},
    )
    await client.post(f"/api/v1/client/cutting-drafts/{draft_id}/optimize", headers=_auth(access))
    changed = deepcopy(parts)
    if change == "add_ref":
        added = deepcopy(changed[0])
        added["part_ref"] = "added"
        changed.append(added)
    elif change == "remove_ref":
        changed = []
    elif change == "material_id":
        changed[0]["material_id"] = str(other_panel.id)
    elif change == "follow_grain":
        changed[0]["follow_grain"] = False
    else:
        changed[0][change] = int(changed[0][change]) + 1
    patched = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": changed},
    )

    assert patched.status_code == 200
    assert patched.json()["chosen_result_id"] is None
    assert patched.json()["results"] == []


async def test_client_cutting_draft_keeps_incomplete_rows_for_autosave(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    access, _ = await _client_access(db_session, preferred_branch_id=branch_id)

    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    draft_id = created.json()["id"]
    incomplete = {
        "part_ref": "in-progress-row",
        "name": "Yon devor",
        "material_id": "",
        "material_source": "shop",
        "follow_grain": False,
        "length_mm": 120,
        "width_mm": 0,
        "quantity": 0,
        "edge_top": None,
        "edge_bottom": None,
        "edge_left": None,
        "edge_right": None,
    }

    updated = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": [incomplete]},
    )
    loaded = await client.get(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
    )

    assert updated.status_code == 200
    assert updated.json()["parts_snapshot"][0]["material_id"] is None
    assert loaded.status_code == 200
    assert loaded.json()["parts_snapshot"][0] == updated.json()["parts_snapshot"][0]


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


async def test_follow_grain_locks_rotation_on_non_grained_material(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    panel, _, _ = await _materials(db_session)
    access, client_row = await _client_access(db_session, phone="+998901111021")

    locked_draft = CuttingDraft(
        client_id=client_row.id,
        parts_snapshot=[_rotated_only_part(panel.id, follow_grain=True)],
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
        json={"parts_snapshot": [_rotated_only_part(panel.id, follow_grain=False)]},
    )
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{unlocked_draft_id}/optimize",
        headers=_auth(access),
    )
    placements = [
        placement
        for result_panel in optimized.json()["results"][0]["panels"]
        for placement in result_panel["placements"]
    ]

    assert locked.status_code == 400
    assert locked.json()["details"]["errors"][0]["code"] == "impossible_grain"
    assert updated.status_code == 200
    assert updated.json()["parts_snapshot"][0]["follow_grain"] is False
    assert optimized.status_code == 200
    assert placements[0]["rotated"] is True


async def test_client_map_import_commit_keeps_a_single_result_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge = await _map_materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(
        db_session, phone="+998901111040", preferred_branch_id=branch_id
    )
    fixture = Path(__file__).parent / "fixtures" / "cutting_import" / "map" / "6.map"
    parsed_model = parse_import_file(filename="6.map", content=fixture.read_bytes())
    parsed = parsed_model.model_dump(mode="json")
    parts = _map_commit_parts(parsed, panel.id, edge.id)
    layout = parsed["map_layout"]
    assert isinstance(layout, dict)
    expected_cut_length = sum(
        2 * (placement["length_mm"] + placement["width_mm"])
        for sheet in layout["sheets"]
        for placement in sheet["placements"]
        if not placement["is_waste"]
    )

    committed = await client.post(
        "/api/v1/client/cutting/import/map/commit",
        headers=_auth(access),
        json={
            "preferred_branch_id": str(branch_id),
            "parts": parts,
            "map_layout": layout,
            "panel_picks": {"m1": str(panel.id)},
        },
    )
    draft = committed.json()
    imported_result = draft["results"][0]
    pdf = await client.get(
        f"/api/v1/client/cutting-results/{imported_result['id']}/pdf",
        headers=_auth(access),
    )
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft['id']}/optimize",
        headers=_auth(access),
    )
    patched = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft['id']}",
        headers=_auth(access),
        json={"parts_snapshot": parts},
    )

    assert committed.status_code == 200
    assert draft["chosen_result_id"] == imported_result["id"]
    assert imported_result["source"] == "imported_map"
    assert imported_result["algorithm_name"] == "imported-2dplace-map"
    assert imported_result["kerf_mm"] == 0
    assert imported_result["edge_trim_mm"] == 0
    assert imported_result["panels_used_by_material"] == {str(panel.id): 1}
    assert imported_result["total_cut_length_mm"] == expected_cut_length
    assert len(imported_result["panels"]) == 1
    assert len(imported_result["panels"][0]["placements"]) == 6
    assert any(offcut["usable"] for offcut in imported_result["panels"][0]["offcuts"])
    assert imported_result["parts_snapshot"][0]["name"]
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert optimized.status_code == 200
    assert [row["source"] for row in optimized.json()["results"]] == ["optimizer"]
    assert optimized.json()["chosen_result_id"] == optimized.json()["results"][0]["id"]
    assert patched.status_code == 200
    assert [row["source"] for row in patched.json()["results"]] == ["optimizer"]
    assert patched.json()["chosen_result_id"] == optimized.json()["results"][0]["id"]

    changed_parts = deepcopy(parts)
    changed_parts[0]["quantity"] += 1
    geometry_edit = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft['id']}",
        headers=_auth(access),
        json={"parts_snapshot": changed_parts},
    )

    assert geometry_edit.status_code == 200
    assert geometry_edit.json()["chosen_result_id"] is None
    assert geometry_edit.json()["results"] == []

    reoptimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft['id']}/optimize",
        headers=_auth(access),
    )

    assert reoptimized.status_code == 200
    assert [row["source"] for row in reoptimized.json()["results"]] == ["optimizer"]
    assert reoptimized.json()["chosen_result_id"] == reoptimized.json()["results"][0]["id"]


async def test_client_map_import_commit_rejects_material_size_mismatch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    correct_panel, _ = await _map_materials(db_session, branch_id=branch_id)
    wrong_panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(
        db_session, phone="+998901111041", preferred_branch_id=branch_id
    )
    fixture = Path(__file__).parent / "fixtures" / "cutting_import" / "map" / "6.map"
    parsed = parse_import_file(filename="6.map", content=fixture.read_bytes()).model_dump(
        mode="json"
    )
    parts = _map_commit_parts(parsed, correct_panel.id, edge.id)

    rejected = await client.post(
        "/api/v1/client/cutting/import/map/commit",
        headers=_auth(access),
        json={
            "preferred_branch_id": str(branch_id),
            "parts": parts,
            "map_layout": parsed["map_layout"],
            "panel_picks": {"m1": str(wrong_panel.id)},
        },
    )

    assert rejected.status_code == 400
    assert rejected.json()["code"] == "map_layout_material_mismatch"


async def test_workshop_map_import_commit_creates_staff_minted_imported_draft(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, workshop_id, branch_id, _ = await _workshop_owner_access(db_session)
    access, _ = await _staff_user_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_ORDERS,
    )
    walk_in = Client(phone="+998901111042", name="Walk-in client")
    db_session.add(walk_in)
    await db_session.flush()
    panel, edge = await _map_materials(db_session, branch_id=branch_id)
    fixture = Path(__file__).parent / "fixtures" / "cutting_import" / "map" / "6.map"
    parsed = parse_import_file(filename="6.map", content=fixture.read_bytes()).model_dump(
        mode="json"
    )

    committed = await client.post(
        "/api/v1/workshop/cutting/import/map/commit",
        headers=_auth(access),
        json={
            "client_id": str(walk_in.id),
            "branch_id": str(branch_id),
            "parts": _map_commit_parts(parsed, panel.id, edge.id),
            "map_layout": parsed["map_layout"],
            "panel_picks": {"m1": str(panel.id)},
        },
    )

    assert committed.status_code == 200, committed.text
    body = committed.json()
    stored = await db_session.get(CuttingDraft, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.client_id == walk_in.id
    assert stored.preferred_branch_id == branch_id
    assert stored.created_via_workshop_id == workshop_id
    assert body["results"][0]["source"] == "imported_map"


async def test_workshop_map_import_commit_requires_branch_manage_orders_grant(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, workshop_id, branch_id, _ = await _workshop_owner_access(db_session)
    access, _ = await _staff_user_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.VIEW_DASHBOARD,
    )
    walk_in = Client(phone="+998901111043", name="Walk-in client")
    db_session.add(walk_in)
    await db_session.flush()

    forbidden = await client.post(
        "/api/v1/workshop/cutting/import/map/commit",
        headers=_auth(access),
        json={
            "client_id": str(walk_in.id),
            "branch_id": str(branch_id),
            "parts": [],
            "map_layout": {
                "sheets": [],
                "part_rows": [],
                "description": "",
                "customer_name": "",
                "order_type": "",
            },
            "panel_picks": {},
        },
    )

    assert forbidden.status_code == 403


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
