"""Inventory balance, transaction, supplier, and supplier-invoice models."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, UniqueConstraint
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
        CheckConstraint(
            "type = 'stock_in' OR (unit_price_tiyin IS NULL AND total_price_tiyin IS NULL)",
            name="ck_stock_transactions_price_stock_in_only",
        ),
        CheckConstraint(
            "(unit_price_tiyin IS NULL OR unit_price_tiyin >= 0) AND "
            "(total_price_tiyin IS NULL OR total_price_tiyin >= 0)",
            name="ck_stock_transactions_price_nonnegative",
        ),
        CheckConstraint(
            "invoice_id IS NULL OR type = 'stock_in'",
            name="ck_stock_transactions_invoice_stock_in_only",
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
    # The arrival document this line belongs to. Every stock-in the platform
    # records now hangs off one; the column stays nullable because the other
    # movement types never have one.
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_invoices.id"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_users.id"))
    note: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class SupplierInvoice(UUIDPrimaryKey, Timestamped, Base):
    """One supplier arrival document — the grain the accountant negotiates in.

    A supplier quotes a total for the whole faktura, discount included; summing
    raw stock-in line prices can never reproduce that number. The invoice groups
    the lines and carries the document-level skidka/ustama, so the payable side
    of the supplier balance folds over `total_tiyin` and agrees with the
    supplier's own arithmetic.

    Discount/surcharge mirror `Order` (same non-negative and cap constraints,
    same stored-total check) but deliberately carry no reason/approver: on an
    order staff *grant* a concession and it needs an audit trail, here they only
    transcribe what the supplier already wrote on the document.
    """

    __tablename__ = "supplier_invoices"
    __table_args__ = (
        UniqueConstraint("workshop_id", "invoice_no", name="uq_supplier_invoices_workshop_no"),
        CheckConstraint("subtotal_tiyin >= 0", name="ck_supplier_invoices_subtotal_nonnegative"),
        CheckConstraint("discount_tiyin >= 0", name="ck_supplier_invoices_discount_nonnegative"),
        CheckConstraint("surcharge_tiyin >= 0", name="ck_supplier_invoices_surcharge_nonnegative"),
        CheckConstraint(
            "discount_tiyin <= subtotal_tiyin",
            name="ck_supplier_invoices_discount_not_above_subtotal",
        ),
        CheckConstraint(
            "total_tiyin = subtotal_tiyin - discount_tiyin + surcharge_tiyin",
            name="ck_supplier_invoices_total_formula",
        ),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    # Stock is per-branch, so one invoice is always one branch.
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    # Nullable because `StockTransaction.supplier_id` is: historical arrivals may
    # carry none, and such an invoice simply takes no part in the debt fold.
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    invoice_no: Mapped[str] = mapped_column(nullable=False)
    invoice_date: Mapped[date] = mapped_column(nullable=False)
    subtotal_tiyin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    discount_tiyin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    surcharge_tiyin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tiyin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    note: Mapped[str | None]
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_users.id"), nullable=False
    )


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
