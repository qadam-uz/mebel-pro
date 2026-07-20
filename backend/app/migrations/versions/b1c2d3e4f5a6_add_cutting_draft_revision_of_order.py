"""add cutting draft revision_of_order_id

Revision ID: b1c2d3e4f5a6
Revises: 274e799729b1
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "274e799729b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cutting_drafts",
        sa.Column("revision_of_order_id", sa.Uuid(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_cutting_drafts_revision_order", "cutting_drafts", ["revision_of_order_id"]
    )
    op.create_foreign_key(
        "fk_cutting_drafts_revision_of_order_id",
        "cutting_drafts",
        "orders",
        ["revision_of_order_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cutting_drafts_revision_of_order_id", "cutting_drafts", type_="foreignkey"
    )
    op.drop_constraint("uq_cutting_drafts_revision_order", "cutting_drafts", type_="unique")
    op.drop_column("cutting_drafts", "revision_of_order_id")
