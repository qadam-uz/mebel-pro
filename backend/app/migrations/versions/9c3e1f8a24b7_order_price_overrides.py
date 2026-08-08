"""order price overrides

Revision ID: 9c3e1f8a24b7
Revises: 4b19c7f2ae83
Create Date: 2026-08-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9c3e1f8a24b7"
down_revision: str | None = "4b19c7f2ae83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The unit prices staff typed for THIS order, replacing the branch's rate
    # card. Kept on the order rather than only written into the item snapshots
    # because the order re-prices for other reasons too (a revision, a change of
    # who supplies the sheets) — without a home here, the next re-price would
    # quietly restore the branch's list price under the agreed one.
    op.add_column(
        "orders",
        sa.Column(
            "price_overrides",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "price_overrides")
