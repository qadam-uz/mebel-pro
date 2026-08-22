import uuid
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    DecorType,
    Permission,
    UserStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.cutting.contracts import (
    CuttingDraft,
    CuttingPanel,
)
from app.modules.cutting.imports.parser import parse_import_file
from app.modules.support.contracts import ActionLog
from app.modules.workshop.contracts import Branch
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    MaterialFixture,
    seed_branch_material,
    seed_kromka_material,
    seed_manufacturer,
    seed_panel_material,
    seed_workshop_with_owner,
)


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
    branch_id: uuid.UUID,
) -> tuple[MaterialFixture, MaterialFixture, MaterialFixture]:
    """The branch's shelf: a plain panel, a kromka, and a grained panel.

    `branch_id` is required since the reshape — a material *is* a branch's
    format of a decor, so there is no platform-wide material to reference and
    every one of these must be carried by the branch to be pickable.
    """
    manufacturer = await seed_manufacturer(db)
    panel = await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=manufacturer,
        code="H1334",
        name="Oak",
        has_grain=False,
        thickness_mm=Decimal("18"),
        length_mm=600,
        width_mm=400,
        price_tiyin=250000,
        min_stock=1,
    )
    other_panel = await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=manufacturer,
        type=DecorType.MDF,
        code="W980",
        name="White",
        has_grain=True,
        thickness_mm=Decimal("16"),
        length_mm=600,
        width_mm=400,
        price_tiyin=180000,
        min_stock=1,
    )
    # The board's OWN decor, not a second one with the same code: a pattern and
    # the kromka that matches it are two formats of one decor now, which is the
    # case the format reshape exists for.
    edge = await seed_kromka_material(
        db,
        branch_id=branch_id,
        decor=panel.decor,
        thickness_mm=Decimal("0.4"),
        tape_width_mm=19,
        price_tiyin=1000,
        min_stock=1,
    )
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
) -> tuple[MaterialFixture, MaterialFixture]:
    manufacturer = await seed_manufacturer(db, name=f"Map Panels {uuid.uuid4().hex[:6]}")
    panel = await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=manufacturer,
        code="MAP",
        name="White",
        has_grain=False,
        thickness_mm=Decimal("18"),
        length_mm=2750,
        width_mm=1830,
        price_tiyin=350000,
        min_stock=1,
    )
    edge = await seed_kromka_material(
        db,
        branch_id=branch_id,
        decor=panel.decor,
        thickness_mm=Decimal("0.4"),
        tape_width_mm=19,
        price_tiyin=1000,
        min_stock=1,
    )
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
    assert [row["algorithm_name"] for row in results] == ["cutting-engine/native"]
    assert optimized.json()["chosen_result_id"] in {row["id"] for row in results}
    first_result = results[0]
    assert first_result["parts_snapshot"][0]["quantity"] == 2
    assert first_result["parts_snapshot"][0]["name"] == "Shelf"
    assert first_result["panels"][0]["offcuts"]
    assert all(panel_row["cut_count"] is not None for panel_row in first_result["panels"])
    assert all(panel_row["cut_length_mm"] is not None for panel_row in first_result["panels"])
    assert (
        sum(panel_row["cut_length_mm"] for panel_row in first_result["panels"])
        == first_result["total_cut_length_mm"]
    )
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


async def test_optimize_consumes_the_branch_edge_overhang_not_the_platform_default(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # The bander's glue-and-trim allowance is a per-branch setting: the same
    # geometry must consume more tape at a branch that trims longer.
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    branch = await db_session.get(Branch, branch_id)
    assert branch is not None
    branch.edge_overhang_mm = 50
    await db_session.flush()
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(db_session, preferred_branch_id=branch_id)

    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    draft_id = created.json()["id"]
    await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": _parts(panel.id, edge.id)},
    )
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft_id}/optimize",
        headers=_auth(access),
    )

    assert optimized.status_code == 200
    result = optimized.json()["results"][0]
    # Geometry is unchanged — the allowance never touches the drawn edge.
    assert result["edge_length_shop_by_material"] == {str(edge.id): 440}
    assert result["edge_length_own_by_material"] == {str(edge.id): 240}
    # 2 shop sides of 220 mm and 2 own sides of 120 mm, each +50 mm.
    assert result["edge_consumed_shop_by_material"] == {str(edge.id): 540}
    assert result["edge_consumed_own_by_material"] == {str(edge.id): 340}


