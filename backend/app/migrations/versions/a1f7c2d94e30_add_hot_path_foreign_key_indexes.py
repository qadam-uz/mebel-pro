"""add hot-path foreign key indexes

Revision ID: a1f7c2d94e30
Revises: 9c3e1f8a24b7
Create Date: 2026-08-08 00:00:00.000000

Postgres indexes primary keys and unique constraints automatically. It does not
index foreign keys — and nearly every read here is "give me the children of this
parent". Forty-five FK columns were bare; these are the ten whose queries sit on
a hot path over a table that actually grows.

At today's volumes none of this is visible, which is why it is not a fix for the
latency reported now. It is the reason that latency will not appear later.
Measured on a schema-identical throwaway database seeded to the envelope in
docs/architecture.md (40 000 orders — two years at the documented rate — and the
1 000 000 order_items that implies):

    order_items lookup by order_id     21.6 ms -> 0.15 ms   (parallel seq scan -> index)
    workshop order list, one branch     5.6 ms -> 0.18 ms   (seq scan -> index scan)

The first runs on every order detail view and every order mutation response; the
second on every workshop order list and production queue load. The remaining
eight follow the same shape on the same kind of query and were measured by the
same method; the two above were re-measured independently before this shipped.

Three indexes are partial. `incomes.order_id`, `expenses.invoice_id` and
`stock_transactions.invoice_id` are NULL on most rows by design — each is
confined by a CHECK constraint to one ledger type — and every query that uses
them supplies an equality, from which the planner proves NOT NULL and uses the
partial index. Indexing only the rows that can match keeps them small.

Column order, where it is not forced: `stock_transactions (stock_item_id,
created_at)` because consumers filter on the item then take the newest row, so
the second column turns a sort into a backward index walk.
`orders (workshop_id, branch_id, status)` puts `status` last because it is the
column most often absent from the predicate — the two-column prefix stays useful
for the queries that omit it.

SAFETY. At current row counts each CREATE INDEX below finishes in milliseconds,
so the plain form inside Alembic's transaction is fine. It does take an ACCESS
EXCLUSIVE lock per table for that moment. If any of these tables ever grows to
where that pause matters, switch that statement to CREATE INDEX CONCURRENTLY —
which cannot run inside a transaction and so needs its own migration with
`autocommit_block()`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f7c2d94e30"
down_revision: str | None = "9c3e1f8a24b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # sales — the order detail page and every order mutation response read both
    # of these by order_id, in the same request.
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)
    op.create_index(
        "ix_order_status_events_order_id",
        "order_status_events",
        ["order_id"],
        unique=False,
    )
    # The workshop order list, the new-order badge, and both production-queue
    # stations scope by workshop then branch, with status an optional tail.
    op.create_index(
        "ix_orders_workshop_branch_status",
        "orders",
        ["workshop_id", "branch_id", "status"],
        unique=False,
    )

    # finance / inventory — settlement folds evaluated once per candidate row,
    # before any LIMIT applies.
    op.create_index(
        "ix_incomes_order_id",
        "incomes",
        ["order_id"],
        unique=False,
        postgresql_where=sa.text("order_id IS NOT NULL"),
    )
    op.create_index(
        "ix_expenses_invoice_id",
        "expenses",
        ["invoice_id"],
        unique=False,
        postgresql_where=sa.text("invoice_id IS NOT NULL"),
    )
    op.create_index(
        "ix_stock_transactions_item_created",
        "stock_transactions",
        ["stock_item_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_stock_transactions_invoice_id",
        "stock_transactions",
        ["invoice_id"],
        unique=False,
        postgresql_where=sa.text("invoice_id IS NOT NULL"),
    )

    # cutting — placements is the widest child table in the schema and carried
    # nothing but its primary key. The index also serves the delete side of
    # re-optimizing a draft, so it earns back its own write cost.
    op.create_index(
        "ix_cutting_placements_panel_id",
        "cutting_placements",
        ["cutting_panel_id"],
        unique=False,
    )
    op.create_index("ix_cutting_results_draft_id", "cutting_results", ["draft_id"], unique=False)

    # catalog — the per-image authorization probe for dekor photos. The existing
    # uq_branch_materials_branch_dekor_format leads with branch_id, so it cannot
    # answer a lookup keyed on dekor_id alone.
    op.create_index("ix_branch_materials_dekor_id", "branch_materials", ["dekor_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_branch_materials_dekor_id", table_name="branch_materials")
    op.drop_index("ix_cutting_results_draft_id", table_name="cutting_results")
    op.drop_index("ix_cutting_placements_panel_id", table_name="cutting_placements")
    op.drop_index("ix_stock_transactions_invoice_id", table_name="stock_transactions")
    op.drop_index("ix_stock_transactions_item_created", table_name="stock_transactions")
    op.drop_index("ix_expenses_invoice_id", table_name="expenses")
    op.drop_index("ix_incomes_order_id", table_name="incomes")
    op.drop_index("ix_orders_workshop_branch_status", table_name="orders")
    op.drop_index("ix_order_status_events_order_id", table_name="order_status_events")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
