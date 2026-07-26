"""group stock-ins under a supplier invoice

Creates `supplier_invoices`, links stock-ins and expenses to it, and backfills
every existing stock-in as its own one-line invoice so that no supplier balance
moves on deploy: with `discount = surcharge = 0`, the invoice total equals the
line's own total, and the payable fold — which switches from summing
`stock_transactions.total_price_tiyin` to summing `supplier_invoices.total_tiyin`
— lands on exactly the same number.

Arrivals with no recorded price coalesce to 0 (they contribute 0 today and must
keep contributing 0); arrivals with no supplier keep none and stay outside every
supplier balance, exactly as they behave now.

Revision ID: 1a7b3c9d2e40
Revises: 37ee5335706c
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1a7b3c9d2e40"
down_revision: str | None = "a1e5c0b9d742"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# One invoice per existing stock-in, numbered per workshop in arrival order, and
# the transaction pointed at it — in one statement so the two can't diverge.
BACKFILL = """
WITH src AS (
    SELECT
        st.id AS transaction_id,
        gen_random_uuid() AS invoice_id,
        b.workshop_id AS workshop_id,
        si.branch_id AS branch_id,
        st.supplier_id AS supplier_id,
        st.created_at AS created_at,
        COALESCE(st.total_price_tiyin, 0) AS total_tiyin,
        COALESCE(st.actor_user_id, fallback.id) AS recorded_by_user_id,
        row_number() OVER (
            PARTITION BY b.workshop_id ORDER BY st.created_at, st.id
        ) AS seq
    FROM stock_transactions st
    JOIN stock_items si ON si.id = st.stock_item_id
    JOIN branches b ON b.id = si.branch_id
    LEFT JOIN LATERAL (
        SELECT wu.id
        FROM workshop_users wu
        WHERE wu.workshop_id = b.workshop_id
        ORDER BY wu.is_owner DESC, wu.created_at
        LIMIT 1
    ) fallback ON TRUE
    WHERE st.type = 'stock_in'
), inserted AS (
    INSERT INTO supplier_invoices (
        id, workshop_id, branch_id, supplier_id, invoice_no, invoice_date,
        subtotal_tiyin, discount_tiyin, surcharge_tiyin, total_tiyin, note,
        recorded_by_user_id, created_at, updated_at
    )
    SELECT
        src.invoice_id, src.workshop_id, src.branch_id, src.supplier_id,
        'K-' || lpad(src.seq::text, 4, '0'), (src.created_at AT TIME ZONE 'UTC')::date,
        src.total_tiyin, 0, 0, src.total_tiyin, NULL,
        src.recorded_by_user_id, src.created_at, src.created_at
    FROM src
    RETURNING id
)
UPDATE stock_transactions st
SET invoice_id = src.invoice_id
FROM src
WHERE st.id = src.transaction_id
"""


def upgrade() -> None:
    op.create_table(
        "supplier_invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workshop_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_no", sa.String(), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("subtotal_tiyin", sa.BigInteger(), nullable=False),
        sa.Column("discount_tiyin", sa.BigInteger(), nullable=False),
        sa.Column("surcharge_tiyin", sa.BigInteger(), nullable=False),
        sa.Column("total_tiyin", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("subtotal_tiyin >= 0", name="ck_supplier_invoices_subtotal_nonnegative"),
        sa.CheckConstraint("discount_tiyin >= 0", name="ck_supplier_invoices_discount_nonnegative"),
        sa.CheckConstraint(
            "surcharge_tiyin >= 0", name="ck_supplier_invoices_surcharge_nonnegative"
        ),
        sa.CheckConstraint(
            "discount_tiyin <= subtotal_tiyin",
            name="ck_supplier_invoices_discount_not_above_subtotal",
        ),
        sa.CheckConstraint(
            "total_tiyin = subtotal_tiyin - discount_tiyin + surcharge_tiyin",
            name="ck_supplier_invoices_total_formula",
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["workshop_users.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workshop_id", "invoice_no", name="uq_supplier_invoices_workshop_no"),
    )
    op.add_column("stock_transactions", sa.Column("invoice_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_stock_transactions_invoice_id",
        "stock_transactions",
        "supplier_invoices",
        ["invoice_id"],
        ["id"],
    )
    op.add_column("expenses", sa.Column("invoice_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_expenses_invoice_id",
        "expenses",
        "supplier_invoices",
        ["invoice_id"],
        ["id"],
    )

    op.execute(BACKFILL)

    # Only a stock-in can carry an invoice — the same shape as the existing
    # price constraint. Added after the backfill so it validates real data.
    op.create_check_constraint(
        "ck_stock_transactions_invoice_stock_in_only",
        "stock_transactions",
        "invoice_id IS NULL OR type = 'stock_in'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_stock_transactions_invoice_stock_in_only", "stock_transactions", type_="check"
    )
    op.drop_constraint("fk_expenses_invoice_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "invoice_id")
    op.drop_constraint("fk_stock_transactions_invoice_id", "stock_transactions", type_="foreignkey")
    op.drop_column("stock_transactions", "invoice_id")
    op.drop_table("supplier_invoices")
