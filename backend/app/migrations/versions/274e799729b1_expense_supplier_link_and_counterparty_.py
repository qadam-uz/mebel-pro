"""expense supplier link and counterparty adjustments

Revision ID: 274e799729b1
Revises: 2029483a3228
Create Date: 2026-07-18 05:33:42.737752
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "274e799729b1"
down_revision: str | None = "2029483a3228"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "counterparty_adjustments",
        sa.Column("workshop_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("amount_tiyin", sa.BigInteger(), nullable=False),
        sa.Column("adjusted_on", sa.Date(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.Column(
            "status",
            # The ledger_status type already exists (incomes/expenses) — reuse it.
            postgresql.ENUM("recorded", "voided", name="ledger_status", create_type=False),
            nullable=False,
        ),
        sa.Column("voided_reason", sa.String(), nullable=True),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("voided_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(supplier_id IS NOT NULL AND client_id IS NULL) OR (supplier_id IS NULL AND client_id IS NOT NULL)",
            name="ck_counterparty_adjustments_exactly_one_party",
        ),
        sa.CheckConstraint("amount_tiyin <> 0", name="ck_counterparty_adjustments_amount_nonzero"),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["workshop_users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["voided_by_user_id"],
            ["workshop_users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workshop_id"],
            ["workshops.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("expenses", sa.Column("supplier_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "expenses_supplier_id_fkey", "expenses", "suppliers", ["supplier_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("expenses_supplier_id_fkey", "expenses", type_="foreignkey")
    op.drop_column("expenses", "supplier_id")
    op.drop_table("counterparty_adjustments")
