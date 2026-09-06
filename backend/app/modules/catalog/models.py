"""Platform decor catalog, decor formats and branch material/pricing models.

The platform owns the whole product fact. `decors` is *pattern identity* — who
makes it, what it is called, what it looks like. `decor_formats` is the concrete
product — substrate, thickness, sheet size or tape width, finished sides. A
branch owns only the commercial decision: `branch_materials` is "we carry this
format, at this price, with this reorder threshold, and it is on/off".

This reverses the earlier "a branch owns the format" split (see
`docs/ref/features/catalog-inventory.md`). A format is the manufacturer's fact,
not the branch's, and the owner wants one id per physical product across every
workshop — the basis for cross-workshop analytics, central price-list import and
board-to-tape pairing. The cost, a branch waiting on the platform for a new
size, is accepted and made visible in the attach sheet.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, SmallInteger, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import DecorType, MaterialStatus, enum_type

# The shape rule of a decor format, as one SQL predicate. Expressible as a table
# CHECK now that `type` lives on the format itself — it could not be before,
# when `type` was a column of the decor and unreachable from `branch_materials`.
DECOR_FORMAT_SHAPE_CHECK = (
    "(type = 'kromka' AND tape_width_mm IS NOT NULL "
    "AND length_mm IS NULL AND width_mm IS NULL AND finished_sides IS NULL) "
    "OR (type <> 'kromka' AND tape_width_mm IS NULL "
    "AND length_mm IS NOT NULL AND width_mm IS NOT NULL "
    "AND length_mm >= width_mm "
    "AND ((type IN ('ldsp', 'dsp', 'mdf') AND finished_sides IN (1, 2)) "
    "OR (type NOT IN ('ldsp', 'dsp', 'mdf') AND finished_sides IS NULL)))"
)


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


class Decor(UUIDPrimaryKey, Timestamped, Base):
    """A platform-owned pattern identity: one decor of one manufacturer.

    Carries no substrate, no thickness, no size and no price. Egger H1145 is ONE
    decor that exists as an LDSP 18 mm board *and* as a 0.8x22 kromka — both are
    `decor_formats` of this row, sharing its photo and its name.
    """

    __tablename__ = "decors"
    __table_args__ = (
        # Uniqueness is by decor code when there is one, by name when there is
        # not. `type` is deliberately NOT part of identity any more: that is
        # exactly what forced the board/kromka twins the reshape merged away.
        # Two partial unique indexes, not UniqueConstraints: the predicate and
        # the lower() are expressions, which a UniqueConstraint cannot carry
        # (same reason as `uq_manufacturers_name_ci` above). The predicate is
        # spelled for BOTH dialects: with only `postgresql_where`, SQLite still
        # creates the index but drops the WHERE, so the test DB enforced
        # name-uniqueness even for two decors with different codes — a rule
        # production does not have. `tur` used to be in the tuple and hid that.
        Index(
            "uq_decors_manufacturer_code_ci",
            "manufacturer_id",
            func.lower(text("code")),
            unique=True,
            postgresql_where=text("code IS NOT NULL"),
            sqlite_where=text("code IS NOT NULL"),
        ),
        Index(
            "uq_decors_manufacturer_name_ci",
            "manufacturer_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("code IS NULL"),
            sqlite_where=text("code IS NULL"),
        ),
        Index("ix_decors_search_key", "search_key"),
        # The typo tier of the search (`word_similarity`) is only affordable
        # behind a trigram index. `gin_trgm_ops` and the GIN access method are
        # Postgres-only; every other dialect ignores the prefixed kwargs and
        # builds a plain b-tree, which is harmless. Declared here rather than
        # only in the migration so autogenerate does not offer to drop it.
        Index(
            "ix_decors_search_key_trgm",
            "search_key",
            postgresql_using="gin",
            postgresql_ops={"search_key": "gin_trgm_ops"},
        ),
    )

    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manufacturers.id"), nullable=False
    )
    code: Mapped[str | None]
    name: Mapped[str] = mapped_column(nullable=False)
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    has_grain: Mapped[bool] = mapped_column(nullable=False)
    status: Mapped[MaterialStatus] = mapped_column(
        enum_type(MaterialStatus, "material_status"),
        default=MaterialStatus.ACTIVE,
        nullable=False,
    )
    # Script- and apostrophe-insensitive search key: `" " + folded words + " "`
    # of the name, code, manufacturer name and the decor's active format types.
    # Recomputed on every write of this row, whenever its manufacturer is
    # renamed, and whenever one of its formats is created or changes status (the
    # type words move). See app/core/search_fold.py and app/core/search_query.py.
    search_key: Mapped[str] = mapped_column(nullable=False, server_default=text("''"), default="")


class DecorFormat(UUIDPrimaryKey, Timestamped, Base):
    """One concrete product of a decor — the thing a supplier actually sells.

    Platform-owned and **immutable**: there is no PATCH for dimensions. A wrong
    format is deactivated and a correct one created, because branch rows, stock,
    cutting panels and order history all resolve through it and a silent
    re-dimension would rewrite what those rows mean. `status` is the only
    mutable column.
    """

    __tablename__ = "decor_formats"
    __table_args__ = (
        # NULLs are distinct in a Postgres unique index, so a plain
        # UniqueConstraint over the nullable columns would let
        # (decor, ldsp, 18, NULL, NULL, ...) in twice. COALESCE collapses them.
        Index(
            "uq_decor_formats_natural_key",
            "decor_id",
            "type",
            "thickness_mm",
            func.coalesce(text("length_mm"), text("0")),
            func.coalesce(text("width_mm"), text("0")),
            func.coalesce(text("tape_width_mm"), text("0")),
            func.coalesce(text("finished_sides"), text("0")),
            unique=True,
        ),
        CheckConstraint("thickness_mm > 0", name="ck_decor_formats_thickness_positive"),
        CheckConstraint(
            "tape_width_mm IS NULL OR tape_width_mm > 0",
            name="ck_decor_formats_tape_width_positive",
        ),
        CheckConstraint(DECOR_FORMAT_SHAPE_CHECK, name="ck_decor_formats_shape"),
    )

    decor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("decors.id"), nullable=False)
    type: Mapped[DecorType] = mapped_column(enum_type(DecorType, "decor_type"), nullable=False)
    thickness_mm: Mapped[Decimal] = mapped_column(nullable=False)
    # Panel-shaped formats carry length/width; tape-shaped ones carry
    # tape_width. Which pair applies is decided by `type` — and unlike before,
    # the DB can now see it, so the whole rule is a CHECK.
    length_mm: Mapped[int | None]
    width_mm: Mapped[int | None]
    tape_width_mm: Mapped[int | None]
    # How many faces are finished — laminate, film or paint. Required for the
    # board types (ldsp/dsp/mdf), NULL for everything else. One-sided is the
    # norm for facade MDF and for the cheap white LDSP used on hidden parts: a
    # different product at a different price, not a variant of the two-sided
    # sheet.
    finished_sides: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[MaterialStatus] = mapped_column(
        enum_type(MaterialStatus, "material_status"),
        default=MaterialStatus.ACTIVE,
        nullable=False,
    )


class BranchMaterial(UUIDPrimaryKey, Timestamped, Base):
    """A decor format one branch has decided to carry — "the material".

    Everything downstream (stock, cutting panels, order items) points here, not
    at the format: the price and the shelf are the branch's, while what the
    sheet physically *is* belongs to the platform. Four facts are the whole row
    — carrying it, its price, its threshold, its own on/off switch.
    """

    __tablename__ = "branch_materials"
    __table_args__ = (
        # Full, not partial: a branch either carries a format or it does not.
        # The old index was partial only because customer-supplied boards lived
        # in this table and two walk-ins with the same sheet collided; boards
        # have their own table now (see cutting.models.CustomerBoard).
        Index(
            "uq_branch_materials_branch_format",
            "branch_id",
            "decor_format_id",
            unique=True,
        ),
        CheckConstraint("price_tiyin >= 0", name="ck_branch_materials_price_nonnegative"),
        CheckConstraint("min_stock >= 0", name="ck_branch_materials_min_stock_nonnegative"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    decor_format_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decor_formats.id"), nullable=False
    )
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
