"""Decor catalog, decor formats and branch material/pricing models.

`decors` is *pattern identity* — who makes it, what it is called, what it looks
like. `decor_formats` is the concrete product — substrate, thickness, sheet size
or tape width, finished sides. A branch owns only the commercial decision:
`branch_materials` is "we carry this format, at this price, and it is on/off".

**Who owns a row** (2026-09-07). The platform catalog is a *library*, not an
authority: a pre-filled list so a workshop does not type Egger's 300 decors by
hand. `workshop_id` on `manufacturers`, `decors` and `decor_formats` says who
wrote the row — `NULL` is the library, a value is one workshop's own. An own row
is visible only to that workshop (its branches, its staff, the clients pinned to
its branches): `visible_to(ws) := workshop_id IS NULL OR workshop_id = ws`.
Nothing is moderated and nothing is promoted; the column exists so the door to a
future merge stays open at zero cost, not because anything walks through it.

This softens — not reverses — the 2026-08-22 move of formats off the branch. A
format is still the manufacturer's fact and still keyed by id everywhere
downstream; what changed is that a workshop no longer *waits* for the platform to
enter a size it already buys.
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


# The owning workshop of a catalog row, or NULL for a library row. Spelled once
# because all three tables carry the identical column, and because the visibility
# predicate reads off it: `workshop_id IS NULL OR workshop_id = :ws`.
_WORKSHOP_OWNED_WHERE = "workshop_id IS NOT NULL"
_LIBRARY_WHERE = "workshop_id IS NULL"


def _workshop_owner_column() -> Mapped[uuid.UUID | None]:
    return mapped_column(ForeignKey("workshops.id"), index=True)


class Manufacturer(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "manufacturers"
    __table_args__ = (
        # One index per ownership arm. NULLs are distinct in a unique index, so a
        # single index over (workshop_id, lower(name)) would let the library hold
        # «Kastamonu» twice; and a single index over lower(name) alone would stop
        # a workshop entering a maker the library already lists under a name it
        # cannot see the row of. Two partial indexes say the actual rule: names
        # are unique inside the library, and unique inside each workshop.
        Index(
            "uq_manufacturers_name_ci",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text(_LIBRARY_WHERE),
            sqlite_where=text(_LIBRARY_WHERE),
        ),
        Index(
            "uq_manufacturers_ws_name_ci",
            "workshop_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text(_WORKSHOP_OWNED_WHERE),
            sqlite_where=text(_WORKSHOP_OWNED_WHERE),
        ),
    )

    name: Mapped[str] = mapped_column(nullable=False)
    country: Mapped[str | None]
    note: Mapped[str | None]
    workshop_id: Mapped[uuid.UUID | None] = _workshop_owner_column()
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
        # Each of the two rules gets an ownership arm, for the reason spelled on
        # `manufacturers` above: the library is unique to itself, and each
        # workshop is unique to itself. A workshop entering «Egger · H1145» of
        # its own while the library already has one is a duplicate the owner
        # accepted — the alternative is refusing a row the operator cannot see.
        Index(
            "uq_decors_manufacturer_code_ci",
            "manufacturer_id",
            func.lower(text("code")),
            unique=True,
            postgresql_where=text(f"code IS NOT NULL AND {_LIBRARY_WHERE}"),
            sqlite_where=text(f"code IS NOT NULL AND {_LIBRARY_WHERE}"),
        ),
        Index(
            "uq_decors_manufacturer_name_ci",
            "manufacturer_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text(f"code IS NULL AND {_LIBRARY_WHERE}"),
            sqlite_where=text(f"code IS NULL AND {_LIBRARY_WHERE}"),
        ),
        Index(
            "uq_decors_ws_manufacturer_code_ci",
            "workshop_id",
            "manufacturer_id",
            func.lower(text("code")),
            unique=True,
            postgresql_where=text(f"code IS NOT NULL AND {_WORKSHOP_OWNED_WHERE}"),
            sqlite_where=text(f"code IS NOT NULL AND {_WORKSHOP_OWNED_WHERE}"),
        ),
        Index(
            "uq_decors_ws_manufacturer_name_ci",
            "workshop_id",
            "manufacturer_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text(f"code IS NULL AND {_WORKSHOP_OWNED_WHERE}"),
            sqlite_where=text(f"code IS NULL AND {_WORKSHOP_OWNED_WHERE}"),
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
    workshop_id: Mapped[uuid.UUID | None] = _workshop_owner_column()
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

    **Immutable**: there is no PATCH for dimensions. A wrong format is
    deactivated and a correct one created, because branch rows, stock, cutting
    panels and order history all resolve through it and a silent re-dimension
    would rewrite what those rows mean. `status` is the only mutable column.

    A workshop-owned format may hang off a **library** decor — the common case is
    "Egger H1145 exists, the 16 mm does not" — or off the workshop's own decor.
    """

    __tablename__ = "decor_formats"
    __table_args__ = (
        # NULLs are distinct in a Postgres unique index, so a plain
        # UniqueConstraint over the nullable columns would let
        # (decor, ldsp, 18, NULL, NULL, ...) in twice. COALESCE collapses them.
        # Split by ownership arm like the decor indexes: one shape per decor
        # inside the library, and one per decor inside each workshop. The service
        # is what stops a workshop duplicating a shape the library *actively*
        # offers (it attaches that row instead); the DB only stops a workshop
        # duplicating its own — an inactive library twin is a shape the workshop
        # legitimately still buys.
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
            postgresql_where=text(_LIBRARY_WHERE),
            sqlite_where=text(_LIBRARY_WHERE),
        ),
        Index(
            "uq_decor_formats_ws_natural_key",
            "workshop_id",
            "decor_id",
            "type",
            "thickness_mm",
            func.coalesce(text("length_mm"), text("0")),
            func.coalesce(text("width_mm"), text("0")),
            func.coalesce(text("tape_width_mm"), text("0")),
            func.coalesce(text("finished_sides"), text("0")),
            unique=True,
            postgresql_where=text(_WORKSHOP_OWNED_WHERE),
            sqlite_where=text(_WORKSHOP_OWNED_WHERE),
        ),
        CheckConstraint("thickness_mm > 0", name="ck_decor_formats_thickness_positive"),
        CheckConstraint(
            "tape_width_mm IS NULL OR tape_width_mm > 0",
            name="ck_decor_formats_tape_width_positive",
        ),
        CheckConstraint(DECOR_FORMAT_SHAPE_CHECK, name="ck_decor_formats_shape"),
    )

    decor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("decors.id"), nullable=False)
    workshop_id: Mapped[uuid.UUID | None] = _workshop_owner_column()
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
    at the format: the price and the shelf are the branch's, while what the sheet
    physically *is* belongs to whoever wrote the format. Three facts are the
    whole row — carrying it, its price, its own on/off switch. The low-stock
    threshold used to be a fourth; it was retired 2026-09-08 (a warning that is
    everywhere is nowhere), leaving `on_hand < 0` as the only stock alarm.
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
