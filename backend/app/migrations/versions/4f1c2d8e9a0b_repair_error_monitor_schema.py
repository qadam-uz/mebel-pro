"""repair error monitor schema

Revision ID: 4f1c2d8e9a0b
Revises: 9d6b2e1f4a7c
Create Date: 2026-06-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f1c2d8e9a0b"
down_revision: str | None = "9d6b2e1f4a7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    error_record_columns = _columns(inspector, "error_records")
    if "count_24h" not in error_record_columns:
        op.add_column(
            "error_records",
            sa.Column("count_24h", sa.Integer(), nullable=False, server_default="0"),
        )
    if "count_7d" not in error_record_columns:
        op.add_column(
            "error_records",
            sa.Column("count_7d", sa.Integer(), nullable=False, server_default="0"),
        )
    if "last_occurred_at" not in error_record_columns:
        op.add_column(
            "error_records",
            sa.Column("last_occurred_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "preview_message" not in error_record_columns:
        op.add_column("error_records", sa.Column("preview_message", sa.String(), nullable=True))
    if "resolved_by_user_id" not in error_record_columns:
        op.add_column("error_records", sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True))
    if "resolved_at" not in error_record_columns:
        op.add_column(
            "error_records",
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )

    error_occurrence_columns = _columns(inspector, "error_occurrences")
    if "stack" not in error_occurrence_columns:
        op.add_column("error_occurrences", sa.Column("stack", sa.String(), nullable=True))
    if "context" not in error_occurrence_columns:
        op.add_column("error_occurrences", sa.Column("context", sa.JSON(), nullable=True))
    if "workshop_id" not in error_occurrence_columns:
        op.add_column("error_occurrences", sa.Column("workshop_id", sa.Uuid(), nullable=True))
    if "user_id" not in error_occurrence_columns:
        op.add_column("error_occurrences", sa.Column("user_id", sa.Uuid(), nullable=True))

    if "ix_error_occurrences_record_time" not in _indexes(inspector, "error_occurrences"):
        op.create_index(
            "ix_error_occurrences_record_time",
            "error_occurrences",
            ["error_record_id", "occurred_at"],
            unique=False,
        )


def downgrade() -> None:
    # Forward-only drift repair: fresh databases already get these columns from
    # the initial migration, so downgrade cannot safely know what this revision
    # added on an older production database.
    pass


def _columns(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}
