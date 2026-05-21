"""Workshop (tenant) and its branches. Spec: docs/ref/entities/workshop.md."""

import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import BranchStatus, Currency, WorkshopStatus


class Workshop(UUIDPrimaryKey, Timestamped, Base):
    """One furniture-cutting business — the tenant. Exactly one owner."""

    __tablename__ = "workshop"

    name: Mapped[str] = mapped_column(String(160))
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column()
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(400))
    # 1:1 with the owner workshop_user; nullable only during the atomic provision.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column()
    status: Mapped[WorkshopStatus] = mapped_column(
        Enum(WorkshopStatus, native_enum=False, length=16), default=WorkshopStatus.ACTIVE
    )
    currency: Mapped[Currency] = mapped_column(
        Enum(Currency, native_enum=False, length=8), default=Currency.UZS
    )


class Branch(UUIDPrimaryKey, Timestamped, Base):
    """A physical location of a workshop. Owns stock, pricing, material selection."""

    __tablename__ = "branch"
    __table_args__ = (Index("ix_branch_workshop", "workshop_id"),)

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop.id"))
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(400))
    phone: Mapped[str] = mapped_column(String(20))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    # per-weekday {open, close} or {closed: true}
    working_hours: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[BranchStatus] = mapped_column(
        Enum(BranchStatus, native_enum=False, length=20), default=BranchStatus.ACTIVE
    )
    closed_reason: Mapped[str | None] = mapped_column(String(300))
