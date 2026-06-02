"""Workshop tenant and branch models."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import BranchStatus, Currency, WorkshopStatus, enum_type


class Workshop(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "workshops"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id", "id"],
            ["workshop_users.id", "workshop_users.workshop_id"],
            name="fk_workshops_owner_user",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    name: Mapped[str] = mapped_column(nullable=False)
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    phone: Mapped[str] = mapped_column(nullable=False)
    address: Mapped[str | None]
    owner_user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    status: Mapped[WorkshopStatus] = mapped_column(
        enum_type(WorkshopStatus, "workshop_status"),
        default=WorkshopStatus.ACTIVE,
        nullable=False,
    )
    currency: Mapped[Currency] = mapped_column(
        enum_type(Currency, "currency"),
        default=Currency.UZS,
        nullable=False,
    )


class Branch(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_branches_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_branches_longitude"),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    address: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str] = mapped_column(nullable=False)
    latitude: Mapped[Decimal] = mapped_column(nullable=False)
    longitude: Mapped[Decimal] = mapped_column(nullable=False)
    working_hours: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    status: Mapped[BranchStatus] = mapped_column(
        enum_type(BranchStatus, "branch_status"),
        default=BranchStatus.ACTIVE,
        nullable=False,
    )
    closed_reason: Mapped[str | None]
