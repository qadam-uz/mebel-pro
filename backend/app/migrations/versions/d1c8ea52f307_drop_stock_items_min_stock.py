"""Drop stock_items.min_stock — the low-stock threshold has one home

The threshold was stored twice: on `branch_materials.min_stock`, where the UI
writes it, and mirrored onto `stock_items.min_stock` so the low-stock filter
could be a single-table predicate. The mirror was maintained by an explicit
`sync_stock_item_min_stock()` call, which is exactly how two copies drift — any
write path that forgets it leaves the alert comparing against a stale number,
silently and forever.

`stock_items` is now only the balance. Every reader joins to the branch material
for the threshold; the join is free because `stock_items.branch_material_id` is
already unique, and `branch_materials` is already in the low-stock query.

Divergence at the time of this migration is *reported, not merged*:
`branch_materials` is the value the operator actually typed, so it simply wins.
The count is logged so a real drift in production is visible rather than
silently discarded.

Revision ID: d1c8ea52f307
Revises: c9f4a2b71e83
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1c8ea52f307"
down_revision: str | None = "c9f4a2b71e83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("stock_items")}
    if "min_stock" not in columns:
        # A database created from current metadata never had the column.
        return

    diverged = bind.execute(
        sa.text(
            "SELECT count(*) FROM stock_items s "
            "JOIN branch_materials bm ON bm.id = s.branch_material_id "
            "WHERE s.min_stock IS DISTINCT FROM bm.min_stock"
        )
    ).scalar_one()
    if diverged:
        print(
            f"[d1c8ea52f307] {diverged} stock_items row(s) had a threshold "
            "differing from their branch material; branch_materials.min_stock wins."
        )

    constraints = {c["name"] for c in inspector.get_check_constraints("stock_items")}
    if "ck_stock_items_min_stock_nonnegative" in constraints:
        op.drop_constraint("ck_stock_items_min_stock_nonnegative", "stock_items", type_="check")
    op.drop_column("stock_items", "min_stock")


def downgrade() -> None:
    op.add_column(
        "stock_items",
        sa.Column("min_stock", sa.Integer(), nullable=False, server_default="0"),
    )
    # Refill from the single source so a downgraded database is consistent rather
    # than uniformly zero — a zero threshold silences every low-stock alert.
    op.execute(
        sa.text(
            "UPDATE stock_items s SET min_stock = bm.min_stock "
            "FROM branch_materials bm WHERE bm.id = s.branch_material_id"
        )
    )
    op.create_check_constraint(
        "ck_stock_items_min_stock_nonnegative", "stock_items", "min_stock >= 0"
    )
    op.alter_column("stock_items", "min_stock", server_default=None)
