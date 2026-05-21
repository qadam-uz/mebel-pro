"""Orders — placement, the production state machine, and reads.

The order is the production spine: it triggers the stock seam (inventory) and is
settled by the money seam (finance) without ever holding either balance. This
module owns placement (client), the workshop state machine (approve / assign /
cutting-done / banding-done / mark-collected / revert / cancel / discount), and
the client + workshop reads.

Spec: docs/ref/features/orders.md, docs/ref/entities/sales.md.

Pricing snapshot (frozen at creation, integer tiyin):

* cutting   = per_sheet: cutting_rate * sum(sheets); per_cut: cutting_rate * cut count
* materials = sum over shop materials (BranchMaterial.price_tiyin * that material's sheets)
* edge      = sum (edge_length_by_thickness[t] metres * branch edge_banding_rates[t])
* total     = cutting + materials + edge - discount  (>= 0)

``cut_count_snapshot`` is the number of placed part-instances in the chosen
result (Σ placements across its sheets) — a stable per-cut metric the result
exposes directly. ``sheets_used_snapshot`` is Σ sheets_used_by_material.

Edge-stock consumption resolves each banded thickness to the branch's active
``edge``-kind material of that thickness (BranchMaterial + Material), consuming
``ceil(mm / 1000)`` metres. A thickness with no matching shop edge material at
the branch is skipped gracefully (the workshop's loss, recorded offline) — order
creation never requires an edge stock item, only a configured banding *rate*.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, bad_request, forbidden, not_found
from app.core.principal import Principal
from app.models.catalog import BranchMaterial, BranchPricing, Material
from app.models.cutting import CuttingResult
from app.models.enums import (
    ActorType,
    BranchStatus,
    CancelledByType,
    CatalogStatus,
    CuttingResultStatus,
    MaterialKind,
    MaterialSource,
    OrderStatus,
    Permission,
    PrincipalType,
    WorkshopStatus,
)
from app.models.identity import Client, WorkshopUser
from app.models.sales import Order, OrderCancellation, OrderItem, OrderStatusEvent
from app.models.workshop import Branch, Workshop
from app.services import audit, cutting, inventory, recipients
from app.services import notifications as notif

# Statuses an order may be cancelled from (any pre-completed state).
_CANCELLABLE = (
    OrderStatus.NEW,
    OrderStatus.CONFIRMED,
    OrderStatus.CUTTING,
    OrderStatus.EDGE_BANDING,
    OrderStatus.READY,
)


# --- errors -----------------------------------------------------------------


def _conflict() -> AppError:
    return AppError(
        "order_conflict",
        "This order changed — refresh and try again.",
        status_code=409,
    )


def _result_not_usable(detail: str = "This cutting draft has no usable chosen result.") -> AppError:
    return AppError("cutting_result_not_usable", detail, status_code=409)


# --- thickness helpers ------------------------------------------------------


def _thickness_key(thickness: float) -> str:
    if thickness == int(thickness):
        return f"{thickness:.1f}"
    return f"{thickness:g}"


# --- pricing snapshot -------------------------------------------------------


class _PricedItem:
    """A snapshot row computed for one draft part."""

    def __init__(
        self,
        *,
        material_id: uuid.UUID,
        material_source: MaterialSource,
        material_snapshot: dict[str, Any],
        part_ref: str,
        length_mm: int,
        width_mm: int,
        quantity: int,
        edges: tuple[float | None, float | None, float | None, float | None],
        unit_cutting_price_tiyin: int,
        unit_material_price_tiyin: int,
        edge_cost_tiyin: int,
    ) -> None:
        self.material_id = material_id
        self.material_source = material_source
        self.material_snapshot = material_snapshot
        self.part_ref = part_ref
        self.length_mm = length_mm
        self.width_mm = width_mm
        self.quantity = quantity
        self.edges = edges
        self.unit_cutting_price_tiyin = unit_cutting_price_tiyin
        self.unit_material_price_tiyin = unit_material_price_tiyin
        self.edge_cost_tiyin = edge_cost_tiyin

    @property
    def line_total_tiyin(self) -> int:
        return (
            self.unit_cutting_price_tiyin + self.unit_material_price_tiyin
        ) * self.quantity + self.edge_cost_tiyin


class PricingSnapshot:
    """The fully-computed price snapshot for an order, ready to persist."""

    def __init__(
        self,
        *,
        subtotal_cutting_tiyin: int,
        subtotal_materials_tiyin: int,
        subtotal_edge_banding_tiyin: int,
        total_tiyin: int,
        sheets_used: int,
        cut_count: int,
        items: list[_PricedItem],
    ) -> None:
        self.subtotal_cutting_tiyin = subtotal_cutting_tiyin
        self.subtotal_materials_tiyin = subtotal_materials_tiyin
        self.subtotal_edge_banding_tiyin = subtotal_edge_banding_tiyin
        self.total_tiyin = total_tiyin
        self.sheets_used = sheets_used
        self.cut_count = cut_count
        self.items = items


async def _placement_count(db: AsyncSession, result: CuttingResult) -> int:
    """Total placed part-instances across the result's sheets — the cut count."""
    _r, layout = await cutting.load_result_with_layout(db, result.id)
    return sum(len(placements) for _sheet, placements in layout)


async def _material_snapshot(
    db: AsyncSession, material: Material, price_tiyin: int
) -> dict[str, Any]:
    return {
        "name": material.name,
        "type": material.type.value if material.type else None,
        "thickness_mm": float(material.thickness_mm),
        "color": material.color,
        "decor_code": material.decor_code,
        "sheet_length_mm": material.sheet_length_mm,
        "sheet_width_mm": material.sheet_width_mm,
        "price_tiyin": price_tiyin,
    }


