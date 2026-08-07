"""catalog dekorlar reshape

Splits the platform `materials` table into platform-owned identity
(`dekorlar`) and branch-owned format (`branch_materials`), and re-points the
three foreign keys that used to name a platform material —
`stock_items`, `cutting_panels`, `order_items` — at the branch material.

Beyond the FK columns, material ids are also embedded as *JSON keys and values*
in cutting drafts/results and orders. Those are rewritten here too: leaving them
keyed by a deleted table's ids would type-check clean and mis-join silently
(blank labels, stock consumption targeting nothing).
`order_items.material_snapshot` is the one JSON blob left completely alone — it
is frozen history, and `app/core/material_label.py` reads both the old and the
new snapshot vocabularies for exactly that reason.

Revision ID: c9f4a2b71e83
Revises: b06a71097c10
Create Date: 2026-08-07 09:00:00.000000
"""

import json
import logging
import uuid
from collections.abc import Callable, Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from app.core.search_fold import fold
from sqlalchemy.dialects import postgresql

# NOTE on the `app.core.search_fold` import above: this migration folds
# `search_key` with the same function the service layer uses, so a row written
# by the backfill and a row written by the API agree. That couples a historical
# revision to app code — if `fold` ever changes, re-running this migration
# produces different keys than it did the first time. Accepted deliberately;
# the alternative (a frozen copy of the fold table inlined here) guarantees the
# stored keys and the query-time fold drift apart instead.

# revision identifiers, used by Alembic.
revision: str = "c9f4a2b71e83"
down_revision: str | None = "b06a71097c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.runtime.migration")

_DEKOR_TYPE_VALUES = ("ldsp", "dsp", "mdf", "fanera", "yogoch", "kromka", "boshqa")

# `materials.kind = 'edge'` becomes tur='kromka'; otherwise the panel substrate
# maps across one-for-one.
#
# NOTE, deliberately: 'dsp' maps to 'dsp', NOT to the new 'ldsp' value — even
# though the display label for 'dsp' has always read "LDSP". The stored value is
# what history means, and re-coding it would be unrecoverable once `materials`
# is dropped. Nothing in this backfill ever produces 'ldsp'.
_TYPE_TO_TUR = {
    "dsp": "dsp",
    "mdf": "mdf",
    "plywood": "fanera",
    "natural_wood": "yogoch",
    "other": "boshqa",
}

# The branch a cutting result belongs to — the ONE definition, used by the panel
# backfill, the mint step, the JSON rewrite and the orphan sweep.
#
# A result reaches its branch by EITHER route and they are mutually exclusive in
# practice: a candidate result hangs off a draft (`draft_id`), while a result
# that has been confirmed onto an order hangs off the order (`order_id`) and its
# draft link is cleared. Resolving only through the draft therefore misses every
# result belonging to a real, produced order — which is most of them in any
# live database. That miss used to be silent *and* destructive: the panels then
# looked branch-less and the orphan sweep deleted them, taking the sheet maps
# and placements of every confirmed order with it.
_RESULT_BRANCH_SQL = """
    SELECT cr.id AS result_id,
           COALESCE(cd.preferred_branch_id, o.branch_id) AS branch_id
      FROM cutting_results cr
      LEFT JOIN cutting_drafts cd ON cd.id = cr.draft_id
      LEFT JOIN orders o ON o.id = cr.order_id
     WHERE COALESCE(cd.preferred_branch_id, o.branch_id) IS NOT NULL
"""

# CuttingResult JSON columns whose top-level keys are material id strings.
# They split by what happens when two old keys land on one branch material
# (which the duplicate-catalog merge above can cause): tallies add up, an
# identity snapshot does not — both keys described the same dekor, so the first
# one already says everything.
_RESULT_COUNTER_COLUMNS = (
    "panels_used_by_material",
    "edge_length_by_material",
    "edge_length_shop_by_material",
    "edge_length_own_by_material",
    "edge_consumed_shop_by_material",
    "edge_consumed_own_by_material",
    "edge_banded_sides_by_material",
)
_RESULT_SNAPSHOT_COLUMNS = ("material_snapshots",)
_RESULT_ID_KEYED_COLUMNS = _RESULT_COUNTER_COLUMNS + _RESULT_SNAPSHOT_COLUMNS

_EDGE_SIDES = ("edge_top", "edge_bottom", "edge_left", "edge_right")

# (branch_id, material_id) -> branch_materials.id
Remap = Callable[[Any, Any], str | None]


def upgrade() -> None:
    bind = op.get_bind()

    _create_dekorlar()
    material_to_dekor = _backfill_dekorlar(bind)
    _create_material_dekor_map(bind, material_to_dekor)
    _repoint_material_files(bind)

    _reshape_branch_materials(bind)
    _add_branch_material_columns()
    _backfill_branch_material_ids(bind)
    _mint_missing_branch_materials(bind)
    _backfill_branch_material_ids(bind)
    _drop_branchless_cutting_panels(bind)
    _assert_no_unresolved_references(bind)

    _merge_duplicate_branch_materials(bind)
    _merge_duplicate_stock_items(bind)
    _assert_cutting_panel_uniqueness(bind)
    # Runs while the merge losers are still on the table: a JSON blob may name
    # a loser's material, and only the loser row still carries that material_id.
    _rewrite_material_id_json(bind)
    _drop_merged_branch_materials(bind)

    _finalize_schema()
    op.execute("DROP TABLE _material_dekor")
    _drop_materials(bind)


