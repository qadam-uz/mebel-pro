"""Canonical material / edge-band display-label formatting.

One shape, used everywhere a material or edge band is shown to a human — the
cutting PDF, sales order summaries, workshop production views, and (by
pass-through) the finance ledger:

- panel: `{tur label} {manufacturer} {kod or nomi}` ·
  `{nomi, only if not already implied by the base}` ·
  `{uzunlik}×{eni}×{qalinlik} mm`
- kromka: `{manufacturer} {kod or nomi}` · `{nomi, if not implied}` ·
  `{qalinlik}×{kromka eni} mm` (no length×width — tapes don't have those)

Both are pure functions over a "material snapshot" `dict[str, Any]` — the JSON
shape frozen onto cutting results and order items. No ORM, no session, no
module-specific types, so any module may import this freely per
backend/AGENTS.md's module-boundary rule instead of reaching into another
module's private `service.py` / `rendering.py`.

**Two snapshot vocabularies are read, deliberately.** The catalog reshape
renamed the snapshot keys (`type`->`tur`, `decor_code`->`kod`, `color`->`nomi`,
`thickness_mm`->`qalinlik_mm`, `panel_length_mm`->`uzunlik_mm`,
`panel_width_mm`->`eni_mm`, `edge_width_mm`->`kromka_eni_mm`, and `name` was
dropped), but `order_items.material_snapshot` and
`cutting_results.material_snapshots` are frozen history and are NOT rewritten by
the migration — that is exactly what protects old orders. So the database holds
both vocabularies forever, and these two functions accept both: new key first,
legacy key as fallback. Dropping the legacy reads would silently render every
pre-reshape order, production card and cutting PDF as an 8-character id
fragment, with no error anywhere.

Current keys: `manufacturer_name`, `tur`, `kod`, `nomi`, `qalinlik_mm`,
`uzunlik_mm`, `eni_mm`, `kromka_eni_mm`, `tolali` (carried for the optimizer,
never printed).
Legacy keys still honoured: `type`, `decor_code`, `name`, `color`,
`thickness_mm`, `panel_length_mm`, `panel_width_mm`, `edge_width_mm`.
"""

# ruff: noqa: RUF001, RUF002, RUF003 -- labels and docstrings reuse the printed/web
# display format's multiplication sign for dimensions.

from __future__ import annotations

from typing import Any

# Keyed by both vocabularies: the new `dekor_type` values and the legacy
# `panel_material_type` ones, so a historical snapshot renders identically.
_PANEL_TYPE_LABELS = {
    # dekor_type
    "ldsp": "LDSP",
    "dsp": "LDSP",
    "mdf": "MDF",
    "fanera": "Fanera",
    "yogoch": "Yog'och",
    "boshqa": "List",
    "kromka": "Kromka",
    # legacy panel_material_type values not reused above
    "plywood": "Fanera",
    "natural_wood": "Yog'och",
    "other": "List",
}


def material_label(snapshot: dict[str, Any], material_id: object) -> str:
    """Canonical panel label, e.g. `MDF Egger H1334 ST9 · Sanoma · 2750×1830×18 mm`.

    Falls back to the first 8 characters of `material_id` when the snapshot
    carries no identity at all (empty/missing snapshot).
    """
    raw_type = _snapshot_text(snapshot, "tur", "type")
    type_label = _PANEL_TYPE_LABELS.get(raw_type, raw_type)
    manufacturer = _snapshot_text(snapshot, "manufacturer_name")
    nomi = _snapshot_text(snapshot, "nomi", "color")
    identity = _identity(snapshot, nomi)
    thickness = _snapshot_text(snapshot, "qalinlik_mm", "thickness_mm")
    length = _int_snapshot(_snapshot_value(snapshot, "uzunlik_mm", "panel_length_mm"), fallback=0)
    width = _int_snapshot(_snapshot_value(snapshot, "eni_mm", "panel_width_mm"), fallback=0)

    base = " ".join(part for part in [type_label, manufacturer, identity] if part)
    if not base:
        return str(material_id)[:8]

    details: list[str] = []
    if nomi and nomi.lower() not in base.lower():
        details.append(nomi)
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
    nomi = _snapshot_text(snapshot, "nomi", "color")
    identity = _identity(snapshot, nomi)
    thickness = _snapshot_text(snapshot, "qalinlik_mm", "thickness_mm")
    width = _int_snapshot(_snapshot_value(snapshot, "kromka_eni_mm", "edge_width_mm"), fallback=0)

    base = " ".join(part for part in [manufacturer, identity] if part) or str(material_id)[:8]
    # A dekor without a `kod` puts `nomi` in the base, so the detail slot must
    # suppress it the same way material_label does — otherwise the label reads
    # "Egger Sonoma eman · Sonoma eman · 2×36 mm".
    detail = nomi if nomi and nomi.lower() not in base.lower() else ""
    if thickness and width > 0:
        size = f"{_format_mm(thickness)}×{width} mm"
    elif thickness:
        size = f"{_format_mm(thickness)} mm"
    else:
        size = ""
    return " · ".join(part for part in [base, detail, size] if part)


def _identity(snapshot: dict[str, Any], nomi: str) -> str:
    """The name-slot of the base: decor code first, then whatever names exist.

    `name` is the legacy server-generated column, gone from new snapshots; it is
    consulted before `nomi` so a historical snapshot keeps rendering the string
    it always did.
    """
    return _snapshot_text(snapshot, "kod", "decor_code") or _snapshot_text(snapshot, "name") or nomi


def _snapshot_value(snapshot: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = snapshot.get(key)
        if value is not None:
            return value
    return None


def _snapshot_text(snapshot: dict[str, Any], *keys: str) -> str:
    value = _snapshot_value(snapshot, *keys)
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
