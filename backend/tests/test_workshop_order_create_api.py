"""Workshop staff creating cutting drafts + orders for walk-in clients."""

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.core.security import hash_password
from app.models.enums import (
    ActorType,
    AuthenticatedPrincipalType,
    OrderStatus,
    Permission,
    UserStatus,
)
from app.modules.access.api import create_session, find_or_create_client
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchPricing
from app.modules.cutting.contracts import CuttingDraft
from app.modules.inventory.contracts import StockItem
from app.modules.sales.contracts import Order, OrderStatusEvent
from app.modules.workshop.api import next_branch_no
from app.modules.workshop.contracts import Branch
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    MaterialFixture,
    seed_kromka_material,
    seed_manufacturer,
    seed_panel_material,
    seed_workshop_with_owner,
)


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _priced_workshop(
    db: AsyncSession,
    *,
    with_pricing: bool = True,
    login: str = "owner",
) -> tuple[str, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Owner access + a branch that (optionally) has cutting/edge pricing."""
    workshop, branch, owner = await seed_workshop_with_owner(db, login=login)
    owner.password_reset_required = False
    if with_pricing:
        db.add(
            BranchPricing(
                branch_id=branch.id,
                cutting_rate_tiyin=50_000,
                edge_banding_rate_tiyin=20_000,
                updated_at=datetime.now(UTC),
                updated_by_user_id=owner.id,
            )
        )
    await db.flush()
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
    staff = WorkshopUser(
        workshop_id=workshop_id,
        login=f"staff-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("StaffTemp123"),
        full_name="Scoped Staff",
        phone=f"+99890{uuid.uuid4().int % 10**7:07d}",
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
    return tokens.access_token


async def _materials(
    db: AsyncSession, *, branch_id: uuid.UUID
) -> tuple[MaterialFixture, MaterialFixture]:
    """The branch's carried panel and kromka, each stocked.

    `.id` is the BRANCH material id — what an order item, a cutting panel and a
    stock row all point at since the reshape.
    """
    manufacturer = await seed_manufacturer(db, name=f"Maker {uuid.uuid4().hex[:6]}", country="UZ")
    panel = await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=manufacturer,
        code=f"W-P-{uuid.uuid4().hex[:4]}",
        name="White",
        has_grain=False,
        thickness_mm=Decimal("18"),
        length_mm=900,
        width_mm=600,
        price_tiyin=250_000,
        min_stock=1,
    )
    edge = await seed_kromka_material(
        db,
        branch_id=branch_id,
        manufacturer=manufacturer,
        code=f"W-E-{uuid.uuid4().hex[:4]}",
        name="White",
        thickness_mm=Decimal("2"),
        tape_width_mm=19,
        price_tiyin=10_000,
        min_stock=1,
    )
    db.add_all(
        [
            StockItem(
                branch_id=branch_id,
                branch_material_id=panel.id,
                on_hand=5,
                updated_at=datetime.now(UTC),
            ),
            StockItem(
                branch_id=branch_id,
                branch_material_id=edge.id,
                on_hand=10_000,
                updated_at=datetime.now(UTC),
            ),
        ]
    )
    await db.flush()
    return panel, edge


async def _resolve_client(client: AsyncClient, access: str, *, phone: str, name: str) -> str:
    resolved = await client.post(
        "/api/v1/workshop/clients/resolve",
        headers=_auth(access),
        json={"phone": phone, "name": name},
    )
    assert resolved.status_code == 200, resolved.text
    return str(resolved.json()["id"])


async def _optimized_workshop_draft(
    client: AsyncClient,
    access: str,
    *,
    client_id: str,
    branch_id: uuid.UUID,
    panel: MaterialFixture,
    edge: MaterialFixture,
) -> str:
    created = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(access),
        json={"client_id": client_id, "branch_id": str(branch_id)},
    )
    assert created.status_code == 201, created.text
    draft_id = created.json()["id"]
    patched = await client.patch(
        f"/api/v1/workshop/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={
            "parts_snapshot": [
                {
                    "part_ref": "walkin-part",
                    "material_id": str(panel.id),
                    "material_source": "shop",
                    "length_mm": 260,
                    "width_mm": 180,
                    "quantity": 2,
                    "edge_top": {"material_id": str(edge.id), "source": "shop"},
                    "edge_bottom": None,
                    "edge_left": None,
                    "edge_right": None,
                }
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    optimized = await client.post(
        f"/api/v1/workshop/cutting-drafts/{draft_id}/optimize",
        headers=_auth(access),
    )
    assert optimized.status_code == 200, optimized.text
    return draft_id


async def test_staff_creates_and_auto_confirms_order_for_walk_in(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, owner_id = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    client_id = await _resolve_client(client, access, phone="+998901112233", name="Walk-in Dilshod")
    draft_id = await _optimized_workshop_draft(
        client, access, client_id=client_id, branch_id=branch_id, panel=panel, edge=edge
    )

    quote = await client.get(
        f"/api/v1/workshop/orders/quote?draft_id={draft_id}&branch_id={branch_id}",
        headers=_auth(access),
    )
    assert quote.status_code == 200, quote.text
    assert quote.json()["total_tiyin"] > 0

    placed = await client.post(
        "/api/v1/workshop/orders",
        headers=_auth(access),
        json={
            "draft_id": draft_id,
            "branch_id": str(branch_id),
            "contact_name": "Walk-in Dilshod",
            "contact_phone": "+998901112233",
            "note_client": "Counter order",
        },
    )
    assert placed.status_code == 201, placed.text
    order = placed.json()
    order_id = uuid.UUID(str(order["id"]))

    # Lands confirmed, not new.
    assert order["status"] == "confirmed"
    row = await db_session.get(Order, order_id)
    assert row is not None
    # One global handle, six random digits, no leading zero (sales.md).
    assert re.fullmatch(r"[1-9]\d{5}", str(order["order_number"]))
    assert row.confirmed_at is not None
    assert row.client_id == uuid.UUID(client_id)

    # Two creation events, both authored by the staff user.
    events = (
        (
            await db_session.execute(
                select(OrderStatusEvent)
                .where(OrderStatusEvent.order_id == order_id)
                .order_by(OrderStatusEvent.changed_at)
            )
        )
        .scalars()
        .all()
    )
    assert [(e.from_status, e.to_status) for e in events] == [
        (None, OrderStatus.NEW),
        (OrderStatus.NEW, OrderStatus.CONFIRMED),
    ]
    assert all(e.actor_type is ActorType.WORKSHOP_USER for e in events)
    assert all(e.actor_user_id == owner_id and e.actor_client_id is None for e in events)

    # The draft is consumed on placement.
    assert await db_session.get(CuttingDraft, uuid.UUID(draft_id)) is None


async def test_walk_in_sees_order_after_bot_login(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, _ = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    phone = "+998901990011"
    client_id = await _resolve_client(client, access, phone=phone, name="Later Login")
    draft_id = await _optimized_workshop_draft(
        client, access, client_id=client_id, branch_id=branch_id, panel=panel, edge=edge
    )
    placed = await client.post(
        "/api/v1/workshop/orders",
        headers=_auth(access),
        json={
            "draft_id": draft_id,
            "branch_id": str(branch_id),
            "contact_name": "Later Login",
            "contact_phone": phone,
        },
    )
    assert placed.status_code == 201
    order_id = placed.json()["id"]

    # The walk-in later signs in through the bot (find-or-create returns the SAME
    # row) and sees it.
    resolution = await find_or_create_client(db_session, phone=phone, name=None)
    assert resolution is not None
    assert resolution.client.id == uuid.UUID(client_id)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=resolution.client.id,
    )
    listed = await client.get("/api/v1/client/orders", headers=_auth(tokens.access_token))
    assert listed.status_code == 200
    rows = {row["id"]: row for row in listed.json()}
    assert order_id in rows
    # The client never saw this drawing before the order existed, so the card has
    # to say staff built it — on the list and on the detail alike.
    assert rows[order_id]["created_via_workshop"] is True
    detail = await client.get(
        f"/api/v1/client/orders/{order_id}", headers=_auth(tokens.access_token)
    )
    assert detail.status_code == 200
    assert detail.json()["created_via_workshop"] is True


async def test_staff_minted_draft_is_hidden_from_the_client(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, _ = await _priced_workshop(db_session)
    phone = "+998901330022"
    client_id = await _resolve_client(client, access, phone=phone, name="Private Draft")
    created = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(access),
        json={"client_id": client_id, "branch_id": str(branch_id)},
    )
    draft_id = created.json()["id"]

    # The owning client logs in — the staff-minted draft is invisible on their surface.
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=uuid.UUID(client_id),
    )
    ch = _auth(tokens.access_token)
    listed = await client.get("/api/v1/client/cutting-drafts", headers=ch)
    assert listed.status_code == 200
    assert draft_id not in {row["id"] for row in listed.json()}
    shown = await client.get(f"/api/v1/client/cutting-drafts/{draft_id}", headers=ch)
    assert shown.status_code == 404


async def test_cross_workshop_draft_access_is_denied(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_a, _, branch_a, _ = await _priced_workshop(db_session)
    client_id = await _resolve_client(client, access_a, phone="+998901440033", name="A Client")
    created = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(access_a),
        json={"client_id": client_id, "branch_id": str(branch_a)},
    )
    draft_id = created.json()["id"]

    # Staff of a DIFFERENT workshop cannot read or order against it.
    access_b, _, branch_b, _ = await _priced_workshop(db_session, login="owner_b")
    shown = await client.get(f"/api/v1/workshop/cutting-drafts/{draft_id}", headers=_auth(access_b))
    assert shown.status_code == 404
    quoted = await client.get(
        f"/api/v1/workshop/orders/quote?draft_id={draft_id}&branch_id={branch_b}",
        headers=_auth(access_b),
    )
    assert quoted.status_code == 404


async def test_process_production_only_staff_cannot_create(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, workshop_id, branch_id, _ = await _priced_workshop(db_session)
    client_id = await _resolve_client(client, owner_access, phone="+998901550044", name="Gated")
    prod_access = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.PROCESS_PRODUCTION,
    )
    created = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(prod_access),
        json={"client_id": client_id, "branch_id": str(branch_id)},
    )
    assert created.status_code == 403
    ordered = await client.post(
        "/api/v1/workshop/orders",
        headers=_auth(prod_access),
        json={
            "draft_id": str(uuid.uuid4()),
            "branch_id": str(branch_id),
            "contact_name": "X",
            "contact_phone": "+998901550044",
        },
    )
    assert ordered.status_code == 403


async def test_missing_pricing_fails_with_client_error_code(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, _ = await _priced_workshop(db_session, with_pricing=False)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    client_id = await _resolve_client(client, access, phone="+998901660055", name="No Price")
    draft_id = await _optimized_workshop_draft(
        client, access, client_id=client_id, branch_id=branch_id, panel=panel, edge=edge
    )
    quoted = await client.get(
        f"/api/v1/workshop/orders/quote?draft_id={draft_id}&branch_id={branch_id}",
        headers=_auth(access),
    )
    assert quoted.status_code == 400
    assert quoted.json()["code"] == "missing_cutting_rate"


async def test_blocked_client_cannot_get_a_draft(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, _ = await _priced_workshop(db_session)
    blocked = Client(
        phone="+998901770066",
        name="Blocked",
        status=UserStatus.BLOCKED,
    )
    db_session.add(blocked)
    await db_session.flush()
    created = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(access),
        json={"client_id": str(blocked.id), "branch_id": str(branch_id)},
    )
    assert created.status_code == 403
    assert created.json()["code"] == "account_blocked"


async def test_draft_limit_excludes_staff_minted_drafts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, workshop_id, branch_id, _ = await _priced_workshop(db_session)
    client_id = await _resolve_client(client, access, phone="+998901880077", name="Budget")
    # 60 staff-minted drafts (over the client's own 50 cap) must not block the
    # client's own draft creation, nor each other.
    for _ in range(60):
        db_session.add(
            CuttingDraft(
                client_id=uuid.UUID(client_id),
                preferred_branch_id=branch_id,
                created_via_workshop_id=workshop_id,
                parts_snapshot=[],
            )
        )
    await db_session.flush()
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=uuid.UUID(client_id),
    )
    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(tokens.access_token))
    assert created.status_code == 201
    own_count = await db_session.scalar(
        select(func.count(CuttingDraft.id)).where(
            CuttingDraft.client_id == uuid.UUID(client_id),
            CuttingDraft.created_via_workshop_id.is_(None),
        )
    )
    assert own_count == 1


async def test_workshop_saved_drafts_index(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, _ = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    dilshod = await _resolve_client(client, access, phone="+998901112255", name="Walk-in Dilshod")
    aziza = await _resolve_client(client, access, phone="+998901112266", name="Walk-in Aziza")

    # An optimised draft (ready for checkout) and a bare one (still in progress).
    optimized_id = await _optimized_workshop_draft(
        client, access, client_id=dilshod, branch_id=branch_id, panel=panel, edge=edge
    )
    bare = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(access),
        json={"client_id": aziza, "branch_id": str(branch_id)},
    )
    assert bare.status_code == 201

    listed = await client.get("/api/v1/workshop/cutting-drafts", headers=_auth(access))
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert {row["id"] for row in rows} == {optimized_id, bare.json()["id"]}
    by_id = {row["id"]: row for row in rows}

    ready = by_id[optimized_id]
    assert ready["client_name"] == "Walk-in Dilshod"
    assert ready["client_phone"] == "+998901112255"
    assert ready["branch_name"]
    assert ready["part_count"] == 2
    assert ready["has_result"] is True
    assert ready["panel_count"] >= 1
    assert ready["waste_percentage"] is not None

    in_progress = by_id[bare.json()["id"]]
    assert in_progress["client_name"] == "Walk-in Aziza"
    assert in_progress["has_result"] is False
    assert in_progress["part_count"] == 0
    assert in_progress["waste_percentage"] is None


async def test_workshop_saved_drafts_index_scope_and_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_a, _, branch_a, _ = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_a)
    client_a = await _resolve_client(client, access_a, phone="+998901113344", name="A Client")
    draft_a = await _optimized_workshop_draft(
        client, access_a, client_id=client_a, branch_id=branch_a, panel=panel, edge=edge
    )

    # A different workshop never sees workshop A's drafts.
    access_b, _, _, _ = await _priced_workshop(db_session, login="owner_b")
    list_b = await client.get("/api/v1/workshop/cutting-drafts", headers=_auth(access_b))
    assert list_b.status_code == 200
    assert list_b.json() == []

    # process_production without manage_orders is rejected.
    prod_access = await _staff_access(
        db_session,
        workshop_id=(
            await db_session.get(CuttingDraft, uuid.UUID(draft_a))
        ).created_via_workshop_id,
        branch_id=branch_a,
        permission=Permission.PROCESS_PRODUCTION,
    )
    forbidden = await client.get("/api/v1/workshop/cutting-drafts", headers=_auth(prod_access))
    assert forbidden.status_code == 403

    # Once ordered, the draft is consumed and drops off the saved list.
    placed = await client.post(
        "/api/v1/workshop/orders",
        headers=_auth(access_a),
        json={
            "draft_id": draft_a,
            "branch_id": str(branch_a),
            "contact_name": "A Client",
            "contact_phone": "+998901113344",
        },
    )
    assert placed.status_code == 201, placed.text
    after = await client.get("/api/v1/workshop/cutting-drafts", headers=_auth(access_a))
    assert after.status_code == 200
    assert after.json() == []


async def test_workshop_saved_drafts_index_filters_by_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The saved-drafts surface follows the app's branch context (QAD-148): a
    draft is frozen to the branch it was started on, so `branch_id` narrows the
    list to that branch and omitting it still returns the whole workshop."""
    access, workshop_id, chilonzor, _ = await _priced_workshop(db_session)
    yunusobod = Branch(
        workshop_id=workshop_id,
        branch_no=await next_branch_no(db_session),
        name="Yunusobod-2",
        address="Tashkent, Yunusobod",
        phone="+998904444444",
        latitude=Decimal("41.365"),
        longitude=Decimal("69.285"),
    )
    db_session.add(yunusobod)
    await db_session.flush()

    walk_in = await _resolve_client(client, access, phone="+998901115577", name="Walk-in Aziza")
    here = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(access),
        json={"client_id": walk_in, "branch_id": str(chilonzor)},
    )
    assert here.status_code == 201, here.text
    there = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(access),
        json={"client_id": walk_in, "branch_id": str(yunusobod.id)},
    )
    assert there.status_code == 201, there.text

    unfiltered = await client.get("/api/v1/workshop/cutting-drafts", headers=_auth(access))
    assert unfiltered.status_code == 200
    assert {row["id"] for row in unfiltered.json()} == {here.json()["id"], there.json()["id"]}

    scoped = await client.get(
        f"/api/v1/workshop/cutting-drafts?branch_id={yunusobod.id}", headers=_auth(access)
    )
    assert scoped.status_code == 200, scoped.text
    assert [row["id"] for row in scoped.json()] == [there.json()["id"]]
    assert scoped.json()[0]["preferred_branch_id"] == str(yunusobod.id)
