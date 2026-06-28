"""make branch coordinates optional

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-06-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("branches", "latitude", existing_type=sa.Numeric(), nullable=True)
    op.alter_column("branches", "longitude", existing_type=sa.Numeric(), nullable=True)


def downgrade() -> None:
    # Forward-only production change. Making these NOT NULL again would need a
    # new migration with an explicit backfill rule for branches that now store
    # unknown coordinates as null.
    pass
