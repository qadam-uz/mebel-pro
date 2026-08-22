"""global decor formats, English catalog vocabulary, customer boards out of the catalog

Four moves in one revision, because all three tables are rebuilt anyway and one
disruption beats two (impl_specs/SPEC_CATALOG_DECOR_FORMATS.md):

1. **The catalog vocabulary goes English.** `dekorlar` -> `decors`, the enum type
   `dekor_type` -> `decor_type`, and every Uzbek column name to its English
   equivalent. Enum *values*, i18n keys and every word on screen are unchanged.
2. **`tur` moves from the decor to the format.** A decor is a pattern identity;
   what it physically is belongs to the product. That dissolves the duplicate
   `board + kromka` twin decors the catalog carried (14 pairs in the demo data),
   which is what step 2 below merges.
3. **`decor_formats` becomes the platform-owned product list**, and
   `branch_materials` shrinks to what a branch actually owns: the decision to
   carry a format, its price, its threshold, its status.
4. **Customer-supplied boards leave `branch_materials`** for their own
   `customer_boards` table, keeping their ids, with their own FK on cutting
   panels and order items.

**Not fully reversible.** `downgrade()` restores the *shape* — the old names,
the old columns, the old enum type — but two data moves cannot be undone:
merging the decor twins destroys which of the two rows a branch material came
from, and a customer board's original `branch_materials` row is gone. Downgrade
is here so a botched deploy can roll the schema back onto a restored dump, not
so a populated database can round-trip. Same asymmetry, and same reason, as
b3c9f7d21a48.

Autogenerate emits none of this: not the table rename, not the enum type rename,
not the CHECK constraints, not the backfill. It is written by hand, and the
merge/backfill steps are factored into module-level functions so a test can
drive them against SQLite without a Postgres server.

Revision ID: c4e91a7b52d0
Revises: b3c9f7d21a48
Create Date: 2026-08-22 00:00:00.000000
"""

import uuid
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "c4e91a7b52d0"
down_revision: str | None = "b3c9f7d21a48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The seeded rows every customer board used to point at, written by
# d4b18e6c07a9 at these exact ids. Copied rather than imported: a frozen
# revision must not import code that can move under it.
CUSTOMER_MANUFACTURER_ID = "00000000-0000-0000-0000-00000000c001"
CUSTOMER_DECOR_ID = "00000000-0000-0000-0000-00000000c002"

# `finished_sides` is a product fact only for the board types. Nothing in the
# old schema recorded one-sided sheets, so every backfilled board format is the
# two-sided norm; a one-sided product is entered as its own format from now on.
FINISHED_SIDES_TYPES = ("ldsp", "dsp", "mdf")
BACKFILL_FINISHED_SIDES = 2

# The shape rule, as one predicate. It could not be a CHECK before: `tur` lived
# on `dekorlar` and was unreachable from `branch_materials`.
DECOR_FORMAT_SHAPE_CHECK = (
    "(type = 'kromka' AND tape_width_mm IS NOT NULL "
    "AND length_mm IS NULL AND width_mm IS NULL AND finished_sides IS NULL) "
    "OR (type <> 'kromka' AND tape_width_mm IS NULL "
    "AND length_mm IS NOT NULL AND width_mm IS NOT NULL "
    "AND length_mm >= width_mm "
    "AND ((type IN ('ldsp', 'dsp', 'mdf') AND finished_sides IN (1, 2)) "
    "OR (type NOT IN ('ldsp', 'dsp', 'mdf') AND finished_sides IS NULL)))"
)


# --------------------------------------------------------------------------- #
# Importable steps — the data moves, portable enough for a SQLite-backed test
# --------------------------------------------------------------------------- #


def _as_uuid(value: Any) -> uuid.UUID:
    """Ids come back as `uuid.UUID` from asyncpg and as hex text from SQLite.

    Normalised on read so every bound parameter below is a real `UUID` and the
    same helper runs against both dialects — which is what lets the migration
    test drive these functions without a Postgres server.
    """

    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _uuid_params(**values: Any) -> Any:
    """`sa.text()` binds with an explicit UUID type on every id parameter."""

    return [sa.bindparam(name, type_=sa.Uuid()) for name in values]


