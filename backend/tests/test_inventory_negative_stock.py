"""Negative stock (QAD-150): a bookkeeping gap must never block a worker.

The order-driven `consume` path records material that physically already moved,
so it may take a branch balance below zero and must work even when the material
was dropped from the branch catalog mid-order. Every human-facing path keeps the
non-negative guard.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    MaterialKind,
    PanelMaterialType,
    Permission,
    StockTransactionType,
    UserStatus,
)
from app.modules.access.contracts import PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, Manufacturer, Material
from app.modules.inventory.api import (
    consume_order_stock,
    list_stock,
    record_adjustment,
    restore_order_stock,
    stock_value,
)
from app.modules.inventory.contracts import StockItem
from app.modules.inventory.schemas import StockAdjustmentRequest
from app.modules.support.contracts import Notification
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner


async def _material(db: AsyncSession, *, name: str) -> Material:
    manufacturer = Manufacturer(name=f"Egger {uuid.uuid4().hex[:6]}", country="AT")
    db.add(manufacturer)
    await db.flush()
    material = Material(
        kind=MaterialKind.PANEL,
        manufacturer_id=manufacturer.id,
        type=PanelMaterialType.DSP,
        name=name,
        thickness_mm=Decimal("18"),
        color="Light oak",
        panel_length_mm=2800,
        panel_width_mm=2070,
        grain_direction=True,
    )
    db.add(material)
    await db.flush()
    return material


async def _stock_item(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    material_id: uuid.UUID,
    on_hand: int,
    min_stock: int = 0,
) -> StockItem:
    item = StockItem(
        branch_id=branch_id,
        material_id=material_id,
        on_hand=on_hand,
        min_stock=min_stock,
        updated_at=datetime.now(UTC),
    )
    db.add(item)
    await db.flush()
    return item


def _owner_principal(*, owner_id: uuid.UUID, workshop_id: uuid.UUID) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner_id,
        session_id=uuid.uuid4(),
        trace_id="negative-stock-test",
        workshop_id=workshop_id,
        is_owner=True,
    )


async def _inventory_staff(
    db: AsyncSession, *, workshop_id: uuid.UUID, branch_id: uuid.UUID
) -> WorkshopUser:
    """A non-owner `manage_inventory` grantee — the notification's real audience."""

    staff = WorkshopUser(
        workshop_id=workshop_id,
        login=f"stock-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("StaffTemp123"),
        full_name="Warehouse Staff",
        phone="+998901234111",
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
            permission=Permission.MANAGE_INVENTORY,
            branch_id=branch_id,
            granted_by_user_id=staff.id,
            granted_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return staff


async def test_consume_goes_negative_and_a_later_arrival_heals_it(db_session: AsyncSession) -> None:
    workshop, branch, _ = await seed_workshop_with_owner(db_session)
    staff = await _inventory_staff(db_session, workshop_id=workshop.id, branch_id=branch.id)
    material = await _material(db_session, name="Zero stock panel")
    db_session.add(
        BranchMaterial(branch_id=branch.id, material_id=material.id, price_tiyin=1, min_stock=0)
    )
    item = await _stock_item(db_session, branch_id=branch.id, material_id=material.id, on_hand=5)
    order_id = uuid.uuid4()

    transaction = await consume_order_stock(
        db_session,
        branch_id=branch.id,
        material_id=material.id,
        order_id=order_id,
        quantity=20,
    )

    assert transaction.balance_after == -15
    assert item.on_hand == -15

    # The arrival nobody entered, entered at last — the balance heals itself.
    await restore_order_stock(
        db_session,
        branch_id=branch.id,
        material_id=material.id,
        order_id=order_id,
        quantity=20,
    )
    assert item.on_hand == 5

    # And a revert from a negative balance moves it in the right direction.
    await consume_order_stock(
        db_session,
        branch_id=branch.id,
        material_id=material.id,
        order_id=order_id,
        quantity=20,
    )
    assert item.on_hand == -15
    restored = await restore_order_stock(
        db_session,
        branch_id=branch.id,
        material_id=material.id,
        order_id=order_id,
        quantity=8,
    )
    assert restored.balance_after == -7
    assert item.on_hand == -7

    # The branch's manage_inventory grantees hear about it.
    codes = set(
        (
            await db_session.scalars(
                select(Notification.event_code).where(Notification.recipient_id == staff.id)
            )
        ).all()
    )
    assert "inventory.negative_stock" in codes
    # Low stock is not a notification any more (QAD-182) — the Ombor badge and
    # the «Kam qolgan materiallar» filter carry that signal instead.
    assert "inventory.low_stock" not in codes


async def test_consume_works_for_a_material_dropped_from_the_branch_catalog(
    db_session: AsyncSession,
) -> None:
    _, branch, _ = await seed_workshop_with_owner(db_session)
    material = await _material(db_session, name="Unlisted panel")
    # No BranchMaterial row at all — the catalog entry was removed mid-order.

    transaction = await consume_order_stock(
        db_session,
        branch_id=branch.id,
        material_id=material.id,
        order_id=uuid.uuid4(),
        quantity=3,
    )

    assert transaction.balance_after == -3
    assert transaction.type is StockTransactionType.CONSUME
    # The material stays OUT of the branch catalog: what is offerable to new
    # clients is a different question from what physically moved.
    assert (
        await db_session.scalar(
            select(BranchMaterial).where(
                BranchMaterial.branch_id == branch.id,
                BranchMaterial.material_id == material.id,
            )
        )
        is None
    )


async def test_manual_stock_out_below_zero_is_still_rejected(db_session: AsyncSession) -> None:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)
    material = await _material(db_session, name="Guarded panel")
    db_session.add(
        BranchMaterial(branch_id=branch.id, material_id=material.id, price_tiyin=1, min_stock=0)
    )
    item = await _stock_item(db_session, branch_id=branch.id, material_id=material.id, on_hand=3)
    principal = _owner_principal(owner_id=owner.id, workshop_id=workshop.id)

    with pytest.raises(APIError) as excinfo:
        await record_adjustment(
            db_session,
            principal=principal,
            branch_id=branch.id,
            payload=StockAdjustmentRequest(
                material_id=material.id, quantity=-10, note="Fat-fingered stock take"
            ),
        )

    assert excinfo.value.code == "stock_below_zero"
    assert item.on_hand == 3


async def test_negative_rows_sort_first_and_count_against_stock_value(
    db_session: AsyncSession,
) -> None:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)
    # Alphabetically ahead of the negative one, so plain name ordering would win.
    healthy = await _material(db_session, name="Aaa healthy panel")
    negative = await _material(db_session, name="Zzz negative panel")
    for material in (healthy, negative):
        db_session.add(
            BranchMaterial(branch_id=branch.id, material_id=material.id, price_tiyin=1, min_stock=0)
        )
    await _stock_item(db_session, branch_id=branch.id, material_id=healthy.id, on_hand=4)
    await _stock_item(db_session, branch_id=branch.id, material_id=negative.id, on_hand=-2)
    principal = _owner_principal(owner_id=owner.id, workshop_id=workshop.id)

    rows = await list_stock(db_session, principal=principal, branch_id=branch.id)
    assert [row.material.name for row in rows] == [negative.name, healthy.name]

    # Never priced, so the figure is zero — but the negative row must not be
    # dropped by a `> 0` filter on the way there.
    assert await stock_value(db_session, principal=principal, branch_id=branch.id) == 0
