"""Workshop tenant and branch models."""

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import BranchStatus, Currency, WorkshopStatus, enum_type


class Workshop(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "workshops"
    __table_args__ = (
        # AB-119: signup-rate counters on the platform dashboard scan by date.
        Index("ix_workshops_created_at", "created_at"),
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
        UniqueConstraint("branch_no", name="uq_branches_branch_no"),
        CheckConstraint("branch_no >= 1", name="ck_branches_branch_no_positive"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_branches_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_branches_longitude"),
        CheckConstraint("kerf_mm >= 1 AND kerf_mm <= 20", name="ck_branches_kerf_mm"),
        CheckConstraint(
            "edge_trim_mm >= 0 AND edge_trim_mm <= 50", name="ck_branches_edge_trim_mm"
        ),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    # Platform-wide branch number, assigned once at creation and never changed —
    # it is the middle segment of every order number this branch ever prints
    # (`#26-14-0003`), so rewriting it would orphan printed cutting maps.
    branch_no: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    address: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str] = mapped_column(nullable=False)
    # Extra published numbers (landline, director's mobile, WhatsApp …), in
    # display order. `phone` stays the single primary number every compact
    # surface and every order record uses; this list is additive only.
    additional_phones: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default="[]",
    )
    latitude: Mapped[Decimal | None]
    longitude: Mapped[Decimal | None]
    # Physical properties of this branch's saw — how the cutting optimiser
    # resolves kerf/trim for every draft scoped to this branch (cutting.md).
    # Platform defaults: kerf 4 mm, edge trim 5 mm.
    kerf_mm: Mapped[int] = mapped_column(nullable=False, default=4, server_default="4")
    edge_trim_mm: Mapped[int] = mapped_column(nullable=False, default=5, server_default="5")
    # Whether this branch takes a client's own sheets (catalog-inventory.md).
    # Off until the owner turns it on: accepting client material changes what
    # the shop stores and what has to arrive before the saw can start, so it is
    # a decision a branch makes rather than a default it inherits.
    own_material_allowed: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=false()
    )
    status: Mapped[BranchStatus] = mapped_column(
        enum_type(BranchStatus, "branch_status"),
        default=BranchStatus.ACTIVE,
        nullable=False,
    )
    closed_reason: Mapped[str | None]
