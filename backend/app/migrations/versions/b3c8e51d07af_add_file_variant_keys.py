"""add file variant keys

Revision ID: b3c8e51d07af
Revises: a1f7c2d94e30
Create Date: 2026-08-08 00:00:00.000000

Records which downscaled renditions exist for an uploaded image, as
{"sm": "<storage key>", "md": "<storage key>"}.

Nullable with no backfill in the migration itself, deliberately. The column is
absent for PDFs, absent for images already smaller than a rendition, and absent
for every image uploaded before this ships — and the read path treats all three
identically by falling back to the original. So an empty column is a correct
state, not a pending one, and the deploy needs no data step to be safe.

Filling it in for the ~1200 existing catalog images is a separate, resumable
command (`python -m app.cli backfill-image-variants`) that re-reads each original
from the object store and writes the renditions. That work does not belong in a
migration: it is measured in minutes, it talks to MinIO, and a failure part-way
through must not roll back a schema change.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b3c8e51d07af"
down_revision: str | None = "a1f7c2d94e30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column("variant_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("files", "variant_keys")