def _staging_table() -> sa.Table:
    """Where a branch material's ORIGINAL decor and substrate are parked.

    A real table rather than raw DDL so the id columns get the dialect's own
    UUID representation — a CHAR(36) staging column will not join against a
    Postgres `uuid` column, which is exactly how this failed first time.
    """

    return sa.Table(
        "_format_backfill",
        sa.MetaData(),
        sa.Column("branch_material_id", sa.Uuid(), nullable=False),
        sa.Column("decor_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
    )


def stage_format_backfill(bind: Connection) -> None:
    """Freeze each branch material's ORIGINAL decor and substrate.

    Has to run before `merge_decor_twins`, which rewrites `branch_materials.
    decor_id` and then deletes the rows the merged-away twins lived on. After
    that the question "what substrate was this branch material?" is unanswerable
    — the LDSP twin and the kromka twin have collapsed into one decor.
    """

    _staging_table().create(bind)
    bind.execute(
        sa.text(
            "INSERT INTO _format_backfill (branch_material_id, decor_id, type) "
            "SELECT bm.id, bm.decor_id, CAST(d.type AS VARCHAR) "
            "FROM branch_materials bm "
            "JOIN decors d ON d.id = bm.decor_id "
            "WHERE bm.customer_supplied = FALSE"
        )
    )


def merge_decor_twins(bind: Connection) -> dict[str, str]:
    """Collapse decors that differ only by the substrate that just left them.

    Identity is `(manufacturer, code)` when there is a code and
    `(manufacturer, name)` when there is not — `tur` used to be part of it,
    which is exactly why Egger H1145 existed twice: once as the LDSP board, once
    as the matching kromka. Those are one decor now.

    The keeper is the row that has a photo (one decor, one image, and the board
    row is the one that carries it in practice), then the oldest, then the
    lowest id so the choice is deterministic on a tie. Returns the
    `{merged_away_id: kept_id}` map, which the caller logs — it is the only
    record of what happened, since the deleted rows are gone.
    """

    rows = bind.execute(
        sa.text(
            "SELECT id, manufacturer_id, code, name, image_file_id, created_at "
            "FROM decors ORDER BY created_at, id"
        )
    ).all()
    groups: dict[tuple[str, str], list[Any]] = {}
    for row in rows:
        identity = (row.code if row.code is not None else row.name) or ""
        groups.setdefault((str(row.manufacturer_id), identity.strip().lower()), []).append(row)

    merge_map: dict[str, str] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        keeper = sorted(
            members,
            key=lambda row: (row.image_file_id is None, row.created_at, str(row.id)),
        )[0]
        for row in members:
            if str(row.id) == str(keeper.id):
                continue
            merge_map[str(_as_uuid(row.id))] = str(_as_uuid(keeper.id))

    for merged_id, kept_id in merge_map.items():
        params = {"kept": uuid.UUID(kept_id), "merged": uuid.UUID(merged_id)}
        binds = _uuid_params(kept=1, merged=1)
        bind.execute(
            sa.text(
                "UPDATE branch_materials SET decor_id = :kept WHERE decor_id = :merged"
            ).bindparams(*binds),
            params,
        )
        bind.execute(
            sa.text(
                "UPDATE _format_backfill SET decor_id = :kept WHERE decor_id = :merged"
            ).bindparams(*binds),
            params,
        )
        # The catalog photo is authorized by `files.entity_id`. Repointing keeps
        # a merged-away decor's image readable instead of dangling at an id that
        # no longer exists; only one of the two ever renders (the keeper's
        # `image_file_id`), and the other becomes an unused but valid row.
        bind.execute(
            sa.text(
                "UPDATE files SET entity_id = :kept "
                "WHERE entity_type = 'material' AND entity_id = :merged"
            ).bindparams(*_uuid_params(kept=1, merged=1)),
            params,
        )
        bind.execute(
            sa.text("DELETE FROM decors WHERE id = :merged").bindparams(
                sa.bindparam("merged", type_=sa.Uuid())
            ),
            {"merged": uuid.UUID(merged_id)},
        )
    return merge_map


def backfill_decor_formats(bind: Connection) -> int:
    """One `decor_formats` row per distinct product a branch was carrying.

    The natural key is `(decor, substrate, thickness, size | tape width,
    finished sides)`, so two branches carrying the same 2800x2070x18 Egger sheet
    collapse onto one platform format and thereafter share one id — which is the
    whole point of the move. Returns the number of formats created.

    UUIDs are minted in Python rather than by `gen_random_uuid()` so the same
    function runs on SQLite in the migration test.
    """

    rows = bind.execute(
        sa.text(
            "SELECT f.decor_id, f.type, bm.thickness_mm, bm.length_mm, bm.width_mm, "
            "bm.tape_width_mm, bm.id AS branch_material_id "
            "FROM _format_backfill f "
            "JOIN branch_materials bm ON bm.id = f.branch_material_id "
            "ORDER BY f.decor_id, f.type, bm.thickness_mm, bm.id"
        )
    ).all()

    formats: dict[tuple[Any, ...], list[uuid.UUID]] = {}
    for row in rows:
        key = (
            _as_uuid(row.decor_id),
            str(row.type),
            str(row.thickness_mm),
            row.length_mm,
            row.width_mm,
            row.tape_width_mm,
        )
        formats.setdefault(key, []).append(_as_uuid(row.branch_material_id))

    insert = sa.text(
        "INSERT INTO decor_formats "
        "(id, decor_id, type, thickness_mm, length_mm, width_mm, tape_width_mm, "
        " finished_sides, status, created_at, updated_at) "
        "VALUES (:id, :decor_id, :type, :thickness_mm, :length_mm, :width_mm, "
        " :tape_width_mm, :finished_sides, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    ).bindparams(*_uuid_params(id=1, decor_id=1))
    attach = sa.text(
        "UPDATE branch_materials SET decor_format_id = :format_id WHERE id = :id"
    ).bindparams(*_uuid_params(format_id=1, id=1))

    for key, branch_material_ids in formats.items():
        decor_id, type_, thickness, length_mm, width_mm, tape_width_mm = key
        format_id = uuid.uuid4()
        bind.execute(
            insert,
            {
                "id": format_id,
                "decor_id": decor_id,
                "type": type_,
                "thickness_mm": thickness,
                "length_mm": length_mm,
                "width_mm": width_mm,
                "tape_width_mm": tape_width_mm,
                "finished_sides": (
                    BACKFILL_FINISHED_SIDES if type_ in FINISHED_SIDES_TYPES else None
                ),
            },
        )
        for branch_material_id in branch_material_ids:
            bind.execute(attach, {"format_id": format_id, "id": branch_material_id})
    return len(formats)


def move_customer_boards(bind: Connection) -> int:
    """Lift every `customer_supplied` branch material into `customer_boards`.

    **The id is kept.** `own_panel_counts`, `material_snapshots`,
    `pricing_overrides.material_prices` and the optimizer's panel spec are all
    keyed by id string, and cutting panels and order items FK it — re-minting
    ids here would orphan every one of them. Keeping the id makes the move
    invisible to all of them: the two namespaces are disjoint UUIDs, so the
    panel/item FKs can simply be re-pointed at the other column.

    Returns the number of boards moved.
    """

    rows = bind.execute(
        sa.text(
            "SELECT bm.id, bm.branch_id, b.workshop_id, bm.name, bm.thickness_mm, "
            "bm.length_mm, bm.width_mm, bm.has_grain, bm.price_tiyin, "
            "bm.stock_material_id, bm.source_draft_id, bm.created_at, "
            "d.has_grain AS decor_has_grain, CAST(d.type AS VARCHAR) AS decor_type "
            "FROM branch_materials bm "
            "JOIN branches b ON b.id = bm.branch_id "
            "JOIN decors d ON d.id = bm.decor_id "
            "WHERE bm.customer_supplied = TRUE"
        )
    ).all()

    insert = sa.text(
        "INSERT INTO customer_boards "
        "(id, workshop_id, branch_id, name, type, thickness_mm, length_mm, width_mm, "
        " has_grain, price_tiyin, stock_material_id, source_draft_id, created_at) "
        "VALUES (:id, :workshop_id, :branch_id, :name, :type, :thickness_mm, "
        " :length_mm, :width_mm, :has_grain, :price_tiyin, :stock_material_id, "
        " :source_draft_id, :created_at)"
    ).bindparams(
        *_uuid_params(id=1, workshop_id=1, branch_id=1, stock_material_id=1, source_draft_id=1)
    )
    rekey_panels = sa.text(
        "UPDATE cutting_panels SET customer_board_id = :id, branch_material_id = NULL "
        "WHERE branch_material_id = :id"
    ).bindparams(sa.bindparam("id", type_=sa.Uuid()))
    rekey_items = sa.text(
        "UPDATE order_items SET customer_board_id = :id, branch_material_id = NULL "
        "WHERE branch_material_id = :id"
    ).bindparams(sa.bindparam("id", type_=sa.Uuid()))

    for row in rows:
        board_id = _as_uuid(row.id)
        bind.execute(
            insert,
            {
                "id": board_id,
                "workshop_id": _as_uuid(row.workshop_id),
                "branch_id": _as_uuid(row.branch_id),
                "name": row.name,
                "type": row.decor_type,
                "thickness_mm": row.thickness_mm,
                "length_mm": row.length_mm,
                "width_mm": row.width_mm,
                # `has_grain` was nullable on the board row and inherited from
                # the shared Mijoz decor when unset.
                "has_grain": (row.decor_has_grain if row.has_grain is None else row.has_grain),
                "price_tiyin": row.price_tiyin,
                "stock_material_id": (
                    _as_uuid(row.stock_material_id) if row.stock_material_id else None
                ),
                "source_draft_id": (_as_uuid(row.source_draft_id) if row.source_draft_id else None),
                "created_at": row.created_at,
            },
        )
        bind.execute(rekey_panels, {"id": board_id})
        bind.execute(rekey_items, {"id": board_id})
    bind.execute(sa.text("DELETE FROM branch_materials WHERE customer_supplied = TRUE"))
    return len(rows)


def drop_seeded_customer_identity(bind: Connection) -> bool:
    """Delete the `Mijoz` decor and manufacturer once nothing points at them.

    Guarded rather than unconditional: an operator may have attached a real
    format to that decor by hand, and a migration must not delete catalog rows
    somebody is using. Returns whether they were removed.
    """

    decor_id = uuid.UUID(CUSTOMER_DECOR_ID)
    manufacturer_id = uuid.UUID(CUSTOMER_MANUFACTURER_ID)
    still_used = bind.execute(
        sa.text(
            "SELECT 1 FROM branch_materials bm "
            "JOIN decor_formats df ON df.id = bm.decor_format_id "
            "WHERE df.decor_id = :decor_id LIMIT 1"
        ).bindparams(sa.bindparam("decor_id", type_=sa.Uuid())),
        {"decor_id": decor_id},
    ).first()
    if still_used is not None:
        return False
    bind.execute(
        sa.text("DELETE FROM decor_formats WHERE decor_id = :id").bindparams(
            sa.bindparam("id", type_=sa.Uuid())
        ),
        {"id": decor_id},
    )
    bind.execute(
        sa.text("DELETE FROM decors WHERE id = :id").bindparams(
            sa.bindparam("id", type_=sa.Uuid())
        ),
        {"id": decor_id},
    )
    other_decors = bind.execute(
        sa.text("SELECT 1 FROM decors WHERE manufacturer_id = :id LIMIT 1").bindparams(
            sa.bindparam("id", type_=sa.Uuid())
        ),
        {"id": manufacturer_id},
    ).first()
    if other_decors is None:
        bind.execute(
            sa.text("DELETE FROM manufacturers WHERE id = :id").bindparams(
                sa.bindparam("id", type_=sa.Uuid())
            ),
            {"id": manufacturer_id},
        )
    return True


def run_data_moves(bind: Connection) -> dict[str, Any]:
    """The whole data half of the migration, in the one order that works.

    Staging must precede the merge (it reads a fact the merge destroys); the
    customer-board move must precede `decor_format_id` being made NOT NULL
    (customer rows have no format and never will). The spec lists the move after
    the NOT NULL; doing it before is the same end state and the only order that
    can actually execute.
    """

    stage_format_backfill(bind)
    merge_map = merge_decor_twins(bind)
    formats = backfill_decor_formats(bind)
    boards = move_customer_boards(bind)
    return {"merge_map": merge_map, "formats": formats, "boards": boards}


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Renames ─────────────────────────────────────────────────────────
    op.execute("ALTER TYPE dekor_type RENAME TO decor_type")
    op.execute("DROP INDEX IF EXISTS uq_dekorlar_manufacturer_tur_kod_ci")
    op.execute("DROP INDEX IF EXISTS uq_dekorlar_manufacturer_tur_nomi_ci")
    op.execute("DROP INDEX IF EXISTS ix_dekorlar_search_key")
    op.execute("DROP INDEX IF EXISTS uq_branch_materials_branch_dekor_format")
    op.execute("DROP INDEX IF EXISTS ix_branch_materials_source_draft")
    op.execute("ALTER TABLE dekorlar RENAME TO decors")
    for old, new in (
        ("kod", "code"),
        ("nomi", "name"),
        ("tolali", "has_grain"),
        ("holat", "status"),
        ("tur", "type"),
    ):
        op.alter_column("decors", old, new_column_name=new)
    # `branch_materials`' Uzbek columns are renamed even though most are dropped
    # in step 5: the backfill SQL below then reads one vocabulary instead of
    # straddling both.
    for old, new in (
        ("dekor_id", "decor_id"),
        ("qalinlik_mm", "thickness_mm"),
        ("uzunlik_mm", "length_mm"),
        ("eni_mm", "width_mm"),
        ("kromka_eni_mm", "tape_width_mm"),
        ("nomi", "name"),
        ("tolali", "has_grain"),
    ):
        op.alter_column("branch_materials", old, new_column_name=new)
    op.execute(
        "ALTER TABLE branch_materials "
        "RENAME CONSTRAINT ck_branch_materials_qalinlik_positive "
        "TO ck_branch_materials_thickness_positive"
    )
    op.execute(
        "ALTER TABLE branch_materials "
        "RENAME CONSTRAINT ck_branch_materials_kromka_eni_positive "
        "TO ck_branch_materials_tape_width_positive"
    )

    # ── 2. New tables ──────────────────────────────────────────────────────
    # Both enum types already exist — `decor_type` is `dekor_type` renamed a few
    # statements ago. `create_type=False` is what stops SQLAlchemy emitting a
    # CREATE TYPE for a type it can see no values for.
    decor_type = postgresql.ENUM(name="decor_type", create_type=False)
    material_status = postgresql.ENUM(name="material_status", create_type=False)
    op.create_table(
        "decor_formats",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("decor_id", sa.Uuid(), sa.ForeignKey("decors.id"), nullable=False),
        sa.Column("type", decor_type, nullable=False),
        sa.Column("thickness_mm", sa.Numeric(), nullable=False),
        sa.Column("length_mm", sa.Integer(), nullable=True),
        sa.Column("width_mm", sa.Integer(), nullable=True),
        sa.Column("tape_width_mm", sa.Integer(), nullable=True),
        sa.Column("finished_sides", sa.SmallInteger(), nullable=True),
        sa.Column("status", material_status, nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("thickness_mm > 0", name="ck_decor_formats_thickness_positive"),
        sa.CheckConstraint(
            "tape_width_mm IS NULL OR tape_width_mm > 0",
            name="ck_decor_formats_tape_width_positive",
        ),
        sa.CheckConstraint(DECOR_FORMAT_SHAPE_CHECK, name="ck_decor_formats_shape"),
    )
    op.create_table(
        "customer_boards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workshop_id", sa.Uuid(), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("type", decor_type, nullable=False),
        sa.Column("thickness_mm", sa.Numeric(), nullable=False),
        sa.Column("length_mm", sa.Integer(), nullable=False),
        sa.Column("width_mm", sa.Integer(), nullable=False),
        sa.Column("has_grain", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("price_tiyin", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "stock_material_id",
            sa.Uuid(),
            sa.ForeignKey("branch_materials.id"),
            nullable=True,
        ),
        sa.Column(
            "source_draft_id",
            sa.Uuid(),
            sa.ForeignKey("cutting_drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("thickness_mm > 0", name="ck_customer_boards_thickness_positive"),
        sa.CheckConstraint(
            "length_mm > 0 AND width_mm > 0 AND length_mm >= width_mm",
            name="ck_customer_boards_panel_size",
        ),
        sa.CheckConstraint("type <> 'kromka'", name="ck_customer_boards_panel_type"),
        sa.CheckConstraint("price_tiyin >= 0", name="ck_customer_boards_price_nonnegative"),
    )

    # ── 3. New columns the data moves write into ───────────────────────────
    op.add_column("branch_materials", sa.Column("decor_format_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_branch_materials_decor_format_id",
        "branch_materials",
        "decor_formats",
        ["decor_format_id"],
        ["id"],
    )
    op.add_column("cutting_panels", sa.Column("customer_board_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_cutting_panels_customer_board_id",
        "cutting_panels",
        "customer_boards",
        ["customer_board_id"],
        ["id"],
    )
    op.add_column("order_items", sa.Column("customer_board_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_order_items_customer_board_id",
        "order_items",
        "customer_boards",
        ["customer_board_id"],
        ["id"],
    )
    op.alter_column("cutting_panels", "branch_material_id", nullable=True)
    op.alter_column("order_items", "branch_material_id", nullable=True)

    # ── 4. Data ────────────────────────────────────────────────────────────
    summary = run_data_moves(bind)
    # The merge map is the only record of what was collapsed — the rows are gone.
    print(
        f"[{revision}] merged {len(summary['merge_map'])} twin decors "
        f"{summary['merge_map']}; created {summary['formats']} decor formats; "
        f"moved {summary['boards']} customer boards"
    )
    drop_seeded_customer_identity(bind)
    _staging_table().drop(bind)

    # ── 5. Drops, constraints, indexes ─────────────────────────────────────
    op.alter_column("branch_materials", "decor_format_id", nullable=False)
    op.drop_constraint("ck_branch_materials_thickness_positive", "branch_materials")
    op.drop_constraint("ck_branch_materials_tape_width_positive", "branch_materials")
    op.drop_constraint("ck_branch_materials_panel_orientation", "branch_materials")
    for column in (
        "decor_id",
        "thickness_mm",
        "length_mm",
        "width_mm",
        "tape_width_mm",
        "customer_supplied",
        "name",
        "has_grain",
        "source_draft_id",
        "stock_material_id",
    ):
        op.drop_column("branch_materials", column)
    op.drop_column("decors", "type")

    op.create_index(
        "uq_branch_materials_branch_format",
        "branch_materials",
        ["branch_id", "decor_format_id"],
        unique=True,
    )
    op.create_index(
        "uq_decors_manufacturer_code_ci",
        "decors",
        ["manufacturer_id", sa.text("lower(code)")],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )
    op.create_index(
        "uq_decors_manufacturer_name_ci",
        "decors",
        ["manufacturer_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("code IS NULL"),
    )
    op.create_index("ix_decors_search_key", "decors", ["search_key"])
    op.create_index(
        "uq_decor_formats_natural_key",
        "decor_formats",
        [
            "decor_id",
            "type",
            "thickness_mm",
            sa.text("coalesce(length_mm, 0)"),
            sa.text("coalesce(width_mm, 0)"),
            sa.text("coalesce(tape_width_mm, 0)"),
            sa.text("coalesce(finished_sides, 0)"),
        ],
        unique=True,
    )
    op.create_unique_constraint(
        "uq_cutting_panels_result_board_index",
        "cutting_panels",
        ["cutting_result_id", "customer_board_id", "panel_index"],
    )
    op.create_check_constraint(
        "ck_cutting_panels_material_exactly_one",
        "cutting_panels",
        "(branch_material_id IS NOT NULL) <> (customer_board_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_order_items_material_exactly_one",
        "order_items",
        "(branch_material_id IS NOT NULL) <> (customer_board_id IS NOT NULL)",
    )


def downgrade() -> None:
    """Shape-only. See the module docstring: the twin merge and the customer-board
    move are not reversible by data, so this restores the old columns empty."""

    op.drop_constraint("ck_order_items_material_exactly_one", "order_items")
    op.drop_constraint("ck_cutting_panels_material_exactly_one", "cutting_panels")
    op.drop_constraint("uq_cutting_panels_result_board_index", "cutting_panels")
    op.drop_index("uq_decor_formats_natural_key", "decor_formats")
    op.drop_index("ix_decors_search_key", "decors")
    op.drop_index("uq_decors_manufacturer_name_ci", "decors")
    op.drop_index("uq_decors_manufacturer_code_ci", "decors")
    op.drop_index("uq_branch_materials_branch_format", "branch_materials")

    decor_type = postgresql.ENUM(name="decor_type", create_type=False)
    op.add_column("decors", sa.Column("type", decor_type, nullable=True))
    op.execute("UPDATE decors SET type = 'boshqa' WHERE type IS NULL")
    op.alter_column("decors", "type", nullable=False)

    op.add_column("branch_materials", sa.Column("decor_id", sa.Uuid(), nullable=True))
    op.add_column("branch_materials", sa.Column("thickness_mm", sa.Numeric(), nullable=True))
    op.add_column("branch_materials", sa.Column("length_mm", sa.Integer(), nullable=True))
    op.add_column("branch_materials", sa.Column("width_mm", sa.Integer(), nullable=True))
    op.add_column("branch_materials", sa.Column("tape_width_mm", sa.Integer(), nullable=True))
    op.add_column(
        "branch_materials",
        sa.Column(
            "customer_supplied", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column("branch_materials", sa.Column("name", sa.String(), nullable=True))
    op.add_column("branch_materials", sa.Column("has_grain", sa.Boolean(), nullable=True))
    op.add_column("branch_materials", sa.Column("source_draft_id", sa.Uuid(), nullable=True))
    op.add_column("branch_materials", sa.Column("stock_material_id", sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE branch_materials SET decor_id = df.decor_id, thickness_mm = df.thickness_mm, "
        "length_mm = df.length_mm, width_mm = df.width_mm, tape_width_mm = df.tape_width_mm "
        "FROM decor_formats df WHERE df.id = branch_materials.decor_format_id"
    )
    op.alter_column("branch_materials", "decor_id", nullable=False)
    op.alter_column("branch_materials", "thickness_mm", nullable=False)
    op.create_foreign_key(
        "fk_branch_materials_decor_id", "branch_materials", "decors", ["decor_id"], ["id"]
    )

    op.drop_constraint("fk_order_items_customer_board_id", "order_items")
    op.drop_column("order_items", "customer_board_id")
    op.drop_constraint("fk_cutting_panels_customer_board_id", "cutting_panels")
    op.drop_column("cutting_panels", "customer_board_id")
    op.execute("DELETE FROM order_items WHERE branch_material_id IS NULL")
    op.execute(
        "DELETE FROM cutting_placements WHERE cutting_panel_id IN "
        "(SELECT id FROM cutting_panels WHERE branch_material_id IS NULL)"
    )
    op.execute("DELETE FROM cutting_panels WHERE branch_material_id IS NULL")
    op.alter_column("cutting_panels", "branch_material_id", nullable=False)
    op.alter_column("order_items", "branch_material_id", nullable=False)

    op.drop_constraint("fk_branch_materials_decor_format_id", "branch_materials")
    op.drop_column("branch_materials", "decor_format_id")
    op.drop_table("customer_boards")
    op.drop_table("decor_formats")

    for new, old in (
        ("decor_id", "dekor_id"),
        ("thickness_mm", "qalinlik_mm"),
        ("length_mm", "uzunlik_mm"),
        ("width_mm", "eni_mm"),
        ("tape_width_mm", "kromka_eni_mm"),
        ("name", "nomi"),
        ("has_grain", "tolali"),
    ):
        op.alter_column("branch_materials", new, new_column_name=old)
    for new, old in (
        ("code", "kod"),
        ("name", "nomi"),
        ("has_grain", "tolali"),
        ("status", "holat"),
        ("type", "tur"),
    ):
        op.alter_column("decors", new, new_column_name=old)
    op.rename_table("decors", "dekorlar")
    op.execute("ALTER TYPE decor_type RENAME TO dekor_type")
    op.create_index(
        "uq_dekorlar_manufacturer_tur_kod_ci",
        "dekorlar",
        ["manufacturer_id", "tur", sa.text("lower(kod)")],
        unique=True,
        postgresql_where=sa.text("kod IS NOT NULL"),
    )
    op.create_index(
        "uq_dekorlar_manufacturer_tur_nomi_ci",
        "dekorlar",
        ["manufacturer_id", "tur", sa.text("lower(nomi)")],
        unique=True,
        postgresql_where=sa.text("kod IS NULL"),
    )
    op.create_index("ix_dekorlar_search_key", "dekorlar", ["search_key"])
    op.create_index("ix_branch_materials_source_draft", "branch_materials", ["source_draft_id"])
