"""per-branch edge overhang

Revision ID: 8a41c7b0d5e2
Revises: b3c8e51d07af
Create Date: 2026-08-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a41c7b0d5e2"
down_revision: str | None = "b3c8e51d07af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 30 mm was the platform-wide constant before this column existed, so the
    # server default keeps every existing branch billing exactly as it did.
    op.add_column(
        "branches",
        sa.Column("edge_overhang_mm", sa.Integer(), server_default="30", nullable=False),
    )
    # Autogenerate misses CheckConstraints — added by hand (backend/AGENTS.md).
    op.create_check_constraint(
        "ck_branches_edge_overhang_mm",
        "branches",
        "edge_overhang_mm >= 0 AND edge_overhang_mm <= 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_branches_edge_overhang_mm", "branches", type_="check")
    op.drop_column("branches", "edge_overhang_mm")
