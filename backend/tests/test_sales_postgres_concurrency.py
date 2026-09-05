"""Postgres-only: concurrent order numbering and the branch-number advisory lock."""

import asyncio
import itertools
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.models import Base, import_all_models
from app.models.enums import Currency, OrderStatus
from app.modules.access.contracts import Client
from app.modules.cutting.contracts import CuttingResult
from app.modules.sales import service as sales_service
from app.modules.sales.contracts import Order
from app.modules.sales.service import _insert_order
from app.modules.workshop.api import next_branch_no
from app.modules.workshop.contracts import Branch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tests.factories import seed_workshop_with_owner

import_all_models()

pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_CONCURRENCY") != "1"
    or not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="set POSTGRES_CONCURRENCY=1 with a throwaway Postgres DATABASE_URL",
)

COLLIDING_NUMBER = "100001"


async def _fresh_engine() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def _add_branch(db: AsyncSession, *, workshop_id: uuid.UUID, name: str) -> Branch:
    branch = Branch(
        workshop_id=workshop_id,
        branch_no=await next_branch_no(db),
        name=name,
        address="Tashkent",
        phone="+998902222222",
    )
    db.add(branch)
    await db.flush()
    return branch


async def test_postgres_parallel_orders_survive_a_number_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eight simultaneous orders that all draw the same number still all land.

    The random number has no reservation and no lock — the retry on
    `uq_orders_order_number` is the entire collision strategy, and it only
    works if a duplicate-key failure costs one SAVEPOINT rather than the whole
    transaction. Postgres is where that is true or false: it refuses every
    later statement in an aborted transaction, which SQLite does not. Rigged so
    that every task's *first* draw is the same number, so seven of the eight
    must recover from a real unique violation raised by a concurrent commit.
    """
    engine, maker = await _fresh_engine()
    try:
        async with maker() as setup:
            workshop, branch, _ = await seed_workshop_with_owner(setup)
            buyer = Client(phone="+998901112233", name="Dilshod")
            setup.add(buyer)
            # Postgres enforces the FK; each order needs its own result row.
            results = [
                CuttingResult(
                    algorithm_name="guillotine",
                    algorithm_version="1",
                    kerf_mm=4,
                    edge_trim_mm=5,
                    waste_percentage=Decimal("0.1"),
                    total_cut_length_mm=0,
                    total_edge_length_mm=0,
                    created_at=datetime.now(UTC),
                )
                for _ in range(8)
            ]
            setup.add_all(results)
            await setup.commit()
            workshop_id, branch_id, buyer_id = workshop.id, branch.id, buyer.id
            result_ids = [result.id for result in results]

        drew_once: set[asyncio.Task[None] | None] = set()
        fallbacks = itertools.count(200_001)

        def _rigged_draw() -> str:
            task = asyncio.current_task()
            if task not in drew_once:
                drew_once.add(task)
                return COLLIDING_NUMBER
            return str(next(fallbacks))

        monkeypatch.setattr(sales_service, "_random_order_number", _rigged_draw)

        async def place(result_id: uuid.UUID) -> None:
            # One session per request, mirroring get_session.
            async with maker() as session:
                order = Order(
                    order_number=sales_service._random_order_number(),
                    client_id=buyer_id,
                    workshop_id=workshop_id,
                    branch_id=branch_id,
                    cutting_result_id=result_id,
                    status=OrderStatus.NEW,
                    version=1,
                    contact_name="Dilshod",
                    contact_phone="+998901112233",
                    subtotal_cutting_tiyin=0,
                    subtotal_materials_tiyin=0,
                    subtotal_edge_banding_tiyin=0,
                    discount_tiyin=0,
                    surcharge_tiyin=0,
                    total_tiyin=0,
                    currency=Currency.UZS,
                )
                await _insert_order(session, order)
                await session.commit()

        await asyncio.gather(*(place(result_id) for result_id in result_ids))

        async with maker() as verify:
            numbers = (await verify.scalars(select(Order.order_number))).all()
        assert len(numbers) == 8
        assert len(set(numbers)) == 8
        # Exactly one task kept the contested number; the rest redrew.
        assert COLLIDING_NUMBER in numbers
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def test_postgres_parallel_branch_creation_gets_distinct_branch_numbers() -> None:
    """`branch_no` is platform-wide unique and immutable — a race must not reuse one."""
    engine, maker = await _fresh_engine()
    try:
        async with maker() as setup:
            workshop, seeded, _ = await seed_workshop_with_owner(setup)
            await setup.commit()
            workshop_id, seeded_no = workshop.id, seeded.branch_no

        async def create(index: int) -> None:
            async with maker() as session:
                await _add_branch(session, workshop_id=workshop_id, name=f"Branch {index}")
                await session.commit()

        await asyncio.gather(*(create(index) for index in range(6)))

        async with maker() as verify:
            numbers = sorted((await verify.scalars(select(Branch.branch_no))).all())
            assert numbers == list(range(seeded_no, seeded_no + 7))
            assert await verify.scalar(select(func.count(Branch.id))) == 7
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
