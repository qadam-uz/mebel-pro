"""Akt sverka as a printable document.

This is the one screen whose output leaves the building: two companies read the
same sheet and sign it. So the PDF states everything a signature needs — both
parties, the period, the opening balance, every movement, the turnover and the
closing balance — and carries a signature block, a repeated table header and
page numbers.

Copy parity: the row labels and column wording mirror
web/src/shared/views/WorkshopFinanceDebtsView.vue and
web/src/shared/app/debtStatement.ts one-for-one. The sign convention itself is
derived in exactly one place per side (`_side`), never inline.
"""

# ruff: noqa: RUF001 -- document copy is Uzbek: U+02BB apostrophes, U+2212 minus.

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import BytesIO
from typing import Literal, NamedTuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.core.pdf import FONT_BOLD, FONT_REGULAR, register_pdf_fonts
from app.modules.finance.schemas import DebtStatementResponse, DebtStatementRow

StatementSide = Literal["suppliers", "clients"]

_PAGE_W = float(A4[0])
_PAGE_H = float(A4[1])
_MARGIN = float(14 * mm)
_CONTENT_W = _PAGE_W - 2 * _MARGIN
_INK = 0.08
_MUTED = 0.42
_HAIRLINE = 0.72
_LINE_H = 12.0
_ROW_PAD = 4.0
_FOOTER_H = 22.0
_SIGN_BLOCK_H = 104.0
_COL_W = (58.0, 197.0, 82.0, 82.0, _CONTENT_W - 419.0)
_FONT_ROW = 8.0
_FONT_HEAD = 7.5


class _Side(NamedTuple):
    """How one side of the ledger words the same stored sign convention."""

    counterparty_label: str
    debit_header: str
    credit_header: str
    # Multiplied into the stored amount, this turns "positive = they owe us"
    # into "positive = the debit column of this side's document".
    debit_sign: int


class _Row(NamedTuple):
    date_text: str
    label_lines: list[str]
    debit: str
    credit: str
    balance: str
    direction: str
    bold: bool

    @property
    def height(self) -> float:
        return max(len(self.label_lines), 2 if self.direction else 1) * _LINE_H + _ROW_PAD


@dataclass(frozen=True)
class StatementPdfContext:
    side: StatementSide
    generated_at: datetime | None = None


def render_statement_pdf(
    statement: DebtStatementResponse,
    context: StatementPdfContext,
) -> bytes:
    """Render one akt sverka. Page count is known before drawing, so every page
    can print `Bet N / M` — which is why rows are laid out first."""

    register_pdf_fonts()
    side = _side(context.side)
    generated_at = context.generated_at or datetime.now(UTC)
    rows = _layout_rows(statement, side)
    pages = _paginate(rows)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Akt sverka — {statement.name}")
    pdf.setAuthor(statement.workshop_name)
    total_pages = len(pages)
    for index, page in enumerate(pages):
        y = _draw_page_head(pdf, statement, side, first=index == 0)
        y = _draw_table_head(pdf, side, y)
        for row in page.rows:
            y = _draw_row(pdf, row, y)
        if page.tail:
            y = _draw_totals(pdf, statement, side, y)
            _draw_signatures(pdf, statement, y - 18)
        _draw_footer(pdf, index + 1, total_pages, generated_at)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _side(side: StatementSide) -> _Side:
    if side == "suppliers":
        # We owe the supplier, so a delivery (stored negative) is the debit.
        return _Side("Ta'minotchi", "Qarzimiz +", "Qarzimiz −", -1)
    return _Side("Mijoz", "Qarzi +", "Qarzi −", 1)


class _Page(NamedTuple):
    rows: list[_Row]
    tail: bool


def _paginate(rows: list[_Row]) -> list[_Page]:
    """Split rows into pages, keeping the totals and signature block together.

    The tail never starts a page it cannot finish: a signature block orphaned
    from its own closing balance is a document nobody can sign.
    """

    pages: list[_Page] = []
    remaining = list(rows)
    first = True
    while True:
        available = _table_top(first) - _TABLE_BOTTOM
        page_rows: list[_Row] = []
        used = _TABLE_HEAD_H
        while remaining and used + remaining[0].height <= available:
            row = remaining.pop(0)
            used += row.height
            page_rows.append(row)
        tail_fits = not remaining and used + _TOTALS_H + _SIGN_BLOCK_H <= available
        pages.append(_Page(page_rows, tail_fits))
        first = False
        if not remaining and tail_fits:
            return pages
        if not remaining:
            pages.append(_Page([], True))
            return pages


