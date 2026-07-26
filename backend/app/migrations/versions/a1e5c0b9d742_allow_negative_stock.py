"""allow negative stock balances

Order-driven `consume` records material that physically already moved, so the
books must be able to go negative when the matching arrival was never entered
(QAD-150). Forward-only: recording the arrival later brings the balance back to
the correct positive number on its own, so there is nothing to reconcile before
a downgrade — but a downgrade would fail on any row already negative, which is
exactly the state this migration exists to allow. Hence no `downgrade`.

Revision ID: a1e5c0b9d742
Revises: 37ee5335706c
Create Date: 2026-07-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1e5c0b9d742"
down_revision: str | None = "37ee5335706c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_stock_transactions_balance_nonnegative", "stock_transactions", type_="check"
    )
    op.drop_constraint("ck_stock_items_on_hand_nonnegative", "stock_items", type_="check")


def downgrade() -> None:
    raise NotImplementedError("Forward-only: negative balances cannot be re-constrained")