async def _branch_edge_materials(
    db: AsyncSession, branch_id: uuid.UUID
) -> dict[str, tuple[uuid.UUID, int]]:
    """thickness_key -> (material_id, price_tiyin) for the branch's active shop
    edge materials. Used both to price (informally) and to consume edge stock."""
    rows = (
        await db.execute(
            select(Material, BranchMaterial.price_tiyin)
            .join(BranchMaterial, BranchMaterial.material_id == Material.id)
            .where(
                BranchMaterial.branch_id == branch_id,
                BranchMaterial.status == CatalogStatus.ACTIVE,
                Material.status == CatalogStatus.ACTIVE,
                Material.kind == MaterialKind.EDGE,
            )
        )
    ).all()
    out: dict[str, tuple[uuid.UUID, int]] = {}
    for material, price in rows:
        out[_thickness_key(float(material.thickness_mm))] = (material.id, int(price))
    return out


async def compute_pricing(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    parts_snapshot: list[dict[str, Any]],
    result: CuttingResult,
) -> PricingSnapshot:
    """Freeze the price against the branch's rates and the chosen result.

    Fails loudly: ``missing_cutting_model`` if the branch has no cutting model,
    ``missing_edge_rate`` if a banded thickness has no configured rate.
    """
    pricing = await db.get(BranchPricing, branch_id)
    if pricing is None or pricing.cutting_model is None:
        raise AppError(
            "missing_cutting_model",
            "This branch can't take orders right now (no cutting model set).",
            status_code=422,
        )

    sheets_by_material: dict[str, int] = {
        str(k): int(v) for k, v in (result.sheets_used_by_material or {}).items()
    }
    total_sheets = sum(sheets_by_material.values())
    cut_count = await _placement_count(db, result)

    # --- cutting subtotal ---
    if pricing.cutting_model.value == "per_sheet":
        subtotal_cutting = int(pricing.cutting_rate_tiyin) * total_sheets
    else:  # per_cut
        subtotal_cutting = int(pricing.cutting_rate_tiyin) * cut_count

    # --- group parts by material; gather shop sheet materials ---
    parts = list(parts_snapshot or [])
    shop_sheet_material_ids = sorted(
        {
            uuid.UUID(p["material_id"])
            for p in parts
            if p.get("material_source") == MaterialSource.SHOP.value
        },
        key=str,
    )
    branch_prices: dict[uuid.UUID, int] = {}
    if shop_sheet_material_ids:
        rows = (
            await db.execute(
                select(BranchMaterial.material_id, BranchMaterial.price_tiyin).where(
                    BranchMaterial.branch_id == branch_id,
                    BranchMaterial.material_id.in_(shop_sheet_material_ids),
                    BranchMaterial.status == CatalogStatus.ACTIVE,
                )
            )
        ).all()
        branch_prices = {mid: int(price) for mid, price in rows}

    # --- materials subtotal: branch price  x sheets attributable to that material ---
    subtotal_materials = 0
    for mid in shop_sheet_material_ids:
        sheets = sheets_by_material.get(str(mid), 0)
        subtotal_materials += branch_prices.get(mid, 0) * sheets

    # --- edge banding subtotal: per-thickness metres  x branch rate ---
    edge_by_thickness: dict[str, int] = {
        str(k): int(v) for k, v in (result.edge_length_by_thickness or {}).items()
    }
    rates: dict[str, Any] = pricing.edge_banding_rates or {}
    subtotal_edge = 0
    for thickness_key, total_mm in edge_by_thickness.items():
        if total_mm <= 0:
            continue
        if thickness_key not in rates:
            raise AppError(
                "missing_edge_rate",
                f"This branch has no edge-banding rate for {thickness_key} mm.",
                status_code=422,
            )
        metres = total_mm / 1000.0
        subtotal_edge += round(metres * int(rates[thickness_key]))

    # --- per-item snapshot rows ---
    # Cutting cost is attributed per item proportionally by quantity so the line
    # totals reconstruct the cutting subtotal; material/edge are exact per item.
    total_qty = sum(int(p["quantity"]) for p in parts) or 1
    items: list[_PricedItem] = []
    cutting_assigned = 0
    materials_cache: dict[uuid.UUID, Material] = {}
    for idx, p in enumerate(parts):
        mid = uuid.UUID(p["material_id"])
        source = MaterialSource(p["material_source"])
        qty = int(p["quantity"])
        if mid not in materials_cache:
            mat = await db.get(Material, mid)
            if mat is None:
                raise not_found(f"Material {mid} not found.")
            materials_cache[mid] = mat
        material = materials_cache[mid]
        price_for_snapshot = branch_prices.get(mid, 0) if source is MaterialSource.SHOP else 0

        # cutting per-unit: distribute the subtotal across all part instances,
        # putting any rounding remainder on the last item.
        if idx == len(parts) - 1:
            line_cutting = subtotal_cutting - cutting_assigned
        else:
            line_cutting = round(subtotal_cutting * qty / total_qty)
            cutting_assigned += line_cutting
        unit_cutting = line_cutting // qty if qty else 0
        # keep cutting attribution exact by folding the per-line remainder into edge_cost? No —
        # store unit_cutting and let line_total use unit x qty; reconcile with edge_cost remainder.
        cutting_remainder = line_cutting - unit_cutting * qty

        # material per-unit (sheets are per-material, not per-item; charge 0 here and
        # carry materials at the order subtotal level — but the entity wants a unit price).
        # We attribute the material subtotal to its parts proportionally by quantity.
        unit_material = 0
        if source is MaterialSource.SHOP and price_for_snapshot:
            # share of this material's sheets cost over its parts' quantity
            unit_material = 0  # computed below per material group

        edges = (
            p.get("edge_top_mm"),
            p.get("edge_bottom_mm"),
            p.get("edge_left_mm"),
            p.get("edge_right_mm"),
        )
        edge_cost = _item_edge_cost(p, edges, rates)

        items.append(
            _PricedItem(
                material_id=mid,
                material_source=source,
                material_snapshot=await _material_snapshot(db, material, price_for_snapshot),
                part_ref=str(p["part_ref"]),
                length_mm=int(p["length_mm"]),
                width_mm=int(p["width_mm"]),
                quantity=qty,
                edges=edges,
                unit_cutting_price_tiyin=unit_cutting,
                unit_material_price_tiyin=unit_material,
                edge_cost_tiyin=edge_cost + cutting_remainder,
            )
        )

    # attribute materials subtotal across shop items proportionally by quantity
    _attribute_materials(items, shop_sheet_material_ids, sheets_by_material, branch_prices)

    total = max(subtotal_cutting + subtotal_materials + subtotal_edge, 0)
    return PricingSnapshot(
        subtotal_cutting_tiyin=subtotal_cutting,
        subtotal_materials_tiyin=subtotal_materials,
        subtotal_edge_banding_tiyin=subtotal_edge,
        total_tiyin=total,
        sheets_used=total_sheets,
        cut_count=cut_count,
        items=items,
    )


