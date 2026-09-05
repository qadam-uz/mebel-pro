"""Akt sverka document layout: the sign convention and page composition.

The money hazard here is that the supplier and client sides invert the same
stored sign, so a payment must land in the *decreasing* column on both — read
the wrong way round, the document tells a counterparty they owe money they have
already paid.
"""

import uuid
from datetime import UTC, date, datetime

from app.modules.finance import statement_pdf
from app.modules.finance.schemas import DebtStatementResponse, DebtStatementRow

WORKSHOP = "Mebel Master"


def _row(
    kind: str, amount_tiyin: int, balance_after_tiyin: int, **extra: object
) -> DebtStatementRow:
    return DebtStatementRow(
        kind=kind,
        on=date(2026, 6, 15),
        at=datetime(2026, 6, 15, 10, 0, tzinfo=UTC),
        reference_id=uuid.uuid4(),
        amount_tiyin=amount_tiyin,
        balance_after_tiyin=balance_after_tiyin,
        **extra,  # type: ignore[arg-type]
    )


def _statement(rows: list[DebtStatementRow], **overrides: object) -> DebtStatementResponse:
    payload: dict[str, object] = {
        "counterparty_id": uuid.uuid4(),
        "name": "Panel Trade MChJ",
        "phone": "+998712300010",
        "workshop_name": WORKSHOP,
        "workshop_phone": "+998712001212",
        "date_from": date(2026, 6, 1),
        "date_to": date(2026, 6, 30),
        "opening_balance_tiyin": 0,
        "period_increase_tiyin": sum(r.amount_tiyin for r in rows if r.amount_tiyin > 0),
        "period_decrease_tiyin": sum(-r.amount_tiyin for r in rows if r.amount_tiyin < 0),
        "closing_balance_tiyin": rows[-1].balance_after_tiyin if rows else 0,
        "current_balance_tiyin": rows[-1].balance_after_tiyin if rows else 0,
        "rows": rows,
    }
    payload.update(overrides)
    return DebtStatementResponse(**payload)  # type: ignore[arg-type]


def test_a_payment_reduces_the_debt_column_on_both_sides() -> None:
    # Supplier side: a delivery grows our debt, our payment shrinks it.
    supplier = _statement(
        [
            _row("delivery", -10_000_000, -10_000_000, invoice_no="K-0001", line_count=1),
            _row("payment", 4_000_000, -6_000_000),
        ]
    )
    laid_out = statement_pdf._layout_rows(supplier, statement_pdf._side("suppliers"))
    delivery, payment = laid_out[1], laid_out[2]
    assert (delivery.debit, delivery.credit) == ("100 000", "")
    assert (payment.debit, payment.credit) == ("", "40 000")

    # Client side: an order grows their debt, their payment shrinks it — the
    # stored sign is the mirror image, the column is the same one.
    client = _statement(
        [
            _row("order", 10_000_000, 10_000_000, order_number="482917"),
            _row("payment", -4_000_000, 6_000_000),
        ]
    )
    laid_out = statement_pdf._layout_rows(client, statement_pdf._side("clients"))
    order, client_payment = laid_out[1], laid_out[2]
    assert (order.debit, order.credit) == ("100 000", "")
    assert (client_payment.debit, client_payment.credit) == ("", "40 000")


def test_period_turnover_maps_onto_each_sides_columns() -> None:
    statement = _statement(
        [
            _row("delivery", -10_000_000, -10_000_000),
            _row("payment", 4_000_000, -6_000_000),
        ]
    )
    assert statement_pdf._turnover(statement, statement_pdf._side("suppliers")) == (
        10_000_000,
        4_000_000,
    )
    assert statement_pdf._turnover(statement, statement_pdf._side("clients")) == (
        4_000_000,
        10_000_000,
    )


def test_direction_word_appears_only_where_the_balance_flips() -> None:
    statement = _statement(
        [
            _row("order", 5_000_000, 5_000_000),
            _row("order", 1_000_000, 6_000_000),
            _row("payment", -9_000_000, -3_000_000),
            _row("adjustment", -1_000_000, -4_000_000),
        ]
    )
    rows = statement_pdf._layout_rows(statement, statement_pdf._side("clients"))
    # Opening (zero, no word), first flip to "they owe", then to "we owe".
    assert [row.direction for row in rows] == ["", "bizga qarzi", "", "qarzimiz", ""]


def test_opening_row_renders_without_a_date_filter() -> None:
    statement = _statement(
        [_row("order", 5_000_000, 5_000_000)],
        date_from=None,
        date_to=None,
        opening_balance_tiyin=0,
    )
    rows = statement_pdf._layout_rows(statement, statement_pdf._side("clients"))
    assert rows[0].label_lines == ["Boshlang'ich qoldiq"]
    assert rows[0].date_text == "—"


def test_totals_and_signature_block_never_split_across_pages() -> None:
    long_statement = _statement([_row("order", 1_000, 1_000 * (index + 1)) for index in range(120)])
    rows = statement_pdf._layout_rows(long_statement, statement_pdf._side("clients"))
    pages = statement_pdf._paginate(rows)
    assert len(pages) > 1
    assert [page.tail for page in pages] == [False] * (len(pages) - 1) + [True]
    assert sum(len(page.rows) for page in pages) == len(rows)


def test_renders_a_pdf_for_a_hundred_row_statement() -> None:
    statement = _statement([_row("order", 1_000, 1_000 * (index + 1)) for index in range(120)])
    document = statement_pdf.render_statement_pdf(
        statement,
        statement_pdf.StatementPdfContext(side="clients"),
    )
    assert document.startswith(b"%PDF-")
    assert len(document) > 2_000
