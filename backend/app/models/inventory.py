"""Inventory balance, transaction, and supplier models."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import StockTransactionType, SupplierStatus, enum_type


class StockItem(UUIDPrimaryKey, Base):
    __tablename__ = "stock_items"
    __table_args__ = (
        UniqueConstraint("branch_id", "material_id", name="uq_stock_items_branch_material"),
        CheckConstraint("on_hand >= 0", name="ck_stock_items_on_hand_nonnegative"),
        CheckConstraint("min_stock >= 0", name="ck_stock_items_min_stock_nonnegative"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False)
    on_hand: Mapped[int] = mapped_column(default=0, nullable=False)
    min_stock: Mapped[int] = mapped_column(default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class StockTransaction(UUIDPrimaryKey, Base):
    __tablename__ = "stock_transactions"
    __table_args__ = (
        CheckConstraint("quantity <> 0", name="ck_stock_transactions_quantity_nonzero"),
        CheckConstraint("balance_after >= 0", name="ck_stock_transactions_balance_nonnegative"),
    )

    stock_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stock_items.id"), nullable=False)
    type: Mapped[StockTransactionType] = mapped_column(
        enum_type(StockTransactionType, "stock_transaction_type"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    balance_after: Mapped[int] = mapped_column(nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"))
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_users.id"))
    note: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class Supplier(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "suppliers"

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str | None]
    note: Mapped[str | None]
    status: Mapped[SupplierStatus] = mapped_column(
        enum_type(SupplierStatus, "supplier_status"),
        default=SupplierStatus.ACTIVE,
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_users.id"), nullable=False
    )
