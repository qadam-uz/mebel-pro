"""workshop public code

Revision ID: f1c8d3a29b47
Revises: d3f5a9c1e846
Create Date: 2026-08-31 19:40:00.000000
"""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1c8d3a29b47"
down_revision: str | None = "d3f5a9c1e846"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Crockford base32 (no I, L, O, U) — kept literal here rather than imported from
# `app.modules.workshop.public_code` so this revision keeps producing the codes
# it produced on the day it ran, whatever the model does later.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_LENGTH = 8


def _code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))


def upgrade() -> None:
    # Three steps rather than one `server_default`: the code must be unique per
    # row, so it cannot come from a default. Add nullable, fill every existing
    # workshop, then close the column.
    op.add_column("workshops", sa.Column("public_code", sa.String(), nullable=True))

    bind = op.get_bind()
    used: set[str] = set()
    for (workshop_id,) in bind.execute(sa.text("SELECT id FROM workshops")).fetchall():
        code = _code()
        while code in used:
            code = _code()
        used.add(code)
        bind.execute(
            sa.text("UPDATE workshops SET public_code = :code WHERE id = :id"),
            {"code": code, "id": workshop_id},
        )

    with op.batch_alter_table("workshops") as batch:
        batch.alter_column("public_code", existing_type=sa.String(), nullable=False)
        batch.create_unique_constraint("uq_workshops_public_code", ["public_code"])


def downgrade() -> None:
    with op.batch_alter_table("workshops") as batch:
        batch.drop_constraint("uq_workshops_public_code", type_="unique")
    op.drop_column("workshops", "public_code")
