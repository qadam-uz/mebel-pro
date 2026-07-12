"""merge catalog material identity and production assign heads

Revision ID: 8d1785741662
Revises: 0a1b2c3d4e5f, 976db35e768a
Create Date: 2026-07-12 20:19:34.422851
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d1785741662"
down_revision: str | None = ("0a1b2c3d4e5f", "976db35e768a")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
