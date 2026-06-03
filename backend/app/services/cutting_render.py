"""SVG and PDF rendering for immutable cutting results."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.schemas.cutting import CuttingPanelResponse, CuttingResultResponse


def render_cutting_svg(result: CuttingResultResponse) -> str:
    panels = result.panels
    if not panels:
        return _svg_document(400, 120, ['<text x="20" y="60">No panels</text>'])

    max_width = max(_panel_length(result, panel) for panel in panels)
    total_height = sum(_panel_width(result, panel) + 72 for panel in panels) + 24
    body: list[str] = []
    y_offset = 28
    for panel in panels:
        material = _material_snapshot(result, panel.material_id)
        panel_length = _panel_length(result, panel)
        panel_width = _panel_width(result, panel)
        title = (
            f"{material.get('manufacturer_name', '')} {material.get('name', panel.material_id)} "
            f"- panel {panel.panel_index}"
        ).strip()
        body.append(f'<text x="20" y="{y_offset - 8}" class="panel-title">{escape(title)}</text>')
        body.append(
            f'<rect x="20" y="{y_offset}" width="{panel_length}" height="{panel_width}" '
            'class="panel" />'
        )
        for placement in panel.placements:
            svg_y = y_offset + panel_width - placement.y_mm - placement.width_mm
            label = f"{placement.part_ref} #{placement.part_quantity_index}"
            if placement.rotated:
                label += " R"
            body.append(
                f'<rect x="{20 + placement.x_mm}" y="{svg_y}" '
                f'width="{placement.length_mm}" height="{placement.width_mm}" '
                'class="placement" />'
            )
            body.append(
                f'<text x="{24 + placement.x_mm}" y="{svg_y + 16}" '
                f'class="placement-label">{escape(label)}</text>'
            )
        y_offset += panel_width + 72
    return _svg_document(max_width + 48, total_height, body)


def render_cutting_pdf(result: CuttingResultResponse) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    for panel in result.panels:
        material = _material_snapshot(result, panel.material_id)
        panel_length = _panel_length(result, panel)
        panel_width = _panel_width(result, panel)
        title = (
            f"{material.get('manufacturer_name', '')} {material.get('name', panel.material_id)} "
            f"- panel {panel.panel_index}"
        ).strip()
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(18 * mm, page_height - 18 * mm, title)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(
            18 * mm,
            page_height - 24 * mm,
            f"{result.algorithm_name} {result.algorithm_version} - "
            f"waste {float(result.waste_percentage) * 100:.2f}%",
        )

        max_draw_width = page_width - 36 * mm
        max_draw_height = page_height - 58 * mm
        scale = min(max_draw_width / panel_length, max_draw_height / panel_width)
        origin_x = 18 * mm
        origin_y = 22 * mm
        draw_width = panel_length * scale
        draw_height = panel_width * scale

        pdf.rect(origin_x, origin_y, draw_width, draw_height)
        pdf.setFont("Helvetica", 7)
        for placement in panel.placements:
            x = origin_x + placement.x_mm * scale
            y = origin_y + (panel_width - placement.y_mm - placement.width_mm) * scale
            width = placement.length_mm * scale
            height = placement.width_mm * scale
            pdf.rect(x, y, width, height)
            label = f"{placement.part_ref} #{placement.part_quantity_index}"
            if placement.rotated:
                label += " R"
            pdf.drawString(x + 2, y + max(8, height - 9), label[:36])
        pdf.showPage()

    if not result.panels:
        pdf.setFont("Helvetica", 12)
        pdf.drawString(18 * mm, page_height - 18 * mm, "No panels")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _svg_document(width: int, height: int, body: list[str]) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
            "<style>"
            ".panel{fill:#fff;stroke:#334155;stroke-width:2}"
            ".placement{fill:#dbeafe;stroke:#2563eb;stroke-width:1}"
            ".panel-title{font:14px sans-serif;fill:#0f172a}"
            ".placement-label{font:12px sans-serif;fill:#0f172a}"
            "</style>",
            *body,
            "</svg>",
        ]
    )


def _material_snapshot(result: CuttingResultResponse, material_id: object) -> dict[str, object]:
    return result.material_snapshots.get(str(material_id), {})


def _panel_length(result: CuttingResultResponse, panel: CuttingPanelResponse) -> int:
    snapshot = _material_snapshot(result, panel.material_id)
    return _int_snapshot(snapshot.get("panel_length_mm"), fallback=1000)


def _panel_width(result: CuttingResultResponse, panel: CuttingPanelResponse) -> int:
    snapshot = _material_snapshot(result, panel.material_id)
    return _int_snapshot(snapshot.get("panel_width_mm"), fallback=700)


def _int_snapshot(value: object, *, fallback: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return fallback
