"""Canonical material / edge-band display-label formatting.

One shape, used everywhere a material or edge band is shown to a human — the
cutting PDF, sales order summaries, workshop production views, and (by
pass-through) the finance ledger:

- panel: `{panel type} {manufacturer} {decor code or name}` ·
  `{color, only if not already implied by the base}` ·
  `{length}×{width}×{thickness} mm`
- edge band: `{manufacturer} {decor code or name}` · `{color}` ·
  `{thickness}×{edge width} mm` (no length×width — edges don't have those)

Both are pure functions over a "material snapshot" `dict[str, Any]` — the
JSON shape frozen onto cutting results and order items
(`manufacturer_name`, `type`, `decor_code`, `name`, `color`, `thickness_mm`,
`panel_length_mm`, `panel_width_mm`, `edge_width_mm`). No ORM, no session, no
module-specific types, so any module may import this freely per
backend/AGENTS.md's module-boundary rule instead of reaching into another
module's private `service.py` / `rendering.py`.
"""

# ruff: noqa: RUF001, RUF002 -- labels and docstrings reuse the printed/web
# display format's multiplication sign for dimensions.

from __future__ import annotations

from typing import Any

_PANEL_TYPE_LABELS = {
    "dsp": "LDSP",
    "mdf": "MDF",
    "plywood": "Fanera",
    "natural_wood": "Yog'och",
    "other": "List",
}


def material_label(snapshot: dict[str, Any], material_id: object) -> str:
    """Canonical panel label, e.g. `MDF Egger H1334 ST9 · Sanoma · 2750×1830×18 mm`.

    Falls back to the first 8 characters of `material_id` when the snapshot
    carries no identity at all (empty/missing snapshot).
    """
    raw_type = _snapshot_text(snapshot, "type")
    type_label = _PANEL_TYPE_LABELS.get(raw_type, raw_type)
    manufacturer = _snapshot_text(snapshot, "manufacturer_name")
    decor = _snapshot_text(snapshot, "decor_code")
    name = _snapshot_text(snapshot, "name")
    color = _snapshot_text(snapshot, "color")
    thickness = _snapshot_text(snapshot, "thickness_mm")
    length = _int_snapshot(snapshot.get("panel_length_mm"), fallback=0)
    width = _int_snapshot(snapshot.get("panel_width_mm"), fallback=0)

    base = " ".join(part for part in [type_label, manufacturer, decor or name] if part)
    if not base:
        return str(material_id)[:8]

    details: list[str] = []
    if color and color.lower() not in base.lower():
        details.append(color)
    if length > 0 and width > 0:
        dims = f"{length}×{width}"
        if thickness:
            dims = f"{dims}×{_format_mm(thickness)}"
        details.append(f"{dims} mm")
    elif thickness:
        details.append(f"{_format_mm(thickness)} mm")
    return " · ".join([base, *details])


def edge_label(snapshot: dict[str, Any], material_id: object) -> str:
    """Canonical edge-band label, e.g. `Egger H1334 ST9 · Sanoma · 2×36 mm`.

    Falls back to the first 8 characters of `material_id` when the snapshot
    carries no identity at all (empty/missing snapshot).
    """
    manufacturer = _snapshot_text(snapshot, "manufacturer_name")
    decor = _snapshot_text(snapshot, "decor_code")
    name = _snapshot_text(snapshot, "name")
    color = _snapshot_text(snapshot, "color")
    thickness = _snapshot_text(snapshot, "thickness_mm")
    width = _int_snapshot(snapshot.get("edge_width_mm"), fallback=0)
    base = " ".join(part for part in [manufacturer, decor or name] if part) or str(material_id)[:8]
    if thickness and width > 0:
        size = f"{_format_mm(thickness)}×{width} mm"
    elif thickness:
        size = f"{_format_mm(thickness)} mm"
    else:
        size = ""
    return " · ".join(part for part in [base, color, size] if part)


def _snapshot_text(snapshot: dict[str, Any], key: str) -> str:
    value = snapshot.get(key)
    return value.strip() if isinstance(value, str) else ""


def _format_mm(value: object) -> str:
    text = str(value).strip()
    try:
        parsed = float(text)
    except ValueError:
        return text
    if parsed.is_integer():
        return str(int(parsed))
    return text.rstrip("0").rstrip(".")


def _int_snapshot(value: object, *, fallback: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return fallback
