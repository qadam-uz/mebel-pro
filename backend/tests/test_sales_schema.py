import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

ORDER_INSERT = text(
    """
    INSERT INTO orders (
        id,
        order_number,
        client_id,
        workshop_id,
        branch_id,
        cutting_result_id,
        status,
        version,
        subtotal_cutting_tiyin,
        subtotal_materials_tiyin,
        subtotal_edge_banding_tiyin,
        discount_tiyin,
        discount_reason,
        discount_applied_by_user_id,
        total_tiyin,
        currency
    )
    VALUES (
        :id,
        :order_number,
        :client_id,
        :workshop_id,
        :branch_id,
        :cutting_result_id,
        'new',
        1,
        :cutting,
        :materials,
        :edge,
        :discount,
        :discount_reason,
        :discount_applied_by_user_id,
        :total,
        'UZS'
    )
    """
)


def _uuid() -> str:
    return str(uuid.uuid4())


async def _insert_order(
    db_session: AsyncSession,
    *,
    discount: int,
    total: int,
    discount_reason: str | None = None,
    discount_applied_by_user_id: str | None = None,
) -> None:
    await db_session.execute(
        ORDER_INSERT,
        {
            "id": _uuid(),
            "order_number": f"ORD-{_uuid()}",
            "client_id": _uuid(),
            "workshop_id": _uuid(),
            "branch_id": _uuid(),
            "cutting_result_id": _uuid(),
            "cutting": 10_000,
            "materials": 20_000,
            "edge": 5_000,
            "discount": discount,
            "discount_reason": discount_reason,
            "discount_applied_by_user_id": discount_applied_by_user_id,
            "total": total,
        },
    )
    await db_session.flush()


async def test_order_discount_may_zero_but_not_negative_total(
    db_session: AsyncSession,
) -> None:
    await _insert_order(
        db_session,
        discount=35_000,
        discount_reason="Warranty goodwill",
        discount_applied_by_user_id=_uuid(),
        total=0,
    )


async def test_order_discount_cannot_exceed_pre_discount_total(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(IntegrityError):
        await _insert_order(
            db_session,
            discount=35_001,
            discount_reason="Too much",
            discount_applied_by_user_id=_uuid(),
            total=-1,
        )


async def test_order_total_must_match_discounted_subtotals(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(IntegrityError):
        await _insert_order(
            db_session,
            discount=5_000,
            discount_reason="Mismatch",
            discount_applied_by_user_id=_uuid(),
            total=35_000,
        )


async def test_positive_order_discount_requires_reason_and_actor(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(IntegrityError):
        await _insert_order(
            db_session,
            discount=5_000,
            total=30_000,
        )
