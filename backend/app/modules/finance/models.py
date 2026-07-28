"""Income and expense foundation models."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import ExpenseCategory, IncomeType, LedgerStatus, MoneyMethod, enum_type


class Income(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "incomes"
    __table_args__ = (
        CheckConstraint("amount_tiyin > 0", name="ck_incomes_amount_positive"),
        CheckConstraint(
            "(type = 'order_payment' AND order_id IS NOT NULL) OR "
            "(type <> 'order_payment' AND order_id IS NULL)",
            name="ck_incomes_order_required_for_order_payment",
        ),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    type: Mapped[IncomeType] = mapped_column(enum_type(IncomeType, "income_type"), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"))
    amount_tiyin: Mapped[int] = mapped_column(BigInteger, nullable=False)
    method: Mapped[MoneyMethod] = mapped_column(
        enum_type(MoneyMethod, "money_method"), nullable=False
    )
    received_on: Mapped[date] = mapped_column(nullable=False)
    note: Mapped[str | None]
    receipt_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    status: Mapped[LedgerStatus] = mapped_column(
        enum_type(LedgerStatus, "ledger_status"),
        default=LedgerStatus.RECORDED,
        nullable=False,
    )
    voided_reason: Mapped[str | None]
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_users.id"), nullable=False
    )
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_users.id"))
    voided_at: Mapped[datetime | None]


class Expense(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount_tiyin > 0", name="ck_expenses_amount_positive"),
        # A supplier-linked expense is a term in that supplier's per-branch
        # balance (QAD-182), so it has to name the branch it settles. Expenses
        # with no counterparty — rent, tax, salary — stay workshop-wide.
        CheckConstraint(
            "supplier_id IS NULL OR branch_id IS NOT NULL",
            name="ck_expenses_supplier_requires_branch",
        ),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    category: Mapped[ExpenseCategory] = mapped_column(
        enum_type(ExpenseCategory, "expense_category"),
        nullable=False,
    )
    amount_tiyin: Mapped[int] = mapped_column(BigInteger, nullable=False)
    incurred_on: Mapped[date] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    vendor: Mapped[str | None]
    # `supplier_id` stays populated even when the expense pays an invoice — it is
    # copied from the invoice — so the payments side of the supplier balance is
    # identical for a faktura payment and a bare advance.
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_invoices.id"))
    receipt_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    status: Mapped[LedgerStatus] = mapped_column(
        enum_type(LedgerStatus, "ledger_status"),
        default=LedgerStatus.RECORDED,
        nullable=False,
    )
    voided_reason: Mapped[str | None]
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_users.id"), nullable=False
    )
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_users.id"))
    voided_at: Mapped[datetime | None]


class CounterpartyAdjustment(UUIDPrimaryKey, Timestamped, Base):
    """A signed debt correction against exactly one supplier or client.

    The pressure valve of the debt fold: opening balances from the pre-system
    era and real-world events that are neither a delivery nor a payment
    (discounts, returns, mutual offsets). It never moves stock or cash — it
    exists only in the derived balance.
    """

    __tablename__ = "counterparty_adjustments"
    __table_args__ = (
        CheckConstraint("amount_tiyin <> 0", name="ck_counterparty_adjustments_amount_nonzero"),
        CheckConstraint(
            "(supplier_id IS NOT NULL AND client_id IS NULL) OR "
            "(supplier_id IS NULL AND client_id IS NOT NULL)",
            name="ck_counterparty_adjustments_exactly_one_party",
        ),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    # Debts are held per branch (QAD-182): an adjustment corrects one branch's
    # balance with a counterparty, never the workshop's in the abstract.
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"))
    # Signed, sign convention everywhere: positive = they owe us more.
    amount_tiyin: Mapped[int] = mapped_column(BigInteger, nullable=False)
    adjusted_on: Mapped[date] = mapped_column(nullable=False)
    note: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[LedgerStatus] = mapped_column(
        enum_type(LedgerStatus, "ledger_status"),
        default=LedgerStatus.RECORDED,
        nullable=False,
    )
    voided_reason: Mapped[str | None]
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_users.id"), nullable=False
    )
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_users.id"))
    voided_at: Mapped[datetime | None]