def downgrade() -> None:
    """Structural rollback only — the material rows themselves are gone.

    `materials` comes back empty and the three `material_id` columns come back
    nullable, because there is nothing left to point them at. A real rollback of
    a deployed upgrade is a restore from backup, not this function.
    """
    bind = op.get_bind()

    op.drop_constraint("uq_stock_items_branch_material", "stock_items", type_="unique")
    op.drop_constraint("uq_cutting_panels_result_material_index", "cutting_panels", type_="unique")
    op.drop_index("uq_branch_materials_branch_dekor_format", table_name="branch_materials")
    for check in (
        "ck_branch_materials_qalinlik_positive",
        "ck_branch_materials_kromka_eni_positive",
        "ck_branch_materials_panel_orientation",
    ):
        op.drop_constraint(check, "branch_materials", type_="check")

    op.create_table(
        "materials",
        sa.Column("kind", sa.Enum("panel", "edge", name="material_kind"), nullable=False),
        sa.Column("manufacturer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("dsp", "mdf", "plywood", "natural_wood", "other", name="panel_material_type"),
            nullable=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("thickness_mm", sa.Numeric(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("decor_code", sa.String(), nullable=True),
        sa.Column("panel_length_mm", sa.Integer(), nullable=True),
        sa.Column("panel_width_mm", sa.Integer(), nullable=True),
        sa.Column("grain_direction", sa.Boolean(), nullable=True),
        sa.Column("edge_width_mm", sa.Integer(), nullable=True),
        sa.Column("image_file_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("active", "inactive", name="material_status", create_type=False),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["image_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["manufacturer_id"], ["manufacturers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    for table, fk_name in (
        ("stock_items", "fk_stock_items_branch_material_id"),
        ("cutting_panels", "fk_cutting_panels_branch_material_id"),
        ("order_items", "fk_order_items_branch_material_id"),
    ):
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.drop_column(table, "branch_material_id")
        op.add_column(table, sa.Column("material_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_material_id", table, "materials", ["material_id"], ["id"]
        )

    op.create_unique_constraint(
        "uq_stock_items_branch_material", "stock_items", ["branch_id", "material_id"]
    )
    op.create_unique_constraint(
        "uq_cutting_panels_result_material_index",
        "cutting_panels",
        ["cutting_result_id", "material_id", "panel_index"],
    )

    op.drop_constraint("fk_branch_materials_dekor_id", "branch_materials", type_="foreignkey")
    for column in ("dekor_id", "qalinlik_mm", "uzunlik_mm", "eni_mm", "kromka_eni_mm"):
        op.drop_column("branch_materials", column)
    op.alter_column("branch_materials", "price_tiyin", server_default=None)
    op.add_column("branch_materials", sa.Column("material_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_branch_materials_material_id", "branch_materials", "materials", ["material_id"], ["id"]
    )
    op.create_unique_constraint(
        "uq_branch_materials_branch_material", "branch_materials", ["branch_id", "material_id"]
    )

    op.drop_index("ix_dekorlar_search_key", table_name="dekorlar")
    op.drop_index("uq_dekorlar_manufacturer_tur_nomi_ci", table_name="dekorlar")
    op.drop_index("uq_dekorlar_manufacturer_tur_kod_ci", table_name="dekorlar")
    op.drop_table("dekorlar")
    sa.Enum(name="dekor_type").drop(bind, checkfirst=True)


# --------------------------------------------------------------------------- #
# 1. dekorlar
# --------------------------------------------------------------------------- #


def _create_dekorlar() -> None:
    bind = op.get_bind()
    dekor_type = postgresql.ENUM(*_DEKOR_TYPE_VALUES, name="dekor_type", create_type=False)
    dekor_type.create(bind, checkfirst=True)

    op.create_table(
        "dekorlar",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("manufacturer_id", sa.Uuid(), nullable=False),
        sa.Column("tur", dekor_type, nullable=False),
        sa.Column("kod", sa.String(), nullable=True),
        sa.Column("nomi", sa.String(), nullable=False),
        sa.Column("image_file_id", sa.Uuid(), nullable=True),
        sa.Column("tolali", sa.Boolean(), nullable=False),
        sa.Column(
            "holat",
            postgresql.ENUM("active", "inactive", name="material_status", create_type=False),
            nullable=False,
        ),
        sa.Column("search_key", sa.String(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["image_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["manufacturer_id"], ["manufacturers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Partial + expression indexes: uniqueness is by decor code where one
    # exists, by name where it does not.
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


def _backfill_dekorlar(bind: sa.Connection) -> dict[Any, uuid.UUID]:
    """Collapse `materials` into dekorlar; return material_id -> dekor_id."""
    rows = (
        bind.execute(
            sa.text(
                """
                SELECT m.id, m.kind, m.type, m.manufacturer_id, mf.name AS manufacturer_name,
                       m.decor_code, m.color, m.grain_direction, m.image_file_id, m.status
                  FROM materials m
                  JOIN manufacturers mf ON mf.id = m.manufacturer_id
                 ORDER BY m.created_at, m.id
                """
            )
        )
        .mappings()
        .all()
    )

    # Group case-insensitively on exactly the identity the new unique indexes
    # use, or the backfill mints rows those indexes immediately reject.
    groups: dict[tuple[Any, str, str], list[Any]] = {}
    for row in rows:
        tur = "kromka" if row["kind"] == "edge" else _TYPE_TO_TUR.get(row["type"] or "", "boshqa")
        identity = ((row["decor_code"] or row["color"]) or "").strip().casefold()
        groups.setdefault((row["manufacturer_id"], tur, identity), []).append(row)

    material_to_dekor: dict[Any, uuid.UUID] = {}
    inserts: list[dict[str, Any]] = []
    for (manufacturer_id, tur, _identity), group in groups.items():
        first = group[0]
        kod = (first["decor_code"] or "").strip() or None
        nomi = (first["color"] or "").strip()
        dekor_id = uuid.uuid4()
        inserts.append(
            {
                "id": dekor_id,
                "manufacturer_id": manufacturer_id,
                "tur": tur,
                "kod": kod,
                "nomi": nomi,
                # One photo serves every format, so the group's first available
                # image wins; the losing `files` rows keep pointing at the same
                # dekor and stay readable, they are simply not the cover.
                "image_file_id": next(
                    (row["image_file_id"] for row in group if row["image_file_id"] is not None),
                    None,
                ),
                "tolali": bool(first["grain_direction"]),
                # A dekor is active if any material that folded into it was.
                "holat": "active"
                if any(row["status"] == "active" for row in group)
                else "inactive",
                "search_key": fold(f"{nomi} {kod or ''} {first['manufacturer_name']}"),
            }
        )
        for row in group:
            material_to_dekor[row["id"]] = dekor_id

    if inserts:
        bind.execute(
            sa.text(
                """
                INSERT INTO dekorlar
                    (id, manufacturer_id, tur, kod, nomi, image_file_id, tolali, holat, search_key)
                VALUES
                    (:id, :manufacturer_id, CAST(:tur AS dekor_type), :kod, :nomi,
                     :image_file_id, :tolali, CAST(:holat AS material_status), :search_key)
                """
            ),
            inserts,
        )
    _LOG.info(
        "dekorlar reshape: %s materials collapsed into %s dekorlar",
        len(material_to_dekor),
        len(inserts),
    )
    return material_to_dekor


def _create_material_dekor_map(
    bind: sa.Connection, material_to_dekor: dict[Any, uuid.UUID]
) -> None:
    op.execute(
        "CREATE TEMPORARY TABLE _material_dekor "
        "(material_id uuid PRIMARY KEY, dekor_id uuid NOT NULL)"
    )
    if material_to_dekor:
        bind.execute(
            sa.text("INSERT INTO _material_dekor (material_id, dekor_id) VALUES (:m, :d)"),
            [{"m": material, "d": dekor} for material, dekor in material_to_dekor.items()],
        )


def _repoint_material_files(bind: sa.Connection) -> None:
    """Move catalog photos onto the dekor that replaced their material.

    `files.entity_id` holds a `materials.id` for every `entity_type='material'`
    row. That id is about to stop resolving, and the read-authorization check in
    support/files.py loads the entity by it — so without this, every existing
    catalog photo would 403 for clients and workshop users while still working
    for platform admins, who short-circuit before the lookup.

    The `entity_type` string deliberately stays the literal `'material'`:
    nothing is gained by renaming a stored tag, and a half-applied rename
    forbids every historical image with no error anywhere.
    """
    updated = bind.execute(
        sa.text(
            """
            UPDATE files f
               SET entity_id = md.dekor_id
              FROM _material_dekor md
             WHERE f.entity_type = 'material' AND f.entity_id = md.material_id
            """
        )
    ).rowcount
    _LOG.info("dekorlar reshape: re-pointed %s catalog file rows onto dekorlar", updated)


# --------------------------------------------------------------------------- #
# 2. branch_materials gains dekor + format
# --------------------------------------------------------------------------- #


def _reshape_branch_materials(bind: sa.Connection) -> None:
    op.add_column("branch_materials", sa.Column("dekor_id", sa.Uuid(), nullable=True))
    op.add_column("branch_materials", sa.Column("qalinlik_mm", sa.Numeric(), nullable=True))
    op.add_column("branch_materials", sa.Column("uzunlik_mm", sa.Integer(), nullable=True))
    op.add_column("branch_materials", sa.Column("eni_mm", sa.Integer(), nullable=True))
    op.add_column("branch_materials", sa.Column("kromka_eni_mm", sa.Integer(), nullable=True))
    bind.execute(
        sa.text(
            """
            UPDATE branch_materials bm
               SET dekor_id = md.dekor_id,
                   qalinlik_mm = m.thickness_mm,
                   uzunlik_mm = m.panel_length_mm,
                   eni_mm = m.panel_width_mm,
                   kromka_eni_mm = m.edge_width_mm
              FROM materials m
              JOIN _material_dekor md ON md.material_id = m.id
             WHERE bm.material_id = m.id
            """
        )
    )


# --------------------------------------------------------------------------- #
# 3. the three re-pointed foreign keys
# --------------------------------------------------------------------------- #


def _add_branch_material_columns() -> None:
    for table in ("stock_items", "cutting_panels", "order_items"):
        op.add_column(table, sa.Column("branch_material_id", sa.Uuid(), nullable=True))


def _backfill_branch_material_ids(bind: sa.Connection) -> None:
    """Resolve each row's branch, then find that branch's row for the material.

    Every one of these rows already sits inside a branch context: stock items
    carry `branch_id`, order items reach it through their order, cutting panels
    through their result's draft.
    """
    bind.execute(
        sa.text(
            """
            UPDATE stock_items si
               SET branch_material_id = bm.id
              FROM branch_materials bm
             WHERE si.branch_material_id IS NULL
               AND bm.branch_id = si.branch_id
               AND bm.material_id = si.material_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE order_items oi
               SET branch_material_id = bm.id
              FROM orders o, branch_materials bm
             WHERE oi.branch_material_id IS NULL
               AND o.id = oi.order_id
               AND bm.branch_id = o.branch_id
               AND bm.material_id = oi.material_id
            """
        )
    )
    bind.execute(
        sa.text(
            f"""
            UPDATE cutting_panels cp
               SET branch_material_id = bm.id
              FROM ({_RESULT_BRANCH_SQL}) rb,
                   branch_materials bm
             WHERE cp.branch_material_id IS NULL
               AND rb.result_id = cp.cutting_result_id
               AND bm.branch_id = rb.branch_id
               AND bm.material_id = cp.material_id
            """  # noqa: S608 - _RESULT_BRANCH_SQL is a module constant, not user input
        )
    )


def _mint_missing_branch_materials(bind: sa.Connection) -> None:
    """Create the branch rows history implies but the catalog never had.

    Today's picker lets an order or a cutting result reference a material the
    branch does not carry — it browses the whole platform catalog through an
    outer join. Under the new schema there is no such thing as stock, a panel or
    an order line without a branch material, so those references get one:
    inactive and unpriced, so it reads as history rather than as something on
    sale.

    Edge materials are why `_needed_bm` exists. They never produce a
    `cutting_panels` row, so they are reachable only through the JSON blobs.
    """
    _collect_json_material_refs(bind)
    minted = bind.execute(
        sa.text(
            f"""
            INSERT INTO branch_materials
                (id, branch_id, material_id, dekor_id, qalinlik_mm, uzunlik_mm, eni_mm,
                 kromka_eni_mm, price_tiyin, min_stock, status, created_at, updated_at)
            SELECT gen_random_uuid(), needed.branch_id, m.id, md.dekor_id, m.thickness_mm,
                   m.panel_length_mm, m.panel_width_mm, m.edge_width_mm, 0, 0,
                   CAST('inactive' AS material_status), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
              FROM (
                    SELECT si.branch_id, si.material_id
                      FROM stock_items si
                     WHERE si.branch_material_id IS NULL
                    UNION
                    SELECT o.branch_id, oi.material_id
                      FROM order_items oi
                      JOIN orders o ON o.id = oi.order_id
                     WHERE oi.branch_material_id IS NULL
                    UNION
                    SELECT rb.branch_id, cp.material_id
                      FROM cutting_panels cp
                      JOIN ({_RESULT_BRANCH_SQL}) rb ON rb.result_id = cp.cutting_result_id
                     WHERE cp.branch_material_id IS NULL
                    UNION
                    SELECT n.branch_id, n.material_id FROM _needed_bm n
                   ) needed
              JOIN materials m ON m.id = needed.material_id
              JOIN _material_dekor md ON md.material_id = m.id
             WHERE NOT EXISTS (
                   SELECT 1 FROM branch_materials bm
                    WHERE bm.branch_id = needed.branch_id AND bm.material_id = needed.material_id)
            """  # noqa: S608 - _RESULT_BRANCH_SQL is a module constant, not user input
        )
    ).rowcount
    op.execute("DROP TABLE _needed_bm")
    if minted:
        _LOG.warning(
            "dekorlar reshape: minted %s inactive branch_materials for history that "
            "referenced materials the branch never carried",
            minted,
        )


def _collect_json_material_refs(bind: sa.Connection) -> None:
    """Stage every (branch, material) pair that only a JSON blob mentions."""
    op.execute(
        "CREATE TEMPORARY TABLE _needed_bm (branch_id uuid NOT NULL, material_id uuid NOT NULL)"
    )
    pairs: set[tuple[Any, uuid.UUID]] = set()

    for row in bind.execute(
        sa.text(
            "SELECT preferred_branch_id, parts_snapshot FROM cutting_drafts "
            "WHERE preferred_branch_id IS NOT NULL"
        )
    ).mappings():
        _collect_from_parts(pairs, row["preferred_branch_id"], row["parts_snapshot"])

    keyed = ", ".join(f"cr.{name}" for name in _RESULT_ID_KEYED_COLUMNS)
    for row in bind.execute(
        sa.text(
            f"SELECT rb.branch_id, cr.parts_snapshot, {keyed} "  # noqa: S608
            f"FROM cutting_results cr JOIN ({_RESULT_BRANCH_SQL}) rb ON rb.result_id = cr.id"
        )
    ).mappings():
        branch_id = row["branch_id"]
        _collect_from_parts(pairs, branch_id, row["parts_snapshot"])
        for column in _RESULT_ID_KEYED_COLUMNS:
            _collect_from_keys(pairs, branch_id, row[column])

    for row in bind.execute(
        sa.text(
            "SELECT branch_id, edge_length_snapshot FROM orders WHERE edge_length_snapshot IS NOT NULL"
        )
    ).mappings():
        _collect_from_keys(pairs, row["branch_id"], row["edge_length_snapshot"])

    for row in bind.execute(
        sa.text(
            "SELECT o.branch_id, oi.edge_top, oi.edge_bottom, oi.edge_left, oi.edge_right "
            "FROM order_items oi JOIN orders o ON o.id = oi.order_id"
        )
    ).mappings():
        for side in _EDGE_SIDES:
            edge = row[side]
            if isinstance(edge, dict):
                _add_pair(pairs, row["branch_id"], edge.get("material_id"))

    if pairs:
        bind.execute(
            sa.text("INSERT INTO _needed_bm (branch_id, material_id) VALUES (:b, :m)"),
            [{"b": branch_id, "m": material_id} for branch_id, material_id in pairs],
        )


def _drop_branchless_cutting_panels(bind: sa.Connection) -> None:
    """A cutting result reachable from NEITHER a branch-ful draft nor an order.

    Runs only after `_RESULT_BRANCH_SQL` has had both routes: a result confirmed
    onto an order has no draft link left, and deleting those on the strength of
    a NULL `preferred_branch_id` alone would destroy the sheet maps of every
    produced order. What is left here is genuinely unreachable — a candidate
    result of a draft that never chose a branch.
    """
    orphans = bind.execute(
        sa.text("SELECT count(*) FROM cutting_panels WHERE branch_material_id IS NULL")
    ).scalar_one()
    if not orphans:
        return
    _LOG.warning(
        "dekorlar reshape: deleting %s cutting_panels rows whose result resolves to no "
        "branch by either route (draft.preferred_branch_id, order.branch_id) — there is "
        "no branch material for them to point at",
        orphans,
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM cutting_placements
             WHERE cutting_panel_id IN (
                   SELECT id FROM cutting_panels WHERE branch_material_id IS NULL)
            """
        )
    )
    bind.execute(sa.text("DELETE FROM cutting_panels WHERE branch_material_id IS NULL"))


def _assert_no_unresolved_references(bind: sa.Connection) -> None:
    for table in ("stock_items", "order_items", "cutting_panels"):
        unresolved = bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE branch_material_id IS NULL")  # noqa: S608
        ).scalar_one()
        if unresolved:
            raise RuntimeError(
                f"{table}: {unresolved} rows could not be mapped to a branch material. "
                "Resolve them by hand before re-running this migration."
            )


# --------------------------------------------------------------------------- #
# 4. de-duplicate what the old schema allowed and the new one forbids
# --------------------------------------------------------------------------- #


def _merge_duplicate_branch_materials(bind: sa.Connection) -> None:
    """`materials` had no uniqueness at all, so two rows could describe one thing.

    Once identity and format are separated, those duplicates land on one
    (branch, dekor, format) tuple, which the new unique index rejects. Keep the
    oldest and re-point everything at it.
    """
    op.execute(
        """
        CREATE TEMPORARY TABLE _bm_merge AS
        SELECT b.id AS loser_id, s.survivor_id
          FROM branch_materials b
          JOIN (
                SELECT branch_id, dekor_id, qalinlik_mm,
                       coalesce(uzunlik_mm, 0) AS u,
                       coalesce(eni_mm, 0) AS e,
                       coalesce(kromka_eni_mm, 0) AS k,
                       (array_agg(id ORDER BY created_at, id))[1] AS survivor_id
                  FROM branch_materials
                 GROUP BY 1, 2, 3, 4, 5, 6
                HAVING count(*) > 1
               ) s
            ON s.branch_id = b.branch_id
           AND s.dekor_id = b.dekor_id
           AND s.qalinlik_mm = b.qalinlik_mm
           AND s.u = coalesce(b.uzunlik_mm, 0)
           AND s.e = coalesce(b.eni_mm, 0)
           AND s.k = coalesce(b.kromka_eni_mm, 0)
         WHERE b.id <> s.survivor_id
        """
    )
    losers = bind.execute(sa.text("SELECT count(*) FROM _bm_merge")).scalar_one()
    if losers:
        _LOG.warning(
            "dekorlar reshape: merging %s duplicate branch_materials rows "
            "(same branch, dekor and format) into their oldest sibling",
            losers,
        )
        for table in ("stock_items", "cutting_panels", "order_items"):
            bind.execute(
                sa.text(
                    f"UPDATE {table} t SET branch_material_id = m.survivor_id "  # noqa: S608
                    "FROM _bm_merge m WHERE t.branch_material_id = m.loser_id"
                )
            )
    # The loser rows stay until `_drop_merged_branch_materials`: the JSON
    # rewrite still needs their `material_id` to resolve blobs that name them.


def _drop_merged_branch_materials(bind: sa.Connection) -> None:
    bind.execute(
        sa.text("DELETE FROM branch_materials WHERE id IN (SELECT loser_id FROM _bm_merge)")
    )
    op.execute("DROP TABLE _bm_merge")


def _merge_duplicate_stock_items(bind: sa.Connection) -> None:
    """Merged branch materials can leave two stock rows for one material."""
    op.execute(
        """
        CREATE TEMPORARY TABLE _si_merge AS
        SELECT si.id AS loser_id, s.survivor_id
          FROM stock_items si
          JOIN (
                SELECT branch_material_id,
                       (array_agg(id ORDER BY updated_at, id))[1] AS survivor_id
                  FROM stock_items
                 GROUP BY branch_material_id
                HAVING count(*) > 1
               ) s ON s.branch_material_id = si.branch_material_id
         WHERE si.id <> s.survivor_id
        """
    )
    losers = bind.execute(sa.text("SELECT count(*) FROM _si_merge")).scalar_one()
    if losers:
        _LOG.warning(
            "dekorlar reshape: folding %s duplicate stock_items rows into their surviving "
            "sibling (balances summed, min_stock takes the maximum)",
            losers,
        )
        bind.execute(
            sa.text(
                """
                UPDATE stock_items t
                   SET on_hand = t.on_hand + agg.extra_on_hand,
                       min_stock = GREATEST(t.min_stock, agg.max_min_stock)
                  FROM (SELECT m.survivor_id,
                               sum(l.on_hand) AS extra_on_hand,
                               max(l.min_stock) AS max_min_stock
                          FROM _si_merge m
                          JOIN stock_items l ON l.id = m.loser_id
                         GROUP BY m.survivor_id) agg
                 WHERE t.id = agg.survivor_id
                """
            )
        )
        bind.execute(
            sa.text(
                "UPDATE stock_transactions st SET stock_item_id = m.survivor_id "
                "FROM _si_merge m WHERE st.stock_item_id = m.loser_id"
            )
        )
        bind.execute(
            sa.text("DELETE FROM stock_items WHERE id IN (SELECT loser_id FROM _si_merge)")
        )
    op.execute("DROP TABLE _si_merge")


def _assert_cutting_panel_uniqueness(bind: sa.Connection) -> None:
    """`panel_index` restarts per material, so a merge can collide two panels.

    Renumbering is not an option: `panel_index` is echoed by the frozen result
    JSON and by the offcut blobs, so shifting it would corrupt exactly the
    history this migration exists to preserve. Fail loudly instead.
    """
    collisions = bind.execute(
        sa.text(
            """
            SELECT count(*) FROM (
                SELECT 1 FROM cutting_panels
                 GROUP BY cutting_result_id, branch_material_id, panel_index
                HAVING count(*) > 1) t
            """
        )
    ).scalar_one()
    if collisions:
        raise RuntimeError(
            f"{collisions} cutting_panels groups collide on "
            "(cutting_result_id, branch_material_id, panel_index) after merging duplicate "
            "catalog rows. Those results reference two materials that turned out to be the "
            "same dekor in the same format; resolve them by hand before re-running."
        )


# --------------------------------------------------------------------------- #
# 5. material ids embedded in JSON
# --------------------------------------------------------------------------- #


def _rewrite_material_id_json(bind: sa.Connection) -> None:
    """Re-key the JSON blobs that address materials by id.

    No foreign key covers these, so nothing would complain: the lookups would
    simply miss, blanking labels and pointing stock consumption at ids that no
    longer exist.
    """
    # `coalesce(m.survivor_id, bm.id)`: a blob may still name a material whose
    # branch row lost a merge, and that row is the only place the material_id
    # survives — resolve it straight to the survivor.
    lookup = {
        (row["branch_id"], row["material_id"]): str(row["effective_id"])
        for row in bind.execute(
            sa.text(
                "SELECT bm.branch_id, bm.material_id, "
                "coalesce(m.survivor_id, bm.id) AS effective_id "
                "FROM branch_materials bm LEFT JOIN _bm_merge m ON m.loser_id = bm.id"
            )
        ).mappings()
    }

    def remap(branch_id: Any, raw_material_id: Any) -> str | None:
        parsed = _as_uuid(raw_material_id)
        if parsed is None:
            return None
        return lookup.get((branch_id, parsed))

    _rewrite_cutting_drafts(bind, remap)
    _rewrite_cutting_results(bind, remap)
    _rewrite_orders(bind, remap)


def _rewrite_cutting_drafts(bind: sa.Connection, remap: Remap) -> None:
    for row in bind.execute(
        sa.text(
            "SELECT id, preferred_branch_id, parts_snapshot FROM cutting_drafts "
            "WHERE preferred_branch_id IS NOT NULL"
        )
    ).mappings():
        parts = _remap_parts(row["parts_snapshot"], row["preferred_branch_id"], remap)
        if parts is not None:
            bind.execute(
                sa.text(
                    "UPDATE cutting_drafts SET parts_snapshot = CAST(:p AS jsonb) WHERE id = :i"
                ),
                {"p": json.dumps(parts), "i": row["id"]},
            )


def _rewrite_cutting_results(bind: sa.Connection, remap: Remap) -> None:
    keyed = ", ".join(f"cr.{name}" for name in _RESULT_ID_KEYED_COLUMNS)
    for row in bind.execute(
        sa.text(
            f"SELECT cr.id, rb.branch_id, cr.parts_snapshot, {keyed} "  # noqa: S608
            f"FROM cutting_results cr JOIN ({_RESULT_BRANCH_SQL}) rb ON rb.result_id = cr.id"
        )
    ).mappings():
        branch_id = row["branch_id"]
        updates: dict[str, Any] = {}
        parts = _remap_parts(row["parts_snapshot"], branch_id, remap)
        if parts is not None:
            updates["parts_snapshot"] = parts
        for column in _RESULT_COUNTER_COLUMNS:
            rekeyed = _rekey(row[column], branch_id, remap, sum_values=True)
            if rekeyed is not None:
                updates[column] = rekeyed
        for column in _RESULT_SNAPSHOT_COLUMNS:
            rekeyed = _rekey(row[column], branch_id, remap, sum_values=False)
            if rekeyed is not None:
                updates[column] = rekeyed
        if not updates:
            continue
        assignments = ", ".join(f"{name} = CAST(:{name} AS jsonb)" for name in updates)
        bind.execute(
            sa.text(f"UPDATE cutting_results SET {assignments} WHERE id = :row_id"),  # noqa: S608
            {**{name: json.dumps(value) for name, value in updates.items()}, "row_id": row["id"]},
        )


def _rewrite_orders(bind: sa.Connection, remap: Remap) -> None:
    for row in bind.execute(
        sa.text(
            "SELECT id, branch_id, edge_length_snapshot FROM orders "
            "WHERE edge_length_snapshot IS NOT NULL"
        )
    ).mappings():
        rekeyed = _rekey(row["edge_length_snapshot"], row["branch_id"], remap, sum_values=True)
        if rekeyed is not None:
            bind.execute(
                sa.text("UPDATE orders SET edge_length_snapshot = CAST(:s AS jsonb) WHERE id = :i"),
                {"s": json.dumps(rekeyed), "i": row["id"]},
            )

    # `order_items.material_snapshot` is deliberately untouched — frozen
    # history. Only the edge blobs carry a live id that must follow the rename.
    for row in bind.execute(
        sa.text(
            "SELECT oi.id, o.branch_id, oi.edge_top, oi.edge_bottom, oi.edge_left, oi.edge_right "
            "FROM order_items oi JOIN orders o ON o.id = oi.order_id"
        )
    ).mappings():
        updates: dict[str, Any] = {}
        for side in _EDGE_SIDES:
            edge = _remap_edge(row[side], row["branch_id"], remap)
            if edge is not None:
                updates[side] = edge
        if not updates:
            continue
        assignments = ", ".join(f"{name} = CAST(:{name} AS jsonb)" for name in updates)
        bind.execute(
            sa.text(f"UPDATE order_items SET {assignments} WHERE id = :row_id"),  # noqa: S608
            {**{name: json.dumps(value) for name, value in updates.items()}, "row_id": row["id"]},
        )


def _rekey(blob: Any, branch_id: Any, remap: Remap, *, sum_values: bool) -> dict[str, Any] | None:
    if not isinstance(blob, dict) or not blob:
        return None
    out: dict[str, Any] = {}
    changed = False
    for key, value in blob.items():
        mapped = remap(branch_id, key)
        if mapped is not None and mapped != key:
            changed = True
        target = mapped or key
        if target in out:
            # Two old material ids collapsed onto one branch material.
            out[target] = _merge_counters(out[target], value) if sum_values else out[target]
        else:
            out[target] = value
    return out if changed else None


def _merge_counters(left: Any, right: Any) -> Any:
    """Add two tallies that used to hang off two ids and now share one."""
    if isinstance(left, bool) or isinstance(right, bool):
        return left
    if isinstance(left, int) and isinstance(right, int):
        return left + right
    if isinstance(left, dict) and isinstance(right, dict):
        merged = dict(left)
        for key, value in right.items():
            merged[key] = _merge_counters(merged[key], value) if key in merged else value
        return merged
    return left


def _remap_parts(blob: Any, branch_id: Any, remap: Remap) -> list[Any] | None:
    if not isinstance(blob, list) or not blob:
        return None
    changed = False
    out: list[Any] = []
    for part in blob:
        if not isinstance(part, dict):
            out.append(part)
            continue
        updated = dict(part)
        mapped = remap(branch_id, updated.get("material_id"))
        if mapped is not None and mapped != updated.get("material_id"):
            updated["material_id"] = mapped
            changed = True
        for side in _EDGE_SIDES:
            edge = _remap_edge(updated.get(side), branch_id, remap)
            if edge is not None:
                updated[side] = edge
                changed = True
        out.append(updated)
    return out if changed else None


def _remap_edge(edge: Any, branch_id: Any, remap: Remap) -> dict[str, Any] | None:
    if not isinstance(edge, dict):
        return None
    mapped = remap(branch_id, edge.get("material_id"))
    if mapped is None or mapped == edge.get("material_id"):
        return None
    return {**edge, "material_id": mapped}


def _collect_from_parts(pairs: set[tuple[Any, uuid.UUID]], branch_id: Any, blob: Any) -> None:
    if not isinstance(blob, list):
        return
    for part in blob:
        if not isinstance(part, dict):
            continue
        _add_pair(pairs, branch_id, part.get("material_id"))
        for side in _EDGE_SIDES:
            edge = part.get(side)
            if isinstance(edge, dict):
                _add_pair(pairs, branch_id, edge.get("material_id"))


def _collect_from_keys(pairs: set[tuple[Any, uuid.UUID]], branch_id: Any, blob: Any) -> None:
    if not isinstance(blob, dict):
        return
    for key in blob:
        _add_pair(pairs, branch_id, key)


def _add_pair(pairs: set[tuple[Any, uuid.UUID]], branch_id: Any, raw: Any) -> None:
    parsed = _as_uuid(raw)
    if parsed is not None:
        pairs.add((branch_id, parsed))


def _as_uuid(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# 6. lock the new shape in, drop the old one
# --------------------------------------------------------------------------- #


def _finalize_schema() -> None:
    op.alter_column("branch_materials", "dekor_id", nullable=False)
    op.alter_column("branch_materials", "qalinlik_mm", nullable=False)
    op.create_foreign_key(
        "fk_branch_materials_dekor_id", "branch_materials", "dekorlar", ["dekor_id"], ["id"]
    )
    op.drop_constraint("uq_branch_materials_branch_material", "branch_materials", type_="unique")
    op.drop_column("branch_materials", "material_id")
    op.create_index(
        "uq_branch_materials_branch_dekor_format",
        "branch_materials",
        [
            "branch_id",
            "dekor_id",
            "qalinlik_mm",
            sa.text("coalesce(uzunlik_mm, 0)"),
            sa.text("coalesce(eni_mm, 0)"),
            sa.text("coalesce(kromka_eni_mm, 0)"),
        ],
        unique=True,
    )
    op.create_check_constraint(
        "ck_branch_materials_qalinlik_positive", "branch_materials", "qalinlik_mm > 0"
    )
    op.create_check_constraint(
        "ck_branch_materials_kromka_eni_positive",
        "branch_materials",
        "kromka_eni_mm IS NULL OR kromka_eni_mm > 0",
    )
    op.create_check_constraint(
        "ck_branch_materials_panel_orientation",
        "branch_materials",
        "uzunlik_mm IS NULL OR eni_mm IS NULL OR uzunlik_mm >= eni_mm",
    )
    op.alter_column("branch_materials", "price_tiyin", server_default=sa.text("0"))

    op.alter_column("stock_items", "branch_material_id", nullable=False)
    op.create_foreign_key(
        "fk_stock_items_branch_material_id",
        "stock_items",
        "branch_materials",
        ["branch_material_id"],
        ["id"],
    )
    op.drop_constraint("uq_stock_items_branch_material", "stock_items", type_="unique")
    op.drop_column("stock_items", "material_id")
    op.create_unique_constraint(
        "uq_stock_items_branch_material", "stock_items", ["branch_material_id"]
    )

    op.alter_column("cutting_panels", "branch_material_id", nullable=False)
    op.create_foreign_key(
        "fk_cutting_panels_branch_material_id",
        "cutting_panels",
        "branch_materials",
        ["branch_material_id"],
        ["id"],
    )
    op.drop_constraint("uq_cutting_panels_result_material_index", "cutting_panels", type_="unique")
    op.drop_column("cutting_panels", "material_id")
    op.create_unique_constraint(
        "uq_cutting_panels_result_material_index",
        "cutting_panels",
        ["cutting_result_id", "branch_material_id", "panel_index"],
    )

    op.alter_column("order_items", "branch_material_id", nullable=False)
    op.create_foreign_key(
        "fk_order_items_branch_material_id",
        "order_items",
        "branch_materials",
        ["branch_material_id"],
        ["id"],
    )
    op.drop_column("order_items", "material_id")


def _drop_materials(bind: sa.Connection) -> None:
    op.drop_table("materials")
    # Native Postgres TYPEs outlive the columns that used them: dropping the
    # table does not drop these, and they must go after every referencing column
    # is already gone.
    sa.Enum(name="material_kind").drop(bind, checkfirst=True)
    sa.Enum(name="panel_material_type").drop(bind, checkfirst=True)
