"""add nullable per-panel cut metrics

Revision ID: a9d0e1f2c3b4
Revises: f4a5b6c7d8e9
Create Date: 2026-07-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9d0e1f2c3b4"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cutting_panels", sa.Column("cut_count", sa.Integer(), nullable=True))
    op.add_column("cutting_panels", sa.Column("cut_length_mm", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_cutting_panels_cut_count",
        "cutting_panels",
        "cut_count IS NULL OR cut_count >= 0",
    )
    op.create_check_constraint(
        "ck_cutting_panels_cut_length",
        "cutting_panels",
        "cut_length_mm IS NULL OR cut_length_mm >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_cutting_panels_cut_length", "cutting_panels", type_="check")
    op.drop_constraint("ck_cutting_panels_cut_count", "cutting_panels", type_="check")
    op.drop_column("cutting_panels", "cut_length_mm")
    op.drop_column("cutting_panels", "cut_count")
