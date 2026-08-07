"""Negative stock (QAD-150): a bookkeeping gap must never block a worker.

The order-driven `consume` path records material that physically already moved,
so it may take a branch balance below zero and must work even when the material
was dropped from the branch catalog mid-order. Every human-facing path keeps the
non-negative guard.
"""

import uuid
from datetime import UTC, datetime

import pytest
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    MaterialStatus,
    Permission,
    StockTransactionType,
    UserStatus,
)
from app.modules.access.contracts import PermissionGrant, WorkshopUser
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

from tests.factories import (
    MaterialFixture,
    seed_manufacturer,
    seed_panel_material,
    seed_workshop_with_owner,
)


async def _stock_item(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    on_hand: int,
    min_stock: int = 0,
) -> StockItem:
    item = StockItem(
        branch_id=branch_id,
        branch_material_id=branch_material_id,
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


async def _material_named(
    db: AsyncSession, *, branch_id: uuid.UUID, maker: str, nomi: str
) -> MaterialFixture:
    """A carried panel whose manufacturer and decor names are both pinned."""
    return await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=await seed_manufacturer(db, name=f"{maker} {uuid.uuid4().hex[:6]}"),
        nomi=nomi,
        price_tiyin=1,
    )


async def test_consume_goes_negative_and_a_later_arrival_heals_it(db_session: AsyncSession) -> None:
    workshop, branch, _ = await seed_workshop_with_owner(db_session)
    staff = await _inventory_staff(db_session, workshop_id=workshop.id, branch_id=branch.id)
    material = await seed_panel_material(
        db_session, branch_id=branch.id, nomi="Zero stock panel", price_tiyin=1
    )
    item = await _stock_item(
        db_session, branch_id=branch.id, branch_material_id=material.id, on_hand=5
    )
    order_id = uuid.uuid4()

    transaction = await consume_order_stock(
        db_session,
        branch_id=branch.id,
        branch_material_id=material.id,
        order_id=order_id,
        quantity=20,
    )

    assert transaction.balance_after == -15
    assert item.on_hand == -15

    # The arrival nobody entered, entered at last — the balance heals itself.
    await restore_order_stock(
        db_session,
        branch_id=branch.id,
        branch_material_id=material.id,
        order_id=order_id,
        quantity=20,
    )
    assert item.on_hand == 5

    # And a revert from a negative balance moves it in the right direction.
    await consume_order_stock(
        db_session,
        branch_id=branch.id,
        branch_material_id=material.id,
        order_id=order_id,
        quantity=20,
    )
    assert item.on_hand == -15
    restored = await restore_order_stock(
        db_session,
        branch_id=branch.id,
        branch_material_id=material.id,
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
    """ "Dropped from the catalog" is now `status=inactive`, not a missing row.

    Before the reshape a branch material could vanish while an order was in
    flight, so consume had to mint one. A material *is* its branch row now — the
    order item FKs it, so it cannot disappear — and de-catalogued means inactive.
    The movement path deliberately applies no status filter: what is offerable to
    new clients is a different question from what physically moved.
    """
    _, branch, _ = await seed_workshop_with_owner(db_session)
    material = await seed_panel_material(
        db_session,
        branch_id=branch.id,
        nomi="Unlisted panel",
        price_tiyin=1,
        status=MaterialStatus.INACTIVE,
    )

    transaction = await consume_order_stock(
        db_session,
        branch_id=branch.id,
        branch_material_id=material.id,
        order_id=uuid.uuid4(),
        quantity=3,
    )

    assert transaction.balance_after == -3
    assert transaction.type is StockTransactionType.CONSUME
    # The stock row is created at zero and then goes negative; the catalog row
    # stays inactive — consuming it must not quietly re-list it for clients.
    assert material.branch_material.status is MaterialStatus.INACTIVE


async def test_consume_refuses_another_branchs_material(db_session: AsyncSession) -> None:
    """`stock_items.branch_id` is denormalized, so a mismatch must not be written.

    Resolving the branch material scoped by its own branch is what stops a
    cutting draft whose `preferred_branch_id` differs from the order's branch
    from creating a stock row whose branch disagrees with its material's.
    """
    _, branch, _ = await seed_workshop_with_owner(db_session)
    _, other_branch, _ = await seed_workshop_with_owner(
        db_session, login=f"other-{uuid.uuid4().hex[:6]}"
    )
    foreign = await seed_panel_material(db_session, branch_id=other_branch.id, price_tiyin=1)

    with pytest.raises(APIError) as excinfo:
        await consume_order_stock(
            db_session,
            branch_id=branch.id,
            branch_material_id=foreign.id,
            order_id=uuid.uuid4(),
            quantity=1,
        )

    assert excinfo.value.code == "branch_material_not_found"
    assert (
        await db_session.scalar(select(StockItem).where(StockItem.branch_material_id == foreign.id))
        is None
    )


async def test_manual_stock_out_below_zero_is_still_rejected(db_session: AsyncSession) -> None:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)
    material = await seed_panel_material(
        db_session, branch_id=branch.id, nomi="Guarded panel", price_tiyin=1
    )
    item = await _stock_item(
        db_session, branch_id=branch.id, branch_material_id=material.id, on_hand=3
    )
    principal = _owner_principal(owner_id=owner.id, workshop_id=workshop.id)

    with pytest.raises(APIError) as excinfo:
        await record_adjustment(
            db_session,
            principal=principal,
            branch_id=branch.id,
            payload=StockAdjustmentRequest(
                branch_material_id=material.id,
                quantity=-10,
                note="Fat-fingered stock take",
            ),
        )

    assert excinfo.value.code == "stock_below_zero"
    assert item.on_hand == 3


async def test_negative_rows_sort_first_and_count_against_stock_value(
    db_session: AsyncSession,
) -> None:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)
    # Ordering is by manufacturer, then decor name, then thickness — there is no
    # stored material name to sort on any more. Both names put the healthy row
    # ahead, so only the negative-first rule can pull the other one to the top.
    healthy = await _material_named(db_session, branch_id=branch.id, maker="Aaa", nomi="Aaa panel")
    negative = await _material_named(db_session, branch_id=branch.id, maker="Zzz", nomi="Zzz panel")
    await _stock_item(db_session, branch_id=branch.id, branch_material_id=healthy.id, on_hand=4)
    await _stock_item(db_session, branch_id=branch.id, branch_material_id=negative.id, on_hand=-2)
    principal = _owner_principal(owner_id=owner.id, workshop_id=workshop.id)

    rows = await list_stock(db_session, principal=principal, branch_id=branch.id)
    assert [row.stock_item.branch_material_id for row in rows] == [negative.id, healthy.id]
    # The label is computed, never stored — it still names the row for a human.
    assert "Zzz panel" in rows[0].label

    # Never priced, so the figure is zero — but the negative row must not be
    # dropped by a `> 0` filter on the way there.
    assert await stock_value(db_session, principal=principal, branch_id=branch.id) == 0
