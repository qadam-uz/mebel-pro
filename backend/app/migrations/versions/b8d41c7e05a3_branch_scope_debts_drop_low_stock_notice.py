"""Branch-scope counterparty debts; drop the low-stock notification (QAD-182).

Two independent cleanups that have to land together because both touch rows a
running workshop can see:

1. `inventory.low_stock` stops being a notification. The signal lives on the
   Ombor row (`is_low_stock`) and in the «Kam qolgan materiallar» filter, which
   is where an operator looks for it; as a bell entry it was noise. Existing
   rows are deleted rather than left behind — the presenter that translated the
   code is gone in the same change, so keeping them would print a raw event
   code in the workshop's bell.

2. Debts become per branch. Every term in the fold already named a branch
   except two: `counterparty_adjustments` had no `branch_id` at all, and a
   supplier-linked `expense` could be workshop-wide. Both are backfilled to the
   workshop's first branch (lowest `branch_no`) — the only defensible guess,
   and the branch a single-branch workshop has anyway.

Revision ID: b8d41c7e05a3
Revises: 5bf3db336f47
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d41c7e05a3"
down_revision: str | None = "5bf3db336f47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Both backfills pick the workshop's first branch by `branch_no`, so an
# adjustment and the expense beside it land in the same place. Written out per
# table rather than templated: the correlated subquery has to name its outer
# table, and a literal reads better than a format call in a migration.
_BACKFILL_ADJUSTMENTS = """
UPDATE counterparty_adjustments
SET branch_id = (
    SELECT b.id
    FROM branches AS b
    WHERE b.workshop_id = counterparty_adjustments.workshop_id
    ORDER BY b.branch_no
    LIMIT 1
)
WHERE branch_id IS NULL
"""

_BACKFILL_SUPPLIER_EXPENSES = """
UPDATE expenses
SET branch_id = (
    SELECT b.id
    FROM branches AS b
    WHERE b.workshop_id = expenses.workshop_id
    ORDER BY b.branch_no
    LIMIT 1
)
WHERE branch_id IS NULL AND supplier_id IS NOT NULL
"""


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM notifications WHERE event_code = 'inventory.low_stock'"))

    op.add_column(
        "counterparty_adjustments",
        sa.Column("branch_id", sa.Uuid(), nullable=True),
    )
    op.execute(sa.text(_BACKFILL_ADJUSTMENTS))
    # A workshop with no branch at all cannot hold a debt adjustment; if one
    # somehow exists the NOT NULL below is the right place to find out.
    op.alter_column("counterparty_adjustments", "branch_id", nullable=False)
    op.create_foreign_key(
        "fk_counterparty_adjustments_branch_id_branches",
        "counterparty_adjustments",
        "branches",
        ["branch_id"],
        ["id"],
    )

    op.execute(sa.text(_BACKFILL_SUPPLIER_EXPENSES))
    op.create_check_constraint(
        "ck_expenses_supplier_requires_branch",
        "expenses",
        "supplier_id IS NULL OR branch_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_expenses_supplier_requires_branch", "expenses", type_="check")
    op.drop_constraint(
        "fk_counterparty_adjustments_branch_id_branches",
        "counterparty_adjustments",
        type_="foreignkey",
    )
    op.drop_column("counterparty_adjustments", "branch_id")
