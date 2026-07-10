"""add cutting result source

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    source_enum = sa.Enum(
        "optimizer",
        "imported_map",
        name="cutting_result_source",
    )
    source_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "cutting_results",
        sa.Column(
            "source",
            source_enum,
            server_default="optimizer",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("cutting_results", "source")
    sa.Enum(name="cutting_result_source").drop(op.get_bind(), checkfirst=True)
