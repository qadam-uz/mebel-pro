"""remove workshop contact fields

Revision ID: c1d2e3f4a5b6
Revises: b8c7d6e5f4a3
Create Date: 2026-06-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b8c7d6e5f4a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("workshops")}
    if "phone" in columns:
        op.drop_column("workshops", "phone")
    if "address" in columns:
        op.drop_column("workshops", "address")


def downgrade() -> None:
    # Forward-only production cleanup. Reintroducing workshop contact fields
    # would need a new migration with an explicit branch-derived backfill rule.
    pass
