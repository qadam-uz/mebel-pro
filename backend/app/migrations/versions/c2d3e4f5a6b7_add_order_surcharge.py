"""add order surcharge (ustama)

Adds the symmetric surcharge adjustment alongside the existing discount and
rewrites the total-formula check constraint to include it:
total = subtotal_cutting + subtotal_materials + subtotal_edge_banding
        - discount_tiyin + surcharge_tiyin.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("surcharge_tiyin", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column("orders", sa.Column("surcharge_reason", sa.String(), nullable=True))
    op.add_column("orders", sa.Column("surcharge_applied_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_orders_surcharge_applied_by_user_id",
        "orders",
        "workshop_users",
        ["surcharge_applied_by_user_id"],
        ["id"],
    )
    # The stored total formula is DB-enforced — rebuild it to add the surcharge term.
    op.drop_constraint("ck_orders_total_formula", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_total_formula",
        "orders",
        "total_tiyin = ("
        "subtotal_cutting_tiyin + subtotal_materials_tiyin "
        "+ subtotal_edge_banding_tiyin - discount_tiyin + surcharge_tiyin)",
    )
    op.create_check_constraint("ck_orders_surcharge_nonnegative", "orders", "surcharge_tiyin >= 0")
    op.create_check_constraint(
        "ck_orders_surcharge_metadata_required",
        "orders",
        "surcharge_tiyin = 0 OR ("
        "surcharge_reason IS NOT NULL AND surcharge_applied_by_user_id IS NOT NULL)",
    )
    # The server_default was only needed to backfill existing rows; the model
    # sets 0 explicitly on insert, so drop it to keep the column app-controlled.
    op.alter_column("orders", "surcharge_tiyin", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_orders_surcharge_metadata_required", "orders", type_="check")
    op.drop_constraint("ck_orders_surcharge_nonnegative", "orders", type_="check")
    op.drop_constraint("ck_orders_total_formula", "orders", type_="check")
    # Fold any applied surcharge back out of the stored total so the restored
    # discount-only formula holds for every existing row before it's validated.
    op.execute("UPDATE orders SET total_tiyin = total_tiyin - surcharge_tiyin")
    op.create_check_constraint(
        "ck_orders_total_formula",
        "orders",
        "total_tiyin = ("
        "subtotal_cutting_tiyin + subtotal_materials_tiyin "
        "+ subtotal_edge_banding_tiyin - discount_tiyin)",
    )
    op.drop_constraint("fk_orders_surcharge_applied_by_user_id", "orders", type_="foreignkey")
    op.drop_column("orders", "surcharge_applied_by_user_id")
    op.drop_column("orders", "surcharge_reason")
    op.drop_column("orders", "surcharge_tiyin")
