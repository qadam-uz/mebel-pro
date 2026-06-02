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
    __table_args__ = (CheckConstraint("amount_tiyin > 0", name="ck_expenses_amount_positive"),)

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
