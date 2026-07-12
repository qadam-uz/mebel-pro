"""add production assign and start stamps

Revision ID: 976db35e768a
Revises: a5b6c7d8e9f0
Create Date: 2026-07-11 17:49:23.865671
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "976db35e768a"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders", sa.Column("cutter_assigned_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("edger_assigned_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("cutting_started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("banding_started_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("orders", "banding_started_at")
    op.drop_column("orders", "cutting_started_at")
    op.drop_column("orders", "edger_assigned_at")
    op.drop_column("orders", "cutter_assigned_at")
