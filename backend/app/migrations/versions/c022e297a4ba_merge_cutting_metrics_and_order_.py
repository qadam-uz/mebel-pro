"""merge cutting metrics and order revision heads

Revision ID: c022e297a4ba
Revises: a9d0e1f2c3b4, b1c2d3e4f5a6
Create Date: 2026-07-23 21:20:05.842709
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c022e297a4ba"
down_revision: str | tuple[str, ...] | None = ("a9d0e1f2c3b4", "b1c2d3e4f5a6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
