"""Inventory models — stock balances, the append-only transaction log, suppliers.

Spec: docs/ref/entities/inventory.md.
"""

import uuid

from sqlalchemy import (
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import StockTransactionType, SupplierStatus


class StockItem(UUIDPrimaryKey, Timestamped, Base):
    """A branch's on-hand balance for one material, in the material's unit."""

    __tablename__ = "stock_item"
    __table_args__ = (UniqueConstraint("branch_id", "material_id", name="uq_stock_item"),)

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), index=True)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material.id"), index=True)
    on_hand: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, default=0)


class StockTransaction(UUIDPrimaryKey, Timestamped, Base):
    """One append-only audit row for one change to a stock item."""

    __tablename__ = "stock_transaction"

    stock_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stock_item.id"), index=True)
    type: Mapped[StockTransactionType] = mapped_column(
        Enum(StockTransactionType, native_enum=False, length=16)
    )
    quantity: Mapped[int] = mapped_column(Integer)  # signed, non-zero
    balance_after: Mapped[int] = mapped_column(Integer)
    order_id: Mapped[uuid.UUID | None] = mapped_column(index=True)  # consume/restore
    supplier_id: Mapped[uuid.UUID | None] = mapped_column()  # stock_in
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column()  # stock_in/adjust
    note: Mapped[str | None] = mapped_column(String(500))


class Supplier(UUIDPrimaryKey, Timestamped, Base):
    """Where a branch's stock came from — a workshop-scoped, lightweight label."""

    __tablename__ = "supplier"

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[SupplierStatus] = mapped_column(
        Enum(SupplierStatus, native_enum=False, length=16), default=SupplierStatus.ACTIVE
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column()