_TABLE_HEAD_H = 20.0
_TOTALS_H = 2 * (_LINE_H + _ROW_PAD) + 8.0
_HEAD_H_FIRST = 118.0
_HEAD_H_CONT = 34.0
_TABLE_BOTTOM = _MARGIN + _FOOTER_H


def _table_top(first: bool) -> float:
    return _PAGE_H - _MARGIN - (_HEAD_H_FIRST if first else _HEAD_H_CONT)


def _layout_rows(statement: DebtStatementResponse, side: _Side) -> list[_Row]:
    rows: list[_Row] = []
    # The opening balance always opens the document — with no period selected
    # it is the all-time opening, which is exactly zero and says so.
    opening_direction = _direction(statement.opening_balance_tiyin)
    rows.append(
        _Row(
            date_text=_format_date(statement.date_from) if statement.date_from else "—",
            label_lines=["Boshlang'ich qoldiq"],
            debit="",
            credit="",
            balance=_money(abs(statement.opening_balance_tiyin)),
            direction=opening_direction,
            bold=True,
        )
    )
    previous = opening_direction
    for row in statement.rows:
        signed = row.amount_tiyin * side.debit_sign
        direction = _direction(row.balance_after_tiyin)
        rows.append(
            _Row(
                date_text=_format_date(row.on),
                label_lines=_wrap(_row_label(row), _COL_W[1] - 8),
                debit=_money(signed) if signed > 0 else "",
                credit=_money(-signed) if signed < 0 else "",
                balance=_money(abs(row.balance_after_tiyin)),
                # Direction is information only where it changes; repeated on
                # every line it is the noisiest thing on the page.
                direction=direction if direction != previous else "",
                bold=False,
            )
        )
        previous = direction
    return rows


def _row_label(row: DebtStatementRow) -> str:
    if row.kind == "delivery":
        parts = [f"Kirim · {row.invoice_no or 'faktura'}"]
        if row.line_count is not None:
            parts.append(f"{row.line_count} pozitsiya")
        if row.discount_tiyin:
            parts.append(f"chegirma {_money(row.discount_tiyin)}")
        if row.surcharge_tiyin:
            parts.append(f"ustama {_money(row.surcharge_tiyin)}")
        return " · ".join(parts)
    if row.kind == "payment":
        if row.order_number:
            return f"To'lov · {row.order_number}"
        detail = row.note or "to'lov"
        return f"Xarajat · {detail}"
    if row.kind == "order":
        return f"Buyurtma {row.order_number or ''}".strip()
    return f"Qarz tuzatish · {row.note or ''}".strip()


def _draw_page_head(
    pdf: canvas.Canvas,
    statement: DebtStatementResponse,
    side: _Side,
    *,
    first: bool,
) -> float:
    y = _PAGE_H - _MARGIN
    if not first:
        _text(pdf, _MARGIN, y - 14, f"Akt sverka (davomi) · {statement.name}", 10, bold=True)
        return y - _HEAD_H_CONT
    _text(pdf, _MARGIN, y - 16, "AKT SVERKA", 16, bold=True)
    _text(pdf, _MARGIN, y - 31, _period_text(statement), 9, gray=_MUTED)
    box_top = y - 40
    box_h = 62.0
    pdf.setStrokeGray(_HAIRLINE)
    pdf.setLineWidth(0.4)
    pdf.rect(_MARGIN, box_top - box_h, _CONTENT_W, box_h)
    pdf.line(_MARGIN + _CONTENT_W / 2, box_top, _MARGIN + _CONTENT_W / 2, box_top - box_h)
    _party(pdf, _MARGIN + 8, box_top, "Ustaxona", statement.workshop_name, statement.workshop_phone)
    _party(
        pdf,
        _MARGIN + _CONTENT_W / 2 + 8,
        box_top,
        side.counterparty_label,
        statement.name,
        statement.phone,
    )
    return box_top - box_h - 16


