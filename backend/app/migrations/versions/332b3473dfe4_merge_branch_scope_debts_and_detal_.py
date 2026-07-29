"""merge branch-scope debts and detal glossary heads

Revision ID: 332b3473dfe4
Revises: b8d41c7e05a3, c022e297a4ba
Create Date: 2026-07-28 19:52:34.974624
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "332b3473dfe4"
down_revision: str | None = ("b8d41c7e05a3", "c022e297a4ba")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
