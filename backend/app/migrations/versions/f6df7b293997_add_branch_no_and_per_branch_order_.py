"""add branch_no and per-branch order numbers

Revision ID: f6df7b293997
Revises: 37ee5335706c
Create Date: 2026-07-26 06:41:46.329110
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6df7b293997"
down_revision: str | None = "37ee5335706c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable first so existing rows survive the ALTER; backfilled below.
    op.add_column("branches", sa.Column("branch_no", sa.Integer(), nullable=True))
    # Oldest branch gets 1 — stable across re-runs, and the order an operator
    # would count the platform's branches in.
    op.execute(
        sa.text(
            """
            UPDATE branches AS b
            SET branch_no = numbered.row_number
            FROM (
                SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS row_number
                FROM branches
            ) AS numbered
            WHERE b.id = numbered.id
            """
        )
    )
    op.alter_column("branches", "branch_no", existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint("uq_branches_branch_no", "branches", ["branch_no"])
    # Autogenerate misses CheckConstraints — added by hand (backend/AGENTS.md).
    op.create_check_constraint("ck_branches_branch_no_positive", "branches", "branch_no >= 1")


def downgrade() -> None:
    op.drop_constraint("ck_branches_branch_no_positive", "branches", type_="check")
    op.drop_constraint("uq_branches_branch_no", "branches", type_="unique")
    op.drop_column("branches", "branch_no")
