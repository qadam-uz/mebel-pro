"""Finance models — the workshop money ledger: income and expenses.

Spec: docs/ref/entities/finance.md.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import (
    ExpenseCategory,
    IncomeType,
    LedgerStatus,
    PaymentMethod,
)


class Income(UUIDPrimaryKey, Timestamped, Base):
    """Money the workshop received; ``order_payment`` carries the order it settles."""

    __tablename__ = "income"
    __table_args__ = ()

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop.id"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"), index=True)
    type: Mapped[IncomeType] = mapped_column(Enum(IncomeType, native_enum=False, length=16))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("order.id"), index=True)
    amount_tiyin: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, native_enum=False, length=16))
    received_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(500))
    receipt_file_id: Mapped[uuid.UUID | None] = mapped_column()
    status: Mapped[LedgerStatus] = mapped_column(
        Enum(LedgerStatus, native_enum=False, length=16), default=LedgerStatus.RECORDED
    )
    voided_reason: Mapped[str | None] = mapped_column(String(500))
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column()
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column()
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Expense(UUIDPrimaryKey, Timestamped, Base):
    """Money the workshop spent — overheads, consumables, and staff salary."""

    __tablename__ = "expense"

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop.id"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"), index=True)
    category: Mapped[ExpenseCategory] = mapped_column(
        Enum(ExpenseCategory, native_enum=False, length=24)
    )
    amount_tiyin: Mapped[int] = mapped_column(BigInteger)
    incurred_on: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    vendor: Mapped[str | None] = mapped_column(String(200))
    receipt_file_id: Mapped[uuid.UUID | None] = mapped_column()
    status: Mapped[LedgerStatus] = mapped_column(
        Enum(LedgerStatus, native_enum=False, length=16), default=LedgerStatus.RECORDED
    )
    voided_reason: Mapped[str | None] = mapped_column(String(500))
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column()
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column()
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
