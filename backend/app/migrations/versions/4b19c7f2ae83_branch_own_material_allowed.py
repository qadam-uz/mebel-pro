"""branch own material allowed

Revision ID: 4b19c7f2ae83
Revises: 0c079c46ac6e
Create Date: 2026-08-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b19c7f2ae83"
down_revision: str | None = "0c079c46ac6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Accepting a client's own sheets is a deliberate choice per branch — it
    # changes what the shop stores, what it is liable for, and what has to
    # arrive before the saw can start. So the column opens closed: a branch
    # turns it on, rather than discovering it was on all along.
    op.add_column(
        "branches",
        sa.Column(
            "own_material_allowed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("branches", "own_material_allowed")