async def _big_panel(db: AsyncSession, *, branch_id: uuid.UUID) -> MaterialFixture:
    """A panel generous enough that different branch edge-trims still leave room
    to place the parts (per-branch kerf/trim, cutting.md)."""
    return await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=await seed_manufacturer(db, name=f"BigPanels {uuid.uuid4().hex[:6]}"),
        code="H1000",
        name="White",
        has_grain=False,
        thickness_mm=Decimal("18"),
        length_mm=1000,
        width_mm=800,
        price_tiyin=300000,
        min_stock=1,
    )


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
    # A material is a branch's own row, so the "same" panel has to be carried by
    # both branches — but the FORMAT is the platform's and is literally shared.
    # The point of the test is the kerf/trim, so the two rows deliberately point
    # at one `decor_format_id`, at each branch's own price.
    panel = await _big_panel(db_session, branch_id=branch1_id)
    panel2 = await seed_branch_material(
        db_session,
        branch_id=uuid.UUID(branch2_id),
        decor_format=panel.decor_format,
        price_tiyin=300000,
        min_stock=1,
    )

    def parts_for(branch_material_id: uuid.UUID) -> list[dict[str, object]]:
        return [
            {
                "part_ref": "shelf",
                "material_id": str(branch_material_id),
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
        json={"parts_snapshot": parts_for(panel.id)},
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
        json={"parts_snapshot": parts_for(panel2.id)},
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


async def test_a_branchless_draft_keeps_platform_defaults_but_cannot_optimize(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """RESHAPED: optimizing without a branch is no longer possible.

    A material *is* a branch's format of a decor, so a draft with no
    `preferred_branch_id` has nothing to resolve its parts against and every one
    of them reports `material_not_found`. The kerf/trim platform defaults still
    show on the draft — the client can build a parts list before choosing a
    branch — but the optimize call now demands one.

    (Before the reshape a branch-less draft optimized against the platform-wide
    material catalog. That browse mode is deleted, deliberately.)
    """
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel = await _big_panel(db_session, branch_id=branch_id)
    access, _ = await _client_access(db_session, phone="+998901111053", preferred_branch_id=None)
    draft = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    draft_id = draft.json()["id"]
    loaded = await client.get(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
    )
    part = {
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
    branchless = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": [part]},
    )

    # Naming the branch is what makes the very same part resolvable.
    accepted = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"preferred_branch_id": str(branch_id), "parts_snapshot": [part]},
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
    assert branchless.status_code == 400
    assert branchless.json()["code"] == "invalid_cutting_parts"
    assert branchless.json()["details"]["errors"][0]["code"] == "material_not_found"
    assert accepted.status_code == 200
    assert optimized.status_code == 200


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


async def test_thickening_round_trips_and_never_invalidates_the_layout(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Thickening is an instruction to the workshop, not geometry: the
    strip is glued under the part and never cut, so flipping the flag must not
    touch the layout. If it ever joined the geometry-affecting set, marking a
    finished drawing would silently throw away its optimised result."""
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

    thickened = deepcopy(parts)
    thickened[0]["thickened"] = True
    patched = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": thickened},
    )

    assert patched.status_code == 200
    assert patched.json()["parts_snapshot"][0]["thickened"] is True
    assert patched.json()["chosen_result_id"] == result["id"]
    assert patched.json()["results"][0]["panels"] == result["panels"]


async def test_parts_default_to_not_thickened(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Every draft saved before the flag existed omits the key entirely — it has
    to read back as off rather than absent, or the UI toggle has no state."""
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(db_session, preferred_branch_id=branch_id)
    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    draft_id = created.json()["id"]

    patched = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": _parts(panel.id, edge.id)},
    )

    assert patched.status_code == 200
    assert patched.json()["parts_snapshot"][0]["thickened"] is False


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
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    _, _, grained_panel = await _materials(db_session, branch_id=branch_id)
    access, client_row = await _client_access(
        db_session, phone="+998901111020", preferred_branch_id=branch_id
    )

    locked_draft = CuttingDraft(
        client_id=client_row.id,
        preferred_branch_id=branch_id,
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
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, _, _ = await _materials(db_session, branch_id=branch_id)
    access, client_row = await _client_access(
        db_session, phone="+998901111021", preferred_branch_id=branch_id
    )

    locked_draft = CuttingDraft(
        client_id=client_row.id,
        preferred_branch_id=branch_id,
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
            "source_filename": "6.map",
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
    # The draft is named after the imported file, extension stripped (CB task:
    # filename -> draft name).
    assert draft["name"] == "6"
    assert imported_result["source"] == "imported_map"
    assert imported_result["algorithm_name"] == "imported-2dplace-map"
    # 6.map's own layout has parts spaced 4 mm apart and inset 5 mm from every
    # sheet edge — kerf_mm/edge_trim_mm are derived from that geometry, not
    # hardcoded (see imports/map_2dplace.py:derive_map_cut_params).
    assert imported_result["kerf_mm"] == 4
    assert imported_result["edge_trim_mm"] == 5
    assert imported_result["panels_used_by_material"] == {str(panel.id): 1}
    assert imported_result["total_cut_length_mm"] == expected_cut_length
    assert len(imported_result["panels"]) == 1
    assert imported_result["panels"][0]["cut_count"] is None
    assert imported_result["panels"][0]["cut_length_mm"] is None
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
            "source_filename": "6.map",
        },
    )

    assert committed.status_code == 200, committed.text
    body = committed.json()
    stored = await db_session.get(CuttingDraft, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.client_id == walk_in.id
    assert stored.preferred_branch_id == branch_id
    assert stored.created_via_workshop_id == workshop_id
    assert stored.name == "6"
    assert body["results"][0]["source"] == "imported_map"
    assert body["results"][0]["kerf_mm"] == 4
    assert body["results"][0]["edge_trim_mm"] == 5


async def test_workshop_map_import_commit_requires_branch_manage_orders_grant(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, workshop_id, branch_id, _ = await _workshop_owner_access(db_session)
    access, _ = await _staff_user_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.VIEW_ORDERS,
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
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    access, client_row = await _client_access(
        db_session, phone="+998901111021", preferred_branch_id=branch_id
    )
    old_part = _parts(panel.id, edge.id)[0]
    old_part.pop("follow_grain", None)
    draft = CuttingDraft(
        client_id=client_row.id, preferred_branch_id=branch_id, parts_snapshot=[old_part]
    )
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
    owner_access, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    first_access, first_client = await _client_access(
        db_session, phone="+998901111001", preferred_branch_id=branch_id
    )
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
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(
        db_session, phone="+998901111010", preferred_branch_id=branch_id
    )
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


async def test_client_cutting_material_picker_is_always_branch_scoped(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """RESHAPED: `branch_id` is required and `carried_only` is gone.

    A material *is* a branch's format of a decor, so there is no platform-wide
    catalog left to browse and nothing to mark as "not carried" — every row the
    picker returns is carried by construction. The old `branch_carried` flag and
    the `carried_only=false` browse mode are both deleted.

    An UNPRICED format is returned to BOTH pickers, flagged `price_unset`.
    Dropping it for clients hid most of the shelf — one real branch carrying 518
    formats offered two — and quoting one no longer risks a free order line,
    because `sales` refuses to confirm an order that sells an unpriced material
    (tests/test_sales_unpriced_materials.py).
    """
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, edge, other_panel = await _materials(db_session, branch_id=branch_id)
    unpriced = await seed_panel_material(
        db_session, branch_id=branch_id, code="UNPRICED", name="Unpriced", price_tiyin=0
    )
    access, _ = await _client_access(db_session)

    panels = await client.get(
        f"/api/v1/client/catalog/materials?branch_id={branch_id}",
        headers=_auth(access),
    )
    tapes = await client.get(
        f"/api/v1/client/catalog/materials?branch_id={branch_id}&tape=true",
        headers=_auth(access),
    )
    branchless = await client.get(
        "/api/v1/client/catalog/materials",
        headers=_auth(access),
    )

    assert panels.status_code == 200
    # `tape=false` (the default) means every panel-shaped decor, not one `type`:
    # the LDSP and the MDF row both belong in a panel picker.
    assert {row["id"] for row in panels.json()} == {
        str(panel.id),
        str(other_panel.id),
        str(unpriced.id),
    }
    by_id = {row["id"]: row for row in panels.json()}
    assert by_id[str(panel.id)]["price_tiyin"] == 250000
    assert by_id[str(panel.id)]["price_unset"] is False
    assert by_id[str(panel.id)]["thickness_mm"] == "18"
    assert by_id[str(panel.id)]["length_mm"] == 600
    assert by_id[str(panel.id)]["type"] == "ldsp"
    assert by_id[str(other_panel.id)]["type"] == "mdf"
    assert by_id[str(other_panel.id)]["has_grain"] is True
    # The unpriced row reaches the client too, carrying the flag the picker
    # renders as "Narx yo'q" — visible shelf, honest label.
    assert by_id[str(unpriced.id)]["price_unset"] is True
    assert by_id[str(unpriced.id)]["price_tiyin"] == 0
    # Kromka is its own shape, and it carries a tape width instead of a size.
    assert [row["id"] for row in tapes.json()] == [str(edge.id)]
    assert tapes.json()[0]["tape_width_mm"] == 19
    assert tapes.json()[0]["length_mm"] is None
    assert tapes.json()[0]["display_unit"] == "metre"
    # No branch, no catalog — the parameter is required, not defaulted.
    assert branchless.status_code == 422


async def test_workshop_cutting_picker_shows_the_unpriced_rows_a_client_cannot_see(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, _, other_panel = await _materials(db_session, branch_id=branch_id)
    unpriced = await seed_panel_material(
        db_session, branch_id=branch_id, code="UNPRICED", name="Unpriced", price_tiyin=0
    )

    staff_view = await client.get(
        f"/api/v1/workshop/catalog/materials?branch_id={branch_id}",
        headers=_auth(owner_access),
    )

    assert staff_view.status_code == 200
    by_id = {row["id"]: row for row in staff_view.json()}
    assert set(by_id) == {str(panel.id), str(other_panel.id), str(unpriced.id)}
    assert by_id[str(unpriced.id)]["price_unset"] is True
    assert by_id[str(unpriced.id)]["price_tiyin"] == 0


async def test_client_catalog_materials_limit_caps_the_branch_load(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # CB-40: a branch's whole shelf can be capped so a fresh draft does not pull
    # it all; the cap is deterministic (ordered by manufacturer, decor, thickness).
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    panel, _, other_panel = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(db_session)

    uncapped = await client.get(
        f"/api/v1/client/catalog/materials?branch_id={branch_id}",
        headers=_auth(access),
    )
    capped = await client.get(
        f"/api/v1/client/catalog/materials?branch_id={branch_id}&limit=1",
        headers=_auth(access),
    )
    bad_limit = await client.get(
        f"/api/v1/client/catalog/materials?branch_id={branch_id}&limit=0",
        headers=_auth(access),
    )

    assert uncapped.status_code == 200
    assert {row["id"] for row in uncapped.json()} == {str(panel.id), str(other_panel.id)}
    assert capped.status_code == 200
    assert len(capped.json()) == 1
    assert bad_limit.status_code == 422


async def _draft_with_own_claim(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    own_material_allowed: bool,
) -> tuple[str, str, dict[str, object]]:
    """A saved draft carrying an own-sheet claim, on a branch with the setting
    as given. Returns (access token, draft id, the draft as the server echoes)."""
    _, _, branch_id, _ = await _workshop_owner_access(db_session)
    branch = await db_session.get(Branch, branch_id)
    assert branch is not None
    branch.own_material_allowed = own_material_allowed
    await db_session.flush()
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    access, _ = await _client_access(db_session, preferred_branch_id=branch_id)

    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    draft_id = created.json()["id"]
    saved = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={
            "parts_snapshot": _parts(panel.id, edge.id),
            "own_panel_counts": {str(panel.id): 2},
            "own_edge_material_ids": [str(edge.id)],
        },
    )
    assert saved.status_code == 200
    return access, draft_id, saved.json()


async def test_branch_that_takes_client_sheets_keeps_the_claim(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, draft = await _draft_with_own_claim(client, db_session, own_material_allowed=True)

    assert draft["own_material_allowed"] is True
    # Echoed back, not just stored — the dialog reopens on this payload, so a
    # claim the server keeps but does not return reads to the client as lost.
    assert sum(draft["own_panel_counts"].values()) == 2
    assert len(draft["own_edge_material_ids"]) == 1


async def test_branch_that_does_not_take_client_sheets_drops_the_claim(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The editor hides the affordance, but the claim arrives as a plain PATCH —
    a branch that does not accept client sheets must not be priced as if it did."""
    _, _, draft = await _draft_with_own_claim(client, db_session, own_material_allowed=False)

    assert draft["own_material_allowed"] is False
    assert draft["own_panel_counts"] == {}
    assert draft["own_edge_material_ids"] == []


async def test_turning_the_branch_setting_off_clears_an_existing_claim_on_next_save(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, draft_id, draft = await _draft_with_own_claim(
        client, db_session, own_material_allowed=True
    )
    assert sum(draft["own_panel_counts"].values()) == 2

    branch_id = draft["preferred_branch_id"]
    branch = await db_session.get(Branch, uuid.UUID(branch_id))
    assert branch is not None
    branch.own_material_allowed = False
    await db_session.flush()

    # Any write re-checks, not only one that carries a claim: the stale claim
    # would otherwise keep pricing sheets the shop no longer accepts.
    resaved = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"name": "renamed"},
    )

    assert resaved.status_code == 200
    assert resaved.json()["own_panel_counts"] == {}
    assert resaved.json()["own_edge_material_ids"] == []


async def test_staff_may_claim_client_material_on_a_branch_that_forbids_self_serve(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """`own_material_allowed` is a self-serve policy, not a shop-floor ban.

    A branch may keep the option out of the client app and still take a walk-in
    who turns up with their own sheets, so the staff editor must not inherit
    the client path's clearing rule.
    """

    owner_access, _, branch_id, _ = await _workshop_owner_access(db_session)
    branch = await db_session.get(Branch, branch_id)
    assert branch is not None
    assert branch.own_material_allowed is False
    panel, edge, _ = await _materials(db_session, branch_id=branch_id)
    walk_in, _ = await _client_access(db_session, preferred_branch_id=branch_id)
    client_row = await db_session.scalar(
        select(Client).where(Client.preferred_branch_id == branch_id)
    )
    assert client_row is not None

    created = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(owner_access),
        json={"branch_id": str(branch_id), "client_id": str(client_row.id)},
    )
    assert created.status_code == 201
    saved = await client.patch(
        f"/api/v1/workshop/cutting-drafts/{created.json()['id']}",
        headers=_auth(owner_access),
        json={
            "parts_snapshot": _parts(panel.id, edge.id),
            "own_panel_counts": {str(panel.id): 2},
        },
    )

    assert saved.status_code == 200, saved.text
    # The branch still reports the self-serve policy as off …
    assert saved.json()["own_material_allowed"] is False
    # … and the staff-entered claim survives anyway.
    assert sum(saved.json()["own_panel_counts"].values()) == 2
    assert walk_in