def _item_edge_cost(
    part: dict[str, Any],
    edges: tuple[float | None, float | None, float | None, float | None],
    rates: dict[str, Any],
) -> int:
    """Edge cost for one item line = Σ banded side length  x qty  x rate (metres)."""
    length_mm = int(part["length_mm"])
    width_mm = int(part["width_mm"])
    qty = int(part["quantity"])
    top, bottom, left, right = edges
    cost = 0.0
    for thickness, side_len in (
        (top, length_mm),
        (bottom, length_mm),
        (left, width_mm),
        (right, width_mm),
    ):
        if thickness:
            key = _thickness_key(float(thickness))
            rate = int(rates.get(key, 0))
            cost += (side_len * qty / 1000.0) * rate
    return round(cost)


def _attribute_materials(
    items: list[_PricedItem],
    shop_material_ids: list[uuid.UUID],
    sheets_by_material: dict[str, int],
    branch_prices: dict[uuid.UUID, int],
) -> None:
    """Spread each material's sheet cost across its shop items by quantity, as a
    per-unit material price (the remainder lands on the material's last item)."""
    for mid in shop_material_ids:
        material_cost = branch_prices.get(mid, 0) * sheets_by_material.get(str(mid), 0)
        if material_cost <= 0:
            continue
        group = [
            it
            for it in items
            if it.material_id == mid and it.material_source is MaterialSource.SHOP
        ]
        total_qty = sum(it.quantity for it in group) or 1
        assigned = 0
        for i, it in enumerate(group):
            if i == len(group) - 1:
                line = material_cost - assigned
            else:
                line = round(material_cost * it.quantity / total_qty)
                assigned += line
            it.unit_material_price_tiyin = line // it.quantity if it.quantity else 0
            remainder = line - it.unit_material_price_tiyin * it.quantity
            it.edge_cost_tiyin += remainder


# --- order number sequence --------------------------------------------------


async def _next_order_number(db: AsyncSession) -> str:
    """``ORD-YYYY-NNNNNN`` — a per-year sequence (count of this year's orders + 1)."""
    year = datetime.now(UTC).year
    prefix = f"ORD-{year}-"
    count = (
        await db.execute(
            select(func.count()).select_from(Order).where(Order.order_number.like(f"{prefix}%"))
        )
    ).scalar_one()
    return f"{prefix}{int(count) + 1:06d}"


# --- placement (client) -----------------------------------------------------


