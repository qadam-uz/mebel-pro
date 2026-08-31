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
from app.models.enums import BranchStatus, Currency, ProductionMode, WorkshopStatus, enum_type
from app.modules.workshop.public_code import generate_public_code


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
    # The identifier behind this workshop's client link/QR (`/w/{code}`) —
    # 8 Crockford-base32 characters, unique platform-wide, permanent: a printed
    # QR must never rot, so there is no regenerate operation anywhere. The
    # column default draws one for every insert path (provisioning allocates a
    # checked-unique code first); see public_code.py.
    public_code: Mapped[str] = mapped_column(
        unique=True,
        nullable=False,
        default=generate_public_code,
    )
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
        CheckConstraint(
            "edge_overhang_mm >= 0 AND edge_overhang_mm <= 100",
            name="ck_branches_edge_overhang_mm",
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
    # Physical properties of this branch's shop floor — how the cutting optimiser
    # resolves kerf/trim/overhang for every draft scoped to this branch
    # (cutting.md). Platform defaults: kerf 4 mm, edge trim 5 mm, overhang 30 mm.
    kerf_mm: Mapped[int] = mapped_column(nullable=False, default=4, server_default="4")
    edge_trim_mm: Mapped[int] = mapped_column(nullable=False, default=5, server_default="5")
    # Glue-and-trim allowance the bander adds to **each** banded side, then cuts
    # flush by hand — it is what the client is billed and what stock is
    # decremented by, on top of the geometric edge length (orders.md#pricing).
    edge_overhang_mm: Mapped[int] = mapped_column(nullable=False, default=30, server_default="30")
    # Whether this branch takes a client's own sheets (catalog-inventory.md).
    # Off until the owner turns it on: accepting client material changes what
    # the shop stores and what has to arrive before the saw can start, so it is
    # a decision a branch makes rather than a default it inherits.
    own_material_allowed: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=false()
    )
    # Which production choreography this branch's orders run (orders.md). Every
    # branch is `simple` — the shops the field visits met run on paper and never
    # tap a station screen, so the collapsed two-tap flow is the adoption
    # default. Branches provisioned before the mode existed took the same
    # default (the migration has no backfill); `full` is an owner opt-in.
    production_mode: Mapped[ProductionMode] = mapped_column(
        enum_type(ProductionMode, "production_mode"),
        nullable=False,
        default=ProductionMode.SIMPLE,
        server_default=ProductionMode.SIMPLE.value,
    )
    status: Mapped[BranchStatus] = mapped_column(
        enum_type(BranchStatus, "branch_status"),
        default=BranchStatus.ACTIVE,
        nullable=False,
    )
    closed_reason: Mapped[str | None]
