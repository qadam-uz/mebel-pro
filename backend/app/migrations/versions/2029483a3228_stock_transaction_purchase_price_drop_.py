"""stock transaction purchase price, drop receipt

Revision ID: 2029483a3228
Revises: 6b7c8d9e0f1a
Create Date: 2026-07-18 05:12:39.116673
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2029483a3228"
down_revision: str | None = "6b7c8d9e0f1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_transactions", sa.Column("unit_price_tiyin", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "stock_transactions", sa.Column("total_price_tiyin", sa.BigInteger(), nullable=True)
    )
    op.create_check_constraint(
        "ck_stock_transactions_price_stock_in_only",
        "stock_transactions",
        "type = 'stock_in' OR (unit_price_tiyin IS NULL AND total_price_tiyin IS NULL)",
    )
    op.create_check_constraint(
        "ck_stock_transactions_price_nonnegative",
        "stock_transactions",
        "(unit_price_tiyin IS NULL OR unit_price_tiyin >= 0) AND "
        "(total_price_tiyin IS NULL OR total_price_tiyin >= 0)",
    )
    op.drop_constraint(
        op.f("stock_transactions_receipt_file_id_fkey"), "stock_transactions", type_="foreignkey"
    )
    op.drop_column("stock_transactions", "receipt_file_id")


def downgrade() -> None:
    op.add_column(
        "stock_transactions",
        sa.Column("receipt_file_id", sa.UUID(), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(
        op.f("stock_transactions_receipt_file_id_fkey"),
        "stock_transactions",
        "files",
        ["receipt_file_id"],
        ["id"],
    )
    op.drop_constraint(
        "ck_stock_transactions_price_nonnegative", "stock_transactions", type_="check"
    )
    op.drop_constraint(
        "ck_stock_transactions_price_stock_in_only", "stock_transactions", type_="check"
    )
    op.drop_column("stock_transactions", "total_price_tiyin")
    op.drop_column("stock_transactions", "unit_price_tiyin")
