"""Platform dekor catalog and branch material/pricing models.

The platform owns *identity* (`dekorlar`: who makes it, what it is, what it is
called, what it looks like). A branch owns *format* (`branch_materials`: the
thickness and sheet/tape size its own supplier actually sells, and its price).
Platform operators cannot know a workshop's formats, which is why the two live
apart — one dekor fans out to as many branch materials as a branch stocks.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import DekorType, MaterialStatus, enum_type


class Manufacturer(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "manufacturers"
    __table_args__ = (Index("uq_manufacturers_name_ci", func.lower(text("name")), unique=True),)

    name: Mapped[str] = mapped_column(nullable=False)
    country: Mapped[str | None]
    note: Mapped[str | None]
    status: Mapped[MaterialStatus] = mapped_column(
        enum_type(MaterialStatus, "material_status"),
        default=MaterialStatus.ACTIVE,
        nullable=False,
    )


class Dekor(UUIDPrimaryKey, Timestamped, Base):
    """A platform-owned catalog identity: one decor of one manufacturer.

    Carries no thickness, no size and no price — those are per-branch facts and
    live on `BranchMaterial`. One photo (`image_file_id`) serves every format.
    """

    __tablename__ = "dekorlar"
    __table_args__ = (
        # Uniqueness is by decor code when there is one, by name when there is
        # not. Two partial unique indexes, not UniqueConstraints: the predicate
        # and the lower() are expressions, which a UniqueConstraint cannot carry
        # (same reason as `uq_manufacturers_name_ci` above). Both are
        # `postgresql_where` and therefore *not* enforced on SQLite — the test
        # DB proves the shape of these rules, never their uniqueness.
        Index(
            "uq_dekorlar_manufacturer_tur_kod_ci",
            "manufacturer_id",
            "tur",
            func.lower(text("kod")),
            unique=True,
            postgresql_where=text("kod IS NOT NULL"),
        ),
        Index(
            "uq_dekorlar_manufacturer_tur_nomi_ci",
            "manufacturer_id",
            "tur",
            func.lower(text("nomi")),
            unique=True,
            postgresql_where=text("kod IS NULL"),
        ),
        Index("ix_dekorlar_search_key", "search_key"),
    )

    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manufacturers.id"), nullable=False
    )
    tur: Mapped[DekorType] = mapped_column(enum_type(DekorType, "dekor_type"), nullable=False)
    kod: Mapped[str | None]
    nomi: Mapped[str] = mapped_column(nullable=False)
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    tolali: Mapped[bool] = mapped_column(nullable=False)
    holat: Mapped[MaterialStatus] = mapped_column(
        enum_type(MaterialStatus, "material_status"),
        default=MaterialStatus.ACTIVE,
        nullable=False,
    )
    # Script- and apostrophe-insensitive search key, recomputed on every write
    # of this row AND whenever its manufacturer is renamed (the manufacturer
    # name is folded into it). See app/core/search_fold.py.
    search_key: Mapped[str] = mapped_column(nullable=False, server_default=text("''"), default="")


class BranchMaterial(UUIDPrimaryKey, Timestamped, Base):
    """A dekor in one concrete format, carried by one branch — "the material".

    Everything downstream (stock, cutting panels, order items) points here, not
    at the dekor: a 16 mm and an 18 mm sheet of the same decor are different
    things to cut, to stock and to price.
    """

    __tablename__ = "branch_materials"
    __table_args__ = (
        # NULLs are distinct in a Postgres unique index, so a plain
        # UniqueConstraint over the nullable format columns would let
        # (dekor, 18mm, NULL, NULL) in twice. COALESCE collapses them.
        Index(
            "uq_branch_materials_branch_dekor_format",
            "branch_id",
            "dekor_id",
            "qalinlik_mm",
            func.coalesce(text("uzunlik_mm"), text("0")),
            func.coalesce(text("eni_mm"), text("0")),
            func.coalesce(text("kromka_eni_mm"), text("0")),
            unique=True,
        ),
        CheckConstraint("price_tiyin >= 0", name="ck_branch_materials_price_nonnegative"),
        CheckConstraint("min_stock >= 0", name="ck_branch_materials_min_stock_nonnegative"),
        CheckConstraint("qalinlik_mm > 0", name="ck_branch_materials_qalinlik_positive"),
        CheckConstraint(
            "kromka_eni_mm IS NULL OR kromka_eni_mm > 0",
            name="ck_branch_materials_kromka_eni_positive",
        ),
        # The full panel/tape shape rule needs `tur`, which lives on dekorlar
        # and is unreachable from a table CHECK. Only the column-local half is
        # enforced here; the service layer owns the rest.
        CheckConstraint(
            "uzunlik_mm IS NULL OR eni_mm IS NULL OR uzunlik_mm >= eni_mm",
            name="ck_branch_materials_panel_orientation",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    dekor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dekorlar.id"), nullable=False)
    qalinlik_mm: Mapped[Decimal] = mapped_column(nullable=False)
    # Panel-shaped formats carry uzunlik/eni; tape-shaped ones carry
    # kromka_eni. Which pair applies is decided by the dekor's `tur`.
    uzunlik_mm: Mapped[int | None]
    eni_mm: Mapped[int | None]
    kromka_eni_mm: Mapped[int | None]
    # 0 means "not priced yet", not "free": a branch may attach its whole
    # format list before it knows prices. Client-facing listings exclude these.
    price_tiyin: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"), default=0
    )
    min_stock: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[MaterialStatus] = mapped_column(
        enum_type(MaterialStatus, "material_status"),
        default=MaterialStatus.ACTIVE,
        nullable=False,
    )


class BranchPricing(Base):
    __tablename__ = "branch_pricing"
    __table_args__ = (
        CheckConstraint(
            "cutting_rate_tiyin IS NULL OR cutting_rate_tiyin >= 0",
            name="ck_branch_pricing_cutting_nonnegative",
        ),
        CheckConstraint(
            "edge_banding_rate_tiyin IS NULL OR edge_banding_rate_tiyin >= 0",
            name="ck_branch_pricing_edge_nonnegative",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), primary_key=True)
    cutting_rate_tiyin: Mapped[int | None] = mapped_column(BigInteger)
    edge_banding_rate_tiyin: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime | None]
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_users.id"))