def _party(
    pdf: canvas.Canvas, x: float, top: float, role: str, name: str, phone: str | None
) -> None:
    _text(pdf, x, top - 14, role, 7.5, gray=_MUTED)
    for index, line in enumerate(_wrap(name, _CONTENT_W / 2 - 16, size=10, bold=True)[:2]):
        _text(pdf, x, top - 28 - index * 12, line, 10, bold=True)
    _text(pdf, x, top - 52, phone or "telefon ko'rsatilmagan", 8.5, gray=_MUTED)


def _period_text(statement: DebtStatementResponse) -> str:
    if statement.date_from and statement.date_to:
        return f"Davr: {_format_date(statement.date_from)} — {_format_date(statement.date_to)}"
    if statement.date_from:
        return f"Davr: {_format_date(statement.date_from)} dan"
    if statement.date_to:
        return f"Davr: {_format_date(statement.date_to)} gacha"
    return "Davr: butun tarix"


def _draw_table_head(pdf: canvas.Canvas, side: _Side, y: float) -> float:
    headers = ["Sana", "Hujjat", side.debit_header, side.credit_header, "Qoldiq"]
    aligns = ["left", "left", "right", "right", "right"]
    pdf.setFillGray(0.93)
    pdf.rect(_MARGIN, y - _TABLE_HEAD_H, _CONTENT_W, _TABLE_HEAD_H, stroke=0, fill=1)
    x = _MARGIN
    for header, width, align in zip(headers, _COL_W, aligns, strict=True):
        _cell(pdf, x, y - 13, width, header, _FONT_HEAD, align, bold=True, gray=_MUTED)
        x += width
    _rule(pdf, y - _TABLE_HEAD_H, dark=True)
    return y - _TABLE_HEAD_H


def _draw_row(pdf: canvas.Canvas, row: _Row, y: float) -> float:
    height = row.height
    baseline = y - _LINE_H
    x = _MARGIN
    _cell(pdf, x, baseline, _COL_W[0], row.date_text, _FONT_ROW, "left", gray=_MUTED)
    x += _COL_W[0]
    for index, line in enumerate(row.label_lines):
        _cell(pdf, x, baseline - index * _LINE_H, _COL_W[1], line, _FONT_ROW, "left", bold=row.bold)
    x += _COL_W[1]
    _cell(pdf, x, baseline, _COL_W[2], row.debit, _FONT_ROW, "right")
    x += _COL_W[2]
    _cell(pdf, x, baseline, _COL_W[3], row.credit, _FONT_ROW, "right")
    x += _COL_W[3]
    _cell(pdf, x, baseline, _COL_W[4], row.balance, _FONT_ROW, "right", bold=True)
    if row.direction:
        _cell(
            pdf,
            x,
            baseline - _LINE_H,
            _COL_W[4],
            row.direction,
            6.8,
            "right",
            gray=_MUTED,
        )
    _rule(pdf, y - height)
    return y - height


def _draw_totals(
    pdf: canvas.Canvas,
    statement: DebtStatementResponse,
    side: _Side,
    y: float,
) -> float:
    debit, credit = _turnover(statement, side)
    height = _LINE_H + _ROW_PAD
    baseline = y - _LINE_H
    x = _MARGIN + _COL_W[0]
    _cell(pdf, x, baseline, _COL_W[1], "Davr aylanmasi", _FONT_ROW, "left", bold=True)
    x += _COL_W[1]
    _cell(pdf, x, baseline, _COL_W[2], _money(debit), _FONT_ROW, "right", bold=True)
    x += _COL_W[2]
    _cell(pdf, x, baseline, _COL_W[3], _money(credit), _FONT_ROW, "right", bold=True)
    y -= height
    _rule(pdf, y, dark=True)

    closing = statement.closing_balance_tiyin
    direction = _direction(closing) or "qarz yo'q"
    baseline = y - _LINE_H - 2
    _cell(
        pdf,
        _MARGIN + _COL_W[0],
        baseline,
        _COL_W[1] + _COL_W[2] + _COL_W[3],
        "Yopilish qoldig'i",
        10,
        "left",
        bold=True,
    )
    _cell(
        pdf,
        _MARGIN + _CONTENT_W - _COL_W[4],
        baseline,
        _COL_W[4],
        _money(abs(closing)),
        10,
        "right",
        bold=True,
    )
    _cell(
        pdf,
        _MARGIN + _CONTENT_W - _COL_W[4],
        baseline - 11,
        _COL_W[4],
        direction,
        7,
        "right",
        gray=_MUTED,
    )
    return y - _TOTALS_H


