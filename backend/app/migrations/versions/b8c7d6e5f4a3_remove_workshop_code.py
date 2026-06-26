"""remove workshop code

Revision ID: b8c7d6e5f4a3
Revises: 4f1c2d8e9a0b
Create Date: 2026-06-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c7d6e5f4a3"
down_revision: str | None = "4f1c2d8e9a0b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("workshops")}
    indexes = {index["name"] for index in inspector.get_indexes("workshops")}

    if "uq_workshops_code_ci" in indexes:
        op.drop_index("uq_workshops_code_ci", table_name="workshops")
    if "code" in columns:
        op.drop_column("workshops", "code")
    if "phone" in columns:
        op.alter_column("workshops", "phone", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Forward-only production cleanup. Reintroducing code would require a new
    # forward migration that decides how to backfill unique values.
    pass
