"""Inventory balance, transaction, and supplier models."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import StockTransactionType, SupplierStatus, enum_type


class StockItem(UUIDPrimaryKey, Base):
    __tablename__ = "stock_items"
    __table_args__ = (
        UniqueConstraint("branch_id", "material_id", name="uq_stock_items_branch_material"),
        CheckConstraint("min_stock >= 0", name="ck_stock_items_min_stock_nonnegative"),
    )
    # `on_hand` is deliberately unbounded below: order-driven `consume` records
    # material that physically already moved, so the books may go negative when
    # the matching arrival was never entered (QAD-150). Manual paths still guard
    # in the service layer.

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False)
    on_hand: Mapped[int] = mapped_column(default=0, nullable=False)
    min_stock: Mapped[int] = mapped_column(default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


class StockTransaction(UUIDPrimaryKey, Base):
    __tablename__ = "stock_transactions"
    __table_args__ = (
        CheckConstraint("quantity <> 0", name="ck_stock_transactions_quantity_nonzero"),
        # No `balance_after >= 0` CHECK — see StockItem.on_hand (QAD-150).
        CheckConstraint(
            "type = 'stock_in' OR (unit_price_tiyin IS NULL AND total_price_tiyin IS NULL)",
            name="ck_stock_transactions_price_stock_in_only",
        ),
        CheckConstraint(
            "(unit_price_tiyin IS NULL OR unit_price_tiyin >= 0) AND "
            "(total_price_tiyin IS NULL OR total_price_tiyin >= 0)",
            name="ck_stock_transactions_price_nonnegative",
        ),
    )

    stock_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stock_items.id"), nullable=False)
    type: Mapped[StockTransactionType] = mapped_column(
        enum_type(StockTransactionType, "stock_transaction_type"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    balance_after: Mapped[int] = mapped_column(nullable=False)
    unit_price_tiyin: Mapped[int | None] = mapped_column(BigInteger)
    total_price_tiyin: Mapped[int | None] = mapped_column(BigInteger)
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