def _turnover(statement: DebtStatementResponse, side: _Side) -> tuple[int, int]:
    """Period turnover mapped onto this side's two columns."""

    if side.debit_sign < 0:
        return statement.period_decrease_tiyin, statement.period_increase_tiyin
    return statement.period_increase_tiyin, statement.period_decrease_tiyin


def _draw_signatures(pdf: canvas.Canvas, statement: DebtStatementResponse, y: float) -> None:
    _text(
        pdf,
        _MARGIN,
        y - 12,
        "Yuqoridagi hisob-kitob tomonlar tomonidan tasdiqlandi:",
        8.5,
        gray=_MUTED,
    )
    top = y - 34
    half = _CONTENT_W / 2
    for index, (role, name) in enumerate(
        (
            ("Ustaxona nomidan", statement.workshop_name),
            ("Kontragent nomidan", statement.name),
        )
    ):
        x = _MARGIN + index * half
        _text(pdf, x, top, role, 8.5, bold=True)
        _text(pdf, x, top - 12, _clip(name, half - 20, 8), 8, gray=_MUTED)
        for line_index, label in enumerate(("F.I.Sh.", "Imzo", "Sana")):
            line_y = top - 32 - line_index * 18
            _text(pdf, x, line_y, label, 7.5, gray=_MUTED)
            pdf.setStrokeGray(_HAIRLINE)
            pdf.setLineWidth(0.4)
            pdf.line(x + 34, line_y - 1, x + half - 20, line_y - 1)


def _draw_footer(pdf: canvas.Canvas, page: int, total: int, generated_at: datetime) -> None:
    y = _MARGIN + 6
    _rule(pdf, y + 12)
    stamp = generated_at.strftime("%d.%m.%Y %H:%M")
    _text(pdf, _MARGIN, y, f"Mebel Pro · {stamp}", 7, gray=_MUTED)
    _cell(pdf, _MARGIN, y, _CONTENT_W, f"Bet {page} / {total}", 7, "right", gray=_MUTED)


def _rule(pdf: canvas.Canvas, y: float, *, dark: bool = False) -> None:
    pdf.setStrokeGray(0.55 if dark else _HAIRLINE)
    pdf.setLineWidth(0.4)
    pdf.line(_MARGIN, y, _MARGIN + _CONTENT_W, y)


def _text(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    size: float,
    *,
    bold: bool = False,
    gray: float = _INK,
) -> None:
    pdf.setFillGray(gray)
    pdf.setFont(FONT_BOLD if bold else FONT_REGULAR, size)
    pdf.drawString(x, y, text)


def _cell(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    text: str,
    size: float,
    align: str,
    *,
    bold: bool = False,
    gray: float = _INK,
) -> None:
    if not text:
        return
    pdf.setFillGray(gray)
    pdf.setFont(FONT_BOLD if bold else FONT_REGULAR, size)
    if align == "right":
        pdf.drawRightString(x + width - 4, y, text)
    else:
        pdf.drawString(x + 4, y, text)


def _wrap(text: str, width: float, *, size: float = _FONT_ROW, bold: bool = False) -> list[str]:
    """Greedy two-line wrap; a third line would push the row past its neighbours."""

    register_pdf_fonts()
    font = FONT_BOLD if bold else FONT_REGULAR
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if current and stringWidth(candidate, font, size) > width:
            lines.append(current)
            current = word
            if len(lines) == 2:
                break
        else:
            current = candidate
    if len(lines) < 2 and current:
        lines.append(current)
    if not lines:
        return [""]
    return [_clip(line, width, size, bold=bold) for line in lines[:2]]


def _clip(text: str, width: float, size: float, *, bold: bool = False) -> str:
    register_pdf_fonts()
    font = FONT_BOLD if bold else FONT_REGULAR
    if stringWidth(text, font, size) <= width:
        return text
    clipped = text
    while clipped and stringWidth(f"{clipped}…", font, size) > width:
        clipped = clipped[:-1]
    return f"{clipped}…"


def _direction(balance: int) -> str:
    if balance > 0:
        return "bizga qarzi"
    if balance < 0:
        return "qarzimiz"
    return ""


def _money(tiyin: int) -> str:
    """So'm with space-grouped thousands. The unit is stated once, in the header."""

    som = round(tiyin / 100)
    return f"{som:,}".replace(",", " ")


def _format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")