async def place_order(
    db: AsyncSession,
    principal: Principal,
    *,
    draft_id: uuid.UUID,
    branch_id: uuid.UUID,
    contact_name: str,
    contact_phone: str,
    note_client: str | None = None,
) -> Order:
    """Place an order from a chosen cutting result (CLIENT only). One transaction."""
    if not principal.is_client:
        raise forbidden()

    draft = await cutting.get_owned_draft(db, principal.id, draft_id)
    result = await cutting.get_chosen_result(db, draft)
    if result is None or result.status is not CuttingResultStatus.CANDIDATE:
        raise _result_not_usable()

    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise not_found("Branch not found.")
    if branch.status is not BranchStatus.ACTIVE:
        raise AppError("branch_closed", "This branch can't take orders right now.", status_code=409)

    workshop = await db.get(Workshop, branch.workshop_id)
    if workshop is None or workshop.status is not WorkshopStatus.ACTIVE:
        raise AppError("workshop_blocked", "This workshop is unavailable.", status_code=409)

    parts = list(draft.parts_snapshot or [])
    shop_ids = {
        uuid.UUID(p["material_id"])
        for p in parts
        if p.get("material_source") == MaterialSource.SHOP.value
    }
    # branch must carry every shop material (active BranchMaterial)
    if shop_ids:
        carried = set(
            (
                await db.execute(
                    select(BranchMaterial.material_id).where(
                        BranchMaterial.branch_id == branch_id,
                        BranchMaterial.material_id.in_(shop_ids),
                        BranchMaterial.status == CatalogStatus.ACTIVE,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not shop_ids <= carried:
            raise AppError(
                "branch_closed",
                "This branch does not carry every material in this cutting.",
                status_code=409,
            )

    snapshot = await compute_pricing(db, branch_id=branch_id, parts_snapshot=parts, result=result)

    order = Order(
        order_number=await _next_order_number(db),
        client_id=principal.id,
        workshop_id=branch.workshop_id,
        branch_id=branch_id,
        cutting_result_id=result.id,
        status=OrderStatus.NEW,
        version=1,
        note_client=note_client.strip() if note_client else None,
        contact_name=contact_name.strip(),
        contact_phone=contact_phone.strip(),
        subtotal_cutting_tiyin=snapshot.subtotal_cutting_tiyin,
        subtotal_materials_tiyin=snapshot.subtotal_materials_tiyin,
        subtotal_edge_banding_tiyin=snapshot.subtotal_edge_banding_tiyin,
        discount_tiyin=0,
        total_tiyin=snapshot.total_tiyin,
    )
    db.add(order)
    await db.flush()

    for it in snapshot.items:
        db.add(
            OrderItem(
                order_id=order.id,
                material_id=it.material_id,
                material_source=it.material_source,
                material_snapshot=it.material_snapshot,
                part_ref=it.part_ref,
                length_mm=it.length_mm,
                width_mm=it.width_mm,
                quantity=it.quantity,
                edge_top_mm=it.edges[0],
                edge_bottom_mm=it.edges[1],
                edge_left_mm=it.edges[2],
                edge_right_mm=it.edges[3],
                unit_cutting_price_tiyin=it.unit_cutting_price_tiyin,
                unit_material_price_tiyin=it.unit_material_price_tiyin,
                edge_cost_tiyin=it.edge_cost_tiyin,
                line_total_tiyin=it.line_total_tiyin,
            )
        )
    await db.flush()

    # bind + confirm the cutting result (deletes the draft and other candidates)
    await cutting.confirm_result_for_order(db, draft, order.id)

    await _record_transition(
        db,
        order,
        from_status=None,
        to_status=OrderStatus.NEW,
        actor=principal,
        action="order.placed",
        summary=f"Placed order {order.order_number}",
    )

    # notify the branch's manage_orders staff + owner of the new order
    await notif.notify_many(
        db,
        recipients=await recipients.branch_recipients(
            db, branch.workshop_id, branch_id, Permission.MANAGE_ORDERS
        ),
        event_code="order.placed",
        entity_type="order",
        entity_id=order.id,
        payload={"order_number": order.order_number, "branch_id": str(branch_id)},
    )

    await db.refresh(order)
    return order


# --- transition plumbing ----------------------------------------------------


async def _record_transition(
    db: AsyncSession,
    order: Order,
    *,
    from_status: OrderStatus | None,
    to_status: OrderStatus,
    actor: Principal | None,
    action: str,
    reason: str | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write the OrderStatusEvent + ActionLog + StatusChangeLog for a transition."""
    actor_type, actor_user_id, actor_client_id = _actor_fields(actor)
    db.add(
        OrderStatusEvent(
            order_id=order.id,
            from_status=from_status,
            to_status=to_status,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            actor_client_id=actor_client_id,
            reason=reason,
            event_metadata=metadata,
        )
    )
    await db.flush()
    log = await audit.record_action(
        db,
        actor=actor,
        action=action,
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=summary,
        details=metadata,
    )
    await audit.record_status_change(
        db,
        entity_type="order",
        entity_id=order.id,
        from_status=from_status.value if from_status else None,
        to_status=to_status.value,
        actor=actor,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        reason=reason,
        action_log_id=log.id,
    )


def _actor_fields(
    principal: Principal | None,
) -> tuple[ActorType, uuid.UUID | None, uuid.UUID | None]:
    if principal is None:
        return ActorType.SYSTEM, None, None
    if principal.type is PrincipalType.CLIENT:
        return ActorType.CLIENT, None, principal.id
    return ActorType.WORKSHOP_USER, principal.id, None


def _bump_version(order: Order, expected: int | None) -> None:
    """Optimistic lock: if the caller gave a version it must match; then bump."""
    if expected is not None and order.version != expected:
        raise _conflict()
    order.version += 1


async def _notify_client_status(db: AsyncSession, order: Order) -> None:
    await notif.notify(
        db,
        recipient_type=PrincipalType.CLIENT,
        recipient_id=order.client_id,
        event_code="order.status_changed",
        entity_type="order",
        entity_id=order.id,
        payload={"order_number": order.order_number, "status": order.status.value},
    )


# --- access -----------------------------------------------------------------


async def _scoped_order_for_workshop(
    db: AsyncSession, principal: Principal, order_id: uuid.UUID
) -> Order:
    """Resolve an order in the principal's workshop (tenancy from stored data)."""
    order = await db.get(Order, order_id)
    if order is None or order.workshop_id != principal.workshop_id:
        raise not_found("Order not found.")
    return order


def _require_manage_orders(principal: Principal, order: Order) -> None:
    if not principal.has_permission(Permission.MANAGE_ORDERS, order.branch_id):
        raise forbidden()


# --- transitions (workshop staff) -------------------------------------------


async def approve(
    db: AsyncSession, principal: Principal, order_id: uuid.UUID, *, expected_version: int | None
) -> tuple[Order, list[dict[str, Any]]]:
    """new → confirmed. Returns the order + non-blocking shop-stock warnings."""
    order = await _scoped_order_for_workshop(db, principal, order_id)
    _require_manage_orders(principal, order)
    if order.status is not OrderStatus.NEW:
        raise bad_request("Only a new order can be approved.", code="invalid_transition")
    _bump_version(order, expected_version)
    order.status = OrderStatus.CONFIRMED
    order.confirmed_at = datetime.now(UTC)
    await db.flush()
    await _record_transition(
        db,
        order,
        from_status=OrderStatus.NEW,
        to_status=OrderStatus.CONFIRMED,
        actor=principal,
        action="order.approved",
    )
    await _notify_client_status(db, order)
    warnings = await shop_stock_warnings(db, order)
    await db.refresh(order)
    return order, warnings


async def shop_stock_warnings(db: AsyncSession, order: Order) -> list[dict[str, Any]]:
    """Projected-balance warning per shop sheet material (non-blocking)."""
    items = await _order_items(db, order.id)
    out: list[dict[str, Any]] = []
    seen: set[uuid.UUID] = set()
    for it in items:
        if it.material_source is not MaterialSource.SHOP or it.material_id in seen:
            continue
        seen.add(it.material_id)
        projected = await inventory.projected_balance(
            db, branch_id=order.branch_id, material_id=it.material_id
        )
        sheets = int(
            (order_result_sheets(await _order_result(db, order)) or {}).get(str(it.material_id), 0)
        )
        if projected < sheets:
            out.append(
                {
                    "material_id": str(it.material_id),
                    "projected_balance": projected,
                    "sheets_needed": sheets,
                }
            )
    return out


async def _order_result(db: AsyncSession, order: Order) -> CuttingResult:
    result = await db.get(CuttingResult, order.cutting_result_id)
    if result is None:
        raise not_found("Cutting result not found.")
    return result


def order_result_sheets(result: CuttingResult) -> dict[str, int]:
    return {str(k): int(v) for k, v in (result.sheets_used_by_material or {}).items()}


async def assign_cutter(
    db: AsyncSession,
    principal: Principal,
    order_id: uuid.UUID,
    *,
    cutter_user_id: uuid.UUID,
    edger_user_id: uuid.UUID | None,
    expected_version: int | None,
) -> Order:
    """confirmed → cutting. Assignment IS the trigger; assign edger if banded."""
    order = await _scoped_order_for_workshop(db, principal, order_id)
    _require_manage_orders(principal, order)
    if order.status is not OrderStatus.CONFIRMED:
        raise bad_request("Only a confirmed order can be assigned.", code="invalid_transition")
    await _validate_production_user(db, order, cutter_user_id)
    banded = await order_has_banded_parts(db, order)
    if banded:
        if edger_user_id is None:
            raise bad_request(
                "This order has banded parts; assign an edger too.", code="edger_required"
            )
        await _validate_production_user(db, order, edger_user_id)
    _bump_version(order, expected_version)
    order.assigned_cutter_user_id = cutter_user_id
    order.assigned_edger_user_id = edger_user_id if banded else None
    order.status = OrderStatus.CUTTING
    await db.flush()
    await _record_transition(
        db,
        order,
        from_status=OrderStatus.CONFIRMED,
        to_status=OrderStatus.CUTTING,
        actor=principal,
        action="order.assigned",
        metadata={
            "assigned_cutter_user_id": str(cutter_user_id),
            "assigned_edger_user_id": str(edger_user_id) if (banded and edger_user_id) else None,
        },
    )
    await _notify_client_status(db, order)
    await db.refresh(order)
    return order


async def _validate_production_user(
    db: AsyncSession, order: Order, user_id: uuid.UUID
) -> WorkshopUser:
    """A cutter/edger must hold process_production on the branch and have
    home_branch_id == order.branch_id — except the owner (exempt)."""
    user = await db.get(WorkshopUser, user_id)
    if user is None or user.workshop_id != order.workshop_id:
        raise not_found("Workshop user not found.")
    if user.is_owner:
        return user
    # non-owner: must hold the grant on this branch AND be home there
    has_grant = await _has_production_grant(db, user_id, order.branch_id)
    if not has_grant or user.home_branch_id != order.branch_id:
        raise AppError(
            "invalid_assignee",
            "The cutter/edger must work this branch and hold process_production here.",
            status_code=422,
        )
    return user


async def _has_production_grant(db: AsyncSession, user_id: uuid.UUID, branch_id: uuid.UUID) -> bool:
    from app.models.identity import PermissionGrant

    n = (
        await db.execute(
            select(func.count())
            .select_from(PermissionGrant)
            .where(
                PermissionGrant.workshop_user_id == user_id,
                PermissionGrant.branch_id == branch_id,
                PermissionGrant.permission == Permission.PROCESS_PRODUCTION,
            )
        )
    ).scalar_one()
    return int(n) > 0


async def order_has_banded_parts(db: AsyncSession, order: Order) -> bool:
    result = await _order_result(db, order)
    edges = result.edge_length_by_thickness or {}
    return any(int(v) > 0 for v in edges.values())


def _resolve_credited_user(
    principal: Principal, assignee: uuid.UUID | None, on_behalf_user_id: uuid.UUID | None
) -> uuid.UUID:
    """Who gets credited: the explicit on-behalf pick, else the assignee, else
    the acting principal (a manage_orders user doing it themselves)."""
    if on_behalf_user_id is not None:
        return on_behalf_user_id
    if assignee is not None:
        return assignee
    return principal.id


async def cutting_done(
    db: AsyncSession,
    principal: Principal,
    order_id: uuid.UUID,
    *,
    on_behalf_user_id: uuid.UUID | None,
    expected_version: int | None,
) -> Order:
    """cutting → edge_banding | ready. Stamps the cutter + snapshot; consumes
    shop sheet stock. process_production (the assignee) OR manage_orders on-behalf."""
    order = await _scoped_order_for_workshop(db, principal, order_id)
    if order.status is not OrderStatus.CUTTING:
        raise bad_request("This order is not at the cutting step.", code="invalid_transition")
    credited = await _authorize_production(
        db, principal, order, order.assigned_cutter_user_id, on_behalf_user_id
    )

    _bump_version(order, expected_version)
    result = await _order_result(db, order)
    sheets_by_material = order_result_sheets(result)
    order.cutter_user_id = credited
    order.cut_completed_at = datetime.now(UTC)
    order.sheets_used_snapshot = sum(sheets_by_material.values())
    order.cut_count_snapshot = await _placement_count(db, result)

    # consume shop SHEET stock (per shop sheet material  x sheets)
    for material_id in await _shop_sheet_material_ids(db, order):
        sheets = sheets_by_material.get(str(material_id), 0)
        if sheets > 0:
            await inventory.consume(
                db,
                branch_id=order.branch_id,
                material_id=material_id,
                qty=sheets,
                order_id=order.id,
            )

    banded = await order_has_banded_parts(db, order)
    to_status = OrderStatus.EDGE_BANDING if banded else OrderStatus.READY
    order.status = to_status
    await db.flush()
    await _record_transition(
        db,
        order,
        from_status=OrderStatus.CUTTING,
        to_status=to_status,
        actor=principal,
        action="order.cutting_done",
        metadata={"credited_user_id": str(credited)},
    )
    await _notify_client_status(db, order)
    await db.refresh(order)
    return order


async def banding_done(
    db: AsyncSession,
    principal: Principal,
    order_id: uuid.UUID,
    *,
    on_behalf_user_id: uuid.UUID | None,
    expected_version: int | None,
) -> Order:
    """edge_banding → ready. Stamps the edger + metres; consumes shop edge stock."""
    order = await _scoped_order_for_workshop(db, principal, order_id)
    if order.status is not OrderStatus.EDGE_BANDING:
        raise bad_request("This order is not at the banding step.", code="invalid_transition")
    credited = await _authorize_production(
        db, principal, order, order.assigned_edger_user_id, on_behalf_user_id
    )

    _bump_version(order, expected_version)
    result = await _order_result(db, order)
    edge_by_thickness = {str(k): int(v) for k, v in (result.edge_length_by_thickness or {}).items()}
    order.edger_user_id = credited
    order.edge_completed_at = datetime.now(UTC)
    order.edge_length_snapshot = edge_by_thickness

    # consume shop EDGE stock: resolve each thickness → branch edge material (metres)
    if await _order_has_shop_parts(db, order):
        edge_materials = await _branch_edge_materials(db, order.branch_id)
        for thickness_key, total_mm in edge_by_thickness.items():
            if total_mm <= 0 or thickness_key not in edge_materials:
                continue  # no matching shop edge material → skip gracefully
            material_id, _price = edge_materials[thickness_key]
            metres = math.ceil(total_mm / 1000)
            if metres > 0:
                await inventory.consume(
                    db,
                    branch_id=order.branch_id,
                    material_id=material_id,
                    qty=metres,
                    order_id=order.id,
                )

    order.status = OrderStatus.READY
    await db.flush()
    await _record_transition(
        db,
        order,
        from_status=OrderStatus.EDGE_BANDING,
        to_status=OrderStatus.READY,
        actor=principal,
        action="order.banding_done",
        metadata={"credited_user_id": str(credited)},
    )
    await _notify_client_status(db, order)
    await db.refresh(order)
    return order


async def _authorize_production(
    db: AsyncSession,
    principal: Principal,
    order: Order,
    assignee: uuid.UUID | None,
    on_behalf_user_id: uuid.UUID | None,
) -> uuid.UUID:
    """A production-completion is allowed if the actor holds process_production on
    the branch (the worker themselves) or manage_orders (on-behalf). Returns the
    credited user id; validates an on-behalf pick is a valid production user."""
    is_worker = principal.has_permission(Permission.PROCESS_PRODUCTION, order.branch_id)
    is_manager = principal.has_permission(Permission.MANAGE_ORDERS, order.branch_id)
    if not (is_worker or is_manager):
        raise forbidden()
    if on_behalf_user_id is not None:
        if not is_manager:
            raise forbidden("On-behalf completion requires manage_orders.")
        await _validate_production_user(db, order, on_behalf_user_id)
    return _resolve_credited_user(principal, assignee, on_behalf_user_id)


async def mark_collected(
    db: AsyncSession, principal: Principal, order_id: uuid.UUID, *, expected_version: int | None
) -> Order:
    """ready → completed. Stamps picked_up_at."""
    order = await _scoped_order_for_workshop(db, principal, order_id)
    _require_manage_orders(principal, order)
    if order.status is not OrderStatus.READY:
        raise bad_request("Only a ready order can be collected.", code="invalid_transition")
    _bump_version(order, expected_version)
    order.status = OrderStatus.COMPLETED
    order.completed_at = datetime.now(UTC)
    order.picked_up_at = datetime.now(UTC)
    await db.flush()
    await _record_transition(
        db,
        order,
        from_status=OrderStatus.READY,
        to_status=OrderStatus.COMPLETED,
        actor=principal,
        action="order.collected",
    )
    await _notify_client_status(db, order)
    await db.refresh(order)
    return order


_REVERT_TARGET: dict[OrderStatus, tuple[OrderStatus, ...]] = {
    OrderStatus.CUTTING: (OrderStatus.CONFIRMED,),
    OrderStatus.EDGE_BANDING: (OrderStatus.CUTTING,),
    OrderStatus.READY: (OrderStatus.EDGE_BANDING, OrderStatus.CUTTING),
}


async def revert(
    db: AsyncSession,
    principal: Principal,
    order_id: uuid.UUID,
    *,
    reason: str,
    expected_version: int | None,
) -> Order:
    """Revert one step (manage_orders + reason). Clears that step's stamps and
    restores the stock it consumed. Never out of completed/cancelled."""
    order = await _scoped_order_for_workshop(db, principal, order_id)
    _require_manage_orders(principal, order)
    if not reason or not reason.strip():
        raise bad_request("A revert requires a reason.", code="reason_required")
    if order.status not in _REVERT_TARGET:
        raise bad_request("This order can't be reverted.", code="invalid_transition")

    from_status = order.status
    # target: ready can go back to edge_banding (if banded) else cutting
    if from_status is OrderStatus.READY:
        banded = await order_has_banded_parts(db, order)
        to_status = OrderStatus.EDGE_BANDING if banded else OrderStatus.CUTTING
    else:
        to_status = _REVERT_TARGET[from_status][0]

    _bump_version(order, expected_version)

    # Reverse exactly the prior step's effects.
    if from_status is OrderStatus.CUTTING:
        # undo the assignment trigger (confirmed has no stamps/stock)
        order.assigned_cutter_user_id = None
        order.assigned_edger_user_id = None
    elif from_status is OrderStatus.EDGE_BANDING:
        # revert the cut step: restore sheets, clear cut stamps
        await _restore_sheet_stock(db, order)
        order.cutter_user_id = None
        order.cut_completed_at = None
        order.sheets_used_snapshot = None
        order.cut_count_snapshot = None
    elif from_status is OrderStatus.READY:
        if to_status is OrderStatus.EDGE_BANDING:
            # revert the banding step: restore edge stock, clear edge stamps
            await _restore_edge_stock(db, order)
            order.edger_user_id = None
            order.edge_completed_at = None
            order.edge_length_snapshot = None
        else:
            # no banding existed: revert the cut step (sheets)
            await _restore_sheet_stock(db, order)
            order.cutter_user_id = None
            order.cut_completed_at = None
            order.sheets_used_snapshot = None
            order.cut_count_snapshot = None

    order.status = to_status
    await db.flush()
    await _record_transition(
        db,
        order,
        from_status=from_status,
        to_status=to_status,
        actor=principal,
        action="order.reverted",
        reason=reason.strip(),
        summary=f"Reverted {from_status.value} → {to_status.value}",
    )
    await _notify_client_status(db, order)
    await db.refresh(order)
    return order


async def _restore_sheet_stock(db: AsyncSession, order: Order) -> None:
    result = await _order_result(db, order)
    sheets_by_material = order_result_sheets(result)
    for material_id in await _shop_sheet_material_ids(db, order):
        sheets = sheets_by_material.get(str(material_id), 0)
        if sheets > 0:
            await inventory.restore(
                db,
                branch_id=order.branch_id,
                material_id=material_id,
                qty=sheets,
                order_id=order.id,
            )


async def _restore_edge_stock(db: AsyncSession, order: Order) -> None:
    if not await _order_has_shop_parts(db, order):
        return
    result = await _order_result(db, order)
    edge_by_thickness = {str(k): int(v) for k, v in (result.edge_length_by_thickness or {}).items()}
    edge_materials = await _branch_edge_materials(db, order.branch_id)
    for thickness_key, total_mm in edge_by_thickness.items():
        if total_mm <= 0 or thickness_key not in edge_materials:
            continue
        material_id, _price = edge_materials[thickness_key]
        metres = math.ceil(total_mm / 1000)
        if metres > 0:
            await inventory.restore(
                db,
                branch_id=order.branch_id,
                material_id=material_id,
                qty=metres,
                order_id=order.id,
            )


async def cancel(
    db: AsyncSession,
    principal: Principal,
    order_id: uuid.UUID,
    *,
    reason: str,
    expected_version: int | None = None,
) -> Order:
    """Cancel a pre-completed order. Client may cancel only while new; staff
    (manage_orders) may cancel any pre-completed status. Consumed stock stays."""
    if not reason or not reason.strip():
        raise bad_request("A cancellation requires a reason.", code="reason_required")

    if principal.is_client:
        order = await db.get(Order, order_id)
        if order is None or order.client_id != principal.id:
            raise not_found("Order not found.")
        if order.status is not OrderStatus.NEW:
            raise bad_request(
                "You can only cancel an order while it is new.", code="invalid_transition"
            )
        cancelled_by_type = CancelledByType.CLIENT
    else:
        order = await _scoped_order_for_workshop(db, principal, order_id)
        _require_manage_orders(principal, order)
        if order.status not in _CANCELLABLE:
            raise bad_request("This order can't be cancelled.", code="invalid_transition")
        cancelled_by_type = CancelledByType.WORKSHOP_USER

    from_status = order.status
    _bump_version(order, expected_version)
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.now(UTC)
    db.add(
        OrderCancellation(
            order_id=order.id,
            cancelled_by_type=cancelled_by_type,
            cancelled_by_user_id=None if principal.is_client else principal.id,
            cancelled_by_client_id=principal.id if principal.is_client else None,
            reason=reason.strip(),
        )
    )
    await db.flush()
    await _record_transition(
        db,
        order,
        from_status=from_status,
        to_status=OrderStatus.CANCELLED,
        actor=principal,
        action="order.cancelled",
        reason=reason.strip(),
    )
    await _notify_client_status(db, order)
    await db.refresh(order)
    return order


async def apply_discount(
    db: AsyncSession,
    principal: Principal,
    order_id: uuid.UUID,
    *,
    discount_tiyin: int,
    reason: str,
    expected_version: int | None,
) -> Order:
    """Apply a discount (manage_orders + reason). Re-derives total; never negative."""
    order = await _scoped_order_for_workshop(db, principal, order_id)
    _require_manage_orders(principal, order)
    if order.status not in (OrderStatus.NEW, OrderStatus.CONFIRMED):
        raise bad_request(
            "A discount can only be applied before production.", code="invalid_transition"
        )
    if discount_tiyin < 0:
        raise bad_request("Discount must be >= 0.", code="invalid_discount")
    if not reason or not reason.strip():
        raise bad_request("A discount requires a reason.", code="reason_required")
    pre_discount = (
        order.subtotal_cutting_tiyin
        + order.subtotal_materials_tiyin
        + order.subtotal_edge_banding_tiyin
    )
    if discount_tiyin > pre_discount:
        raise bad_request("Discount can't exceed the pre-discount total.", code="invalid_discount")
    _bump_version(order, expected_version)
    order.discount_tiyin = discount_tiyin
    order.discount_reason = reason.strip()
    order.discount_applied_by_user_id = principal.id
    order.total_tiyin = max(pre_discount - discount_tiyin, 0)
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="order.discount_applied",
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=reason.strip(),
        details={"discount_tiyin": discount_tiyin},
    )
    await db.refresh(order)
    return order


# --- order item / material helpers ------------------------------------------


async def _order_items(db: AsyncSession, order_id: uuid.UUID) -> list[OrderItem]:
    return list(
        (
            await db.execute(
                select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
            )
        )
        .scalars()
        .all()
    )


async def _shop_sheet_material_ids(db: AsyncSession, order: Order) -> list[uuid.UUID]:
    items = await _order_items(db, order.id)
    return sorted(
        {it.material_id for it in items if it.material_source is MaterialSource.SHOP}, key=str
    )


async def _order_has_shop_parts(db: AsyncSession, order: Order) -> bool:
    items = await _order_items(db, order.id)
    return any(it.material_source is MaterialSource.SHOP for it in items)


# --- reads ------------------------------------------------------------------


async def list_client_orders(
    db: AsyncSession, client_id: uuid.UUID, *, scope: str = "all", search: str | None = None
) -> list[Order]:
    stmt = select(Order).where(Order.client_id == client_id)
    if scope == "active":
        stmt = stmt.where(Order.status.in_(_CANCELLABLE))
    elif scope == "completed":
        stmt = stmt.where(Order.status == OrderStatus.COMPLETED)
    elif scope == "cancelled":
        stmt = stmt.where(Order.status == OrderStatus.CANCELLED)
    if search:
        stmt = stmt.where(Order.order_number.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(Order.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def get_client_order(db: AsyncSession, client_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.client_id != client_id:
        raise not_found("Order not found.")
    return order


async def list_workshop_orders(
    db: AsyncSession,
    principal: Principal,
    *,
    branch_id: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    search: str | None = None,
) -> list[Order]:
    """Branch-scoped: owner sees all workshop branches; staff see granted branches."""
    assert principal.workshop_id is not None
    stmt = select(Order).where(Order.workshop_id == principal.workshop_id)
    if not principal.is_owner:
        accessible = principal.accessible_branches
        if not accessible:
            return []
        stmt = stmt.where(Order.branch_id.in_(accessible))
    if branch_id is not None:
        stmt = stmt.where(Order.branch_id == branch_id)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    if search:
        stmt = stmt.where(Order.order_number.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(Order.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def workshop_board_counts(
    db: AsyncSession, principal: Principal, *, branch_id: uuid.UUID | None = None
) -> dict[str, int]:
    """Per-status counts for the board columns (pre-completed statuses)."""
    orders = await list_workshop_orders(db, principal, branch_id=branch_id)
    counts: dict[str, int] = {s.value: 0 for s in _CANCELLABLE}
    for o in orders:
        if o.status.value in counts:
            counts[o.status.value] += 1
    return counts


async def list_my_production(
    db: AsyncSession, principal: Principal, *, statuses: tuple[OrderStatus, ...]
) -> list[Order]:
    """Orders in the given statuses assigned to this user (cutter workspace etc.)."""
    assert principal.workshop_id is not None
    stmt = select(Order).where(
        Order.workshop_id == principal.workshop_id,
        Order.status.in_(statuses),
    )
    return list((await db.execute(stmt)).scalars().all())


async def order_status_events(db: AsyncSession, order_id: uuid.UUID) -> list[OrderStatusEvent]:
    return list(
        (
            await db.execute(
                select(OrderStatusEvent)
                .where(OrderStatusEvent.order_id == order_id)
                .order_by(OrderStatusEvent.changed_at.asc())
            )
        )
        .scalars()
        .all()
    )


async def order_cancellation(db: AsyncSession, order_id: uuid.UUID) -> OrderCancellation | None:
    return (
        await db.execute(select(OrderCancellation).where(OrderCancellation.order_id == order_id))
    ).scalar_one_or_none()


async def order_items_for_read(db: AsyncSession, order_id: uuid.UUID) -> list[OrderItem]:
    return await _order_items(db, order_id)


async def order_client(db: AsyncSession, order: Order) -> Client | None:
    return await db.get(Client, order.client_id)
