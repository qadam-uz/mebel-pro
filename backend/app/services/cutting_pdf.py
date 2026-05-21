"""Print-ready cutting-map PDF — one page per sheet, for the saw operator.

Header: material + sheet index + waste. Footer: the algorithm stamp. Pure
rendering off persisted rows; no DB access. Built with reportlab.
"""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.cutting import CuttingPlacement, CuttingResult, CuttingSheet


def _material_label(material_id: str, materials: dict[str, str]) -> str:
    return materials.get(material_id, material_id)


def render_cutting_pdf(
    result: CuttingResult,
    layout: list[tuple[CuttingSheet, list[CuttingPlacement]]],
    *,
    sheet_dims: dict[str, tuple[int, int]],
    material_labels: dict[str, str],
) -> bytes:
    """Render one A4-landscape page per sheet.

    ``sheet_dims`` maps material_id → (sheet_length_mm, sheet_width_mm).
    """
    buffer = io.BytesIO()
    page_w, page_h = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))

    margin = 18 * mm
    draw_w = page_w - 2 * margin
    draw_h = page_h - 2 * margin - 28 * mm  # leave room for header/footer

    stamp = f"{result.algorithm_name} v{result.algorithm_version}"

    if not layout:
        _draw_header(pdf, page_w, page_h, margin, "No sheets", 0, 0.0)
        _draw_footer(pdf, page_w, margin, stamp)
        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    for sheet, placements in layout:
        mid = str(sheet.material_id)
        sl, sw = sheet_dims.get(mid, (2800, 2070))
        label = _material_label(mid, material_labels)
        waste = float(result.waste_percentage)

        _draw_header(pdf, page_w, page_h, margin, label, sheet.sheet_index, waste)

        # scale the sheet (length along x, width along y) to fit the draw area
        scale = min(draw_w / sl, draw_h / sw)
        origin_x = margin
        origin_y = margin + 14 * mm

        # sheet outline
        pdf.setLineWidth(1)
        pdf.rect(origin_x, origin_y, sl * scale, sw * scale)

        pdf.setFont("Helvetica", 7)
        for p in placements:
            x = origin_x + p.x_mm * scale
            y = origin_y + p.y_mm * scale
            w = p.length_mm * scale
            h = p.width_mm * scale
            pdf.setLineWidth(0.5)
            pdf.rect(x, y, w, h, fill=0)
            text = f"{p.part_ref[:6]} #{p.part_quantity_index}"
            dims = f"{p.length_mm}x{p.width_mm}" + (" R" if p.rotated else "")
            pdf.drawString(x + 2, y + h - 9, text)
            pdf.drawString(x + 2, y + 2, dims)

        _draw_footer(pdf, page_w, margin, stamp)
        pdf.showPage()

    pdf.save()
    return buffer.getvalue()


def _draw_header(
    pdf: canvas.Canvas,
    page_w: float,
    page_h: float,
    margin: float,
    material: str,
    sheet_index: int,
    waste: float,
) -> None:
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, page_h - margin, f"{material}  ·  Sheet {sheet_index}")
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(page_w - margin, page_h - margin, f"Waste: {waste * 100:.1f}%")


def _draw_footer(pdf: canvas.Canvas, page_w: float, margin: float, stamp: str) -> None:
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(margin, margin - 8 * mm, f"Algorithm: {stamp}")
    pdf.drawRightString(page_w - margin, margin - 8 * mm, "Mebel Pro — cutting map")
