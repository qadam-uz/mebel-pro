import asyncio
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.core.security import hash_password
from app.models import Base, import_all_models
from app.models.enums import (
    AuthenticatedPrincipalType,
    MaterialKind,
    MaterialStatus,
    PanelMaterialType,
    SupplierStatus,
)
from app.modules.access.contracts import WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, BranchPricing, Manufacturer, Material
from app.modules.inventory.api import create_invoice, record_adjustment
from app.modules.inventory.contracts import (
    StockItem,
    StockTransaction,
    Supplier,
    SupplierInvoice,
)
from app.modules.inventory.schemas import (
    StockAdjustmentRequest,
    SupplierInvoiceCreateRequest,
    SupplierInvoiceLineInput,
)
from app.modules.workshop.api import next_branch_no
from app.modules.workshop.contracts import Branch, Workshop
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.factories import default_working_hours

import_all_models()

pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_CONCURRENCY") != "1"
    or not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="set POSTGRES_CONCURRENCY=1 with a throwaway Postgres DATABASE_URL",
)


async def test_postgres_stock_adjustments_serialize_on_stock_item_lock() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with maker() as setup:
            workshop_id = uuid.uuid4()
            owner_id = uuid.uuid4()
            workshop = Workshop(
                id=workshop_id,
                owner_user_id=owner_id,
                name="Concurrent Workshop",
            )
            setup.add(workshop)
            await setup.flush()
            branch = Branch(
                workshop_id=workshop.id,
                branch_no=await next_branch_no(setup),
                name="Main",
                address="Tashkent",
                phone="+998902222222",
                latitude=Decimal("41.3"),
                longitude=Decimal("69.2"),
                working_hours=default_working_hours(),
            )
            setup.add(branch)
            await setup.flush()
            setup.add(BranchPricing(branch_id=branch.id))
            owner = WorkshopUser(
                id=owner_id,
                workshop_id=workshop.id,
                login="owner",
                password_hash=hash_password("Owner123"),
                full_name="Owner",
                phone="+998903333333",
                is_owner=True,
                home_branch_id=branch.id,
                password_reset_required=False,
            )
            manufacturer = Manufacturer(name="Egger", status=MaterialStatus.ACTIVE)
            setup.add_all([owner, manufacturer])
            await setup.flush()
            material = Material(
                kind=MaterialKind.PANEL,
                manufacturer_id=manufacturer.id,
                type=PanelMaterialType.DSP,
                name="Panel",
                thickness_mm=Decimal("18"),
                color="Oak",
                panel_length_mm=2800,
                panel_width_mm=2070,
                grain_direction=True,
                status=MaterialStatus.ACTIVE,
            )
            setup.add(material)
            await setup.flush()
            setup.add(
                BranchMaterial(
                    branch_id=branch.id,
                    material_id=material.id,
                    price_tiyin=100000,
                    min_stock=0,
                    status=MaterialStatus.ACTIVE,
                )
            )
            stock_item = StockItem(
                branch_id=branch.id,
                material_id=material.id,
                on_hand=10,
                min_stock=0,
                updated_at=datetime.now(UTC),
            )
            setup.add(stock_item)
            await setup.commit()

        principal = AuthenticatedPrincipal(
            principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
            principal_id=owner_id,
            session_id=uuid.uuid4(),
            trace_id="postgres-concurrency",
            workshop_id=workshop_id,
            is_owner=True,
        )

        async def adjust() -> object:
            async with maker() as session:
                try:
                    row = await record_adjustment(
                        session,
                        principal=principal,
                        branch_id=branch.id,
                        payload=StockAdjustmentRequest(
                            material_id=material.id,
                            quantity=-7,
                            note="Concurrent stock take",
                        ),
                    )
                    await session.commit()
                    return row
                except Exception as exc:
                    await session.rollback()
                    return exc

        results = await asyncio.gather(adjust(), adjust())
        errors = [result for result in results if isinstance(result, APIError)]
        successes = [result for result in results if not isinstance(result, Exception)]

        async with maker() as verify:
            final_on_hand = await verify.scalar(select(StockItem.on_hand))
            transaction_count = await verify.scalar(
                select(func.count()).select_from(StockTransaction)
            )

        assert len(successes) == 1
        assert len(errors) == 1
        assert errors[0].code == "stock_below_zero"
        assert final_on_hand == 3
        assert transaction_count == 1
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def test_postgres_concurrent_invoices_never_share_a_number() -> None:
    """`K-…` is minted from a count under an advisory lock, like order numbers.

    Two arrivals recorded at the same instant must serialize on that lock —
    without it both would read the same count and mint the same `K-0001`, which
    the per-workshop unique index would then reject as a 500 to one of them.
    """

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with maker() as setup:
            workshop_id = uuid.uuid4()
            owner_id = uuid.uuid4()
            setup.add(Workshop(id=workshop_id, owner_user_id=owner_id, name="Invoice Workshop"))
            await setup.flush()
            branch = Branch(
                workshop_id=workshop_id,
                branch_no=await next_branch_no(setup),
                name="Main",
                address="Tashkent",
                phone="+998902222223",
                latitude=Decimal("41.3"),
                longitude=Decimal("69.2"),
                working_hours=default_working_hours(),
            )
            setup.add(branch)
            await setup.flush()
            setup.add(BranchPricing(branch_id=branch.id))
            owner = WorkshopUser(
                id=owner_id,
                workshop_id=workshop_id,
                login="owner",
                password_hash=hash_password("Owner123"),
                full_name="Owner",
                phone="+998903333334",
                is_owner=True,
                home_branch_id=branch.id,
                password_reset_required=False,
            )
            manufacturer = Manufacturer(name="Kronospan", status=MaterialStatus.ACTIVE)
            setup.add_all([owner, manufacturer])
            await setup.flush()
            material = Material(
                kind=MaterialKind.PANEL,
                manufacturer_id=manufacturer.id,
                type=PanelMaterialType.DSP,
                name="Panel",
                thickness_mm=Decimal("18"),
                color="Ash",
                panel_length_mm=2800,
                panel_width_mm=2070,
                grain_direction=True,
                status=MaterialStatus.ACTIVE,
            )
            setup.add(material)
            await setup.flush()
            setup.add(
                BranchMaterial(
                    branch_id=branch.id,
                    material_id=material.id,
                    price_tiyin=100000,
                    min_stock=0,
                    status=MaterialStatus.ACTIVE,
                )
            )
            # The stock row exists up front, as it does for any material a
            # branch already carries: this test is about the numbering lock, and
            # racing the lazy first-arrival creation of a `stock_items` row would
            # trip the branch/material unique index instead — a different,
            # pre-existing race that has nothing to do with `K-…`.
            setup.add(
                StockItem(
                    branch_id=branch.id,
                    material_id=material.id,
                    on_hand=0,
                    min_stock=0,
                    updated_at=datetime.now(UTC),
                )
            )
            supplier = Supplier(
                workshop_id=workshop_id,
                name="Kronospan Osiyo",
                status=SupplierStatus.ACTIVE,
                created_by_user_id=owner_id,
            )
            setup.add(supplier)
            await setup.commit()

        principal = AuthenticatedPrincipal(
            principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
            principal_id=owner_id,
            session_id=uuid.uuid4(),
            trace_id="postgres-concurrency",
            workshop_id=workshop_id,
            is_owner=True,
        )

        async def record() -> object:
            async with maker() as session:
                try:
                    row = await create_invoice(
                        session,
                        principal=principal,
                        payload=SupplierInvoiceCreateRequest(
                            branch_id=branch.id,
                            supplier_id=supplier.id,
                            lines=[
                                SupplierInvoiceLineInput(
                                    material_id=material.id,
                                    quantity=2,
                                    unit_price_tiyin=100000,
                                )
                            ],
                        ),
                    )
                    await session.commit()
                    return row
                except Exception as exc:  # pragma: no cover - only on a numbering race
                    await session.rollback()
                    return exc

        results = await asyncio.gather(record(), record())
        assert [result for result in results if isinstance(result, Exception)] == []

        async with maker() as verify:
            numbers = sorted(
                (await verify.scalars(select(SupplierInvoice.invoice_no))).all(),
            )
        assert numbers == ["K-0001", "K-0002"]
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
