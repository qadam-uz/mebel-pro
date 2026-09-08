"""Workshop-owned catalog rows, and the retired low-stock threshold

Two changes the same release makes to `branch_materials`' neighbourhood.

**Ownership.** `manufacturers`, `decors` and `decor_formats` each gain a nullable
`workshop_id`. `NULL` means "library row" — the platform's pre-filled list — and
every existing row is one by definition, so there is no backfill. A value means
one workshop wrote it, and only that workshop can see it. The partial unique
indexes split into two arms each (`WHERE workshop_id IS NULL` for the library,
`(workshop_id, ...) WHERE workshop_id IS NOT NULL` for the workshops): NULLs are
distinct inside a unique index, so one index genuinely cannot cover both — with a
single `(workshop_id, lower(name))` index the library could hold «Egger» twice,
and with the old index alone a workshop could not enter a maker whose library row
it is not allowed to see.

**The threshold goes.** `branch_materials.min_stock` and its CHECK are dropped:
the per-material low-stock warning is retired (2026-09-08 — "a warning that is
everywhere is nowhere"), leaving `on_hand < 0` as the only stock alarm, which
needs no stored number. The `stock_items` mirror went the same way in
`d1c8ea52f307`; this is the source column following it. `inventory.min_stock.update`
audit rows stay — history is not rewritten, it just stops growing.

Forward-only in spirit: `downgrade()` restores the shape, not the numbers. Every
threshold reverts to 0, i.e. monitoring off, which is the safe direction — a
restored-but-wrong threshold would alarm on the wrong rows.

Revision ID: f2b7d41c908e
Revises: e1a4c8b70d35
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b7d41c908e"
down_revision: str | None = "e1a4c8b70d35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIBRARY = "workshop_id IS NULL"
OWNED = "workshop_id IS NOT NULL"

_OWNED_TABLES = ("manufacturers", "decors", "decor_formats")

# The natural key of a format, as the index columns spell it.
_FORMAT_KEY = [
    "decor_id",
    "type",
    "thickness_mm",
    sa.text("coalesce(length_mm, 0)"),
    sa.text("coalesce(width_mm, 0)"),
    sa.text("coalesce(tape_width_mm, 0)"),
    sa.text("coalesce(finished_sides, 0)"),
]


def upgrade() -> None:
    for table in _OWNED_TABLES:
        op.add_column(table, sa.Column("workshop_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_workshop_id_workshops", table, "workshops", ["workshop_id"], ["id"]
        )
        op.create_index(f"ix_{table}_workshop_id", table, ["workshop_id"])

    op.drop_index("uq_manufacturers_name_ci", table_name="manufacturers")
    op.create_index(
        "uq_manufacturers_name_ci",
        "manufacturers",
        [sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text(LIBRARY),
        sqlite_where=sa.text(LIBRARY),
    )
    op.create_index(
        "uq_manufacturers_ws_name_ci",
        "manufacturers",
        ["workshop_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text(OWNED),
        sqlite_where=sa.text(OWNED),
    )

    op.drop_index("uq_decors_manufacturer_code_ci", table_name="decors")
    op.drop_index("uq_decors_manufacturer_name_ci", table_name="decors")
    for name, code_predicate, ownership, columns in (
        (
            "uq_decors_manufacturer_code_ci",
            "code IS NOT NULL",
            LIBRARY,
            ["manufacturer_id", sa.text("lower(code)")],
        ),
        (
            "uq_decors_manufacturer_name_ci",
            "code IS NULL",
            LIBRARY,
            ["manufacturer_id", sa.text("lower(name)")],
        ),
        (
            "uq_decors_ws_manufacturer_code_ci",
            "code IS NOT NULL",
            OWNED,
            ["workshop_id", "manufacturer_id", sa.text("lower(code)")],
        ),
        (
            "uq_decors_ws_manufacturer_name_ci",
            "code IS NULL",
            OWNED,
            ["workshop_id", "manufacturer_id", sa.text("lower(name)")],
        ),
    ):
        predicate = sa.text(f"{code_predicate} AND {ownership}")
        op.create_index(
            name,
            "decors",
            columns,
            unique=True,
            postgresql_where=predicate,
            sqlite_where=predicate,
        )

    op.drop_index("uq_decor_formats_natural_key", table_name="decor_formats")
    op.create_index(
        "uq_decor_formats_natural_key",
        "decor_formats",
        _FORMAT_KEY,
        unique=True,
        postgresql_where=sa.text(LIBRARY),
        sqlite_where=sa.text(LIBRARY),
    )
    op.create_index(
        "uq_decor_formats_ws_natural_key",
        "decor_formats",
        ["workshop_id", *_FORMAT_KEY],
        unique=True,
        postgresql_where=sa.text(OWNED),
        sqlite_where=sa.text(OWNED),
    )

    _drop_min_stock()


def _drop_min_stock() -> None:
    """`branch_materials.min_stock` and its CHECK — guarded like `d1c8ea52f307`.

    A database created from current metadata never had the column, and this
    revision has to be re-runnable against one.
    """

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "min_stock" not in {c["name"] for c in inspector.get_columns("branch_materials")}:
        return
    constraints = {c["name"] for c in inspector.get_check_constraints("branch_materials")}
    if "ck_branch_materials_min_stock_nonnegative" in constraints:
        op.drop_constraint(
            "ck_branch_materials_min_stock_nonnegative", "branch_materials", type_="check"
        )
    op.drop_column("branch_materials", "min_stock")


def downgrade() -> None:
    op.add_column(
        "branch_materials",
        sa.Column("min_stock", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_branch_materials_min_stock_nonnegative", "branch_materials", "min_stock >= 0"
    )
    op.alter_column("branch_materials", "min_stock", server_default=None)

    op.drop_index("uq_decor_formats_ws_natural_key", table_name="decor_formats")
    op.drop_index("uq_decor_formats_natural_key", table_name="decor_formats")
    op.create_index("uq_decor_formats_natural_key", "decor_formats", _FORMAT_KEY, unique=True)

    for name in (
        "uq_decors_ws_manufacturer_name_ci",
        "uq_decors_ws_manufacturer_code_ci",
        "uq_decors_manufacturer_name_ci",
        "uq_decors_manufacturer_code_ci",
    ):
        op.drop_index(name, table_name="decors")
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

    op.drop_index("uq_manufacturers_ws_name_ci", table_name="manufacturers")
    op.drop_index("uq_manufacturers_name_ci", table_name="manufacturers")
    op.create_index(
        "uq_manufacturers_name_ci", "manufacturers", [sa.text("lower(name)")], unique=True
    )

    for table in reversed(_OWNED_TABLES):
        op.drop_index(f"ix_{table}_workshop_id", table_name=table)
        op.drop_constraint(f"fk_{table}_workshop_id_workshops", table, type_="foreignkey")
        op.drop_column(table, "workshop_id")
