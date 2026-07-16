"""add cutting draft name

Revision ID: 6b7c8d9e0f1a
Revises: 8d1785741662
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6b7c8d9e0f1a"
down_revision: str | None = "8d1785741662"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cutting_drafts", sa.Column("name", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("cutting_drafts", "name")
