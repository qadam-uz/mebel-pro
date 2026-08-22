"""Canonical material / edge-band display-label formatting.

One shape, used everywhere a material or edge band is shown to a human — the
cutting PDF, sales order summaries, workshop production views, and (by
pass-through) the finance ledger:

- panel: `{type label} {manufacturer} {code or name}` ·
  `{decor name, only if not already implied by the base}` ·
  `{length}×{width}×{thickness} mm` · `{"1 tomonlama", only when one-sided}`
- kromka: `{manufacturer} {code or name}` · `{decor name, if not implied}` ·
  `{thickness}×{tape width} mm` (no length×width — tapes don't have those)

Both are pure functions over a "material snapshot" `dict[str, Any]` — the JSON
shape frozen onto cutting results and order items. No ORM, no session, no
module-specific types, so any module may import this freely per
backend/AGENTS.md's module-boundary rule instead of reaching into another
module's private `service.py` / `rendering.py`.

**Three snapshot vocabularies are read, deliberately.** `order_items.
material_snapshot` and `cutting_results.material_snapshots` are frozen history
and are never rewritten by a migration — that is exactly what protects old
orders — so the database holds every vocabulary the app has ever written,
forever. Dropping an old read would silently render those rows as an
8-character id fragment, with no error anywhere.

| Slot            | 1. current English | 2. Uzbek (reshape era) | 3. pre-reshape English |
|-----------------|--------------------|------------------------|------------------------|
| substrate       | `type`             | `tur`                  | `type`                 |
| manufacturer    | `manufacturer_name`| `manufacturer_name`    | `manufacturer_name`    |
| decor code      | `code`             | `kod`                  | `decor_code`           |
| decor name      | `name`             | `nomi`                 | `color`                |
| thickness       | `thickness_mm`     | `qalinlik_mm`          | `thickness_mm`         |
| sheet length    | `length_mm`        | `uzunlik_mm`           | `panel_length_mm`      |
| sheet width     | `width_mm`         | `eni_mm`               | `panel_width_mm`       |
| tape width      | `tape_width_mm`    | `kromka_eni_mm`        | `edge_width_mm`        |
| finished faces  | `finished_sides`   | —                      | —                      |
| grain           | `has_grain`        | `tolali`               | —                      |

`type` and `thickness_mm` mean the same thing in columns 1 and 3, so they read
straight through. **Two keys collide and must not:**

- `code` (current: the decor code, e.g. `H1334 ST9`) is NOT the pre-reshape
  `decor_code`'s only home, but they mean the same thing and are read as one
  slot, newest first.
- `name` means two different things. Current snapshots put the *decor name*
  there (`Sonoma eman`); pre-reshape snapshots put the whole *generated
  material name* there (`LDSP Egger H1334 Sonoma`). So the decor-name slot reads
  `nomi` and `color` BEFORE `name` — those two never occur in a current
  snapshot, so a current one still resolves to `name`, while a pre-reshape one
  keeps resolving to `color` and leaves its generated `name` to the identity
  slot, which is where it always rendered.

`has_grain` / `tolali` are carried for the optimizer and never printed.
"""

# ruff: noqa: RUF001, RUF002, RUF003 -- labels and docstrings reuse the printed/web
# display format's multiplication sign for dimensions.

from __future__ import annotations

from typing import Any

# Keyed by both vocabularies: the `decor_type` values and the legacy
# `panel_material_type` ones, so a historical snapshot renders identically.
_PANEL_TYPE_LABELS = {
    # decor_type
    "ldsp": "LDSP",
    # DSP is chipboard without the laminate — a different product from LDSP at a
    # different price, and it used to borrow LDSP's label, which made the two
    # indistinguishable on every screen and document.
    "dsp": "DSP",
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

# Printed only for a one-sided board. Two-sided is the norm and saying so on
# every row would be noise; one-sided is the exception a buyer must see.
_ONE_SIDED_LABEL = "1 tomonlama"


def material_label(snapshot: dict[str, Any], material_id: object) -> str:
    """Canonical panel label, e.g. `MDF Egger H1334 ST9 · Sanoma · 2750×1830×18 mm`.

    Falls back to the first 8 characters of `material_id` when the snapshot
    carries no identity at all (empty/missing snapshot).
    """
    raw_type = _snapshot_text(snapshot, "type", "tur")
    type_label = _PANEL_TYPE_LABELS.get(raw_type, raw_type)
    manufacturer = _snapshot_text(snapshot, "manufacturer_name")
    decor_name = _decor_name(snapshot)
    identity = _identity(snapshot, decor_name)
    thickness = _snapshot_text(snapshot, "thickness_mm", "qalinlik_mm")
    length = _int_snapshot(
        _snapshot_value(snapshot, "length_mm", "uzunlik_mm", "panel_length_mm"), fallback=0
    )
    width = _int_snapshot(
        _snapshot_value(snapshot, "width_mm", "eni_mm", "panel_width_mm"), fallback=0
    )

    base = " ".join(part for part in [type_label, manufacturer, identity] if part)
    if not base:
        return str(material_id)[:8]

    details: list[str] = []
    if decor_name and decor_name.lower() not in base.lower():
        details.append(decor_name)
    if length > 0 and width > 0:
        dims = f"{length}×{width}"
        if thickness:
            dims = f"{dims}×{_format_mm(thickness)}"
        details.append(f"{dims} mm")
    elif thickness:
        details.append(f"{_format_mm(thickness)} mm")
    if _int_snapshot(_snapshot_value(snapshot, "finished_sides"), fallback=0) == 1:
        details.append(_ONE_SIDED_LABEL)
    return " · ".join([base, *details])


def edge_label(snapshot: dict[str, Any], material_id: object) -> str:
    """Canonical edge-band label, e.g. `Egger H1334 ST9 · Sanoma · 2×36 mm`.

    Falls back to the first 8 characters of `material_id` when the snapshot
    carries no identity at all (empty/missing snapshot).
    """
    manufacturer = _snapshot_text(snapshot, "manufacturer_name")
    decor_name = _decor_name(snapshot)
    identity = _identity(snapshot, decor_name)
    thickness = _snapshot_text(snapshot, "thickness_mm", "qalinlik_mm")
    width = _int_snapshot(
        _snapshot_value(snapshot, "tape_width_mm", "kromka_eni_mm", "edge_width_mm"), fallback=0
    )

    base = " ".join(part for part in [manufacturer, identity] if part) or str(material_id)[:8]
    # A decor without a code puts its name in the base, so the detail slot must
    # suppress it the same way material_label does — otherwise the label reads
    # "Egger Sonoma eman · Sonoma eman · 2×36 mm".
    detail = decor_name if decor_name and decor_name.lower() not in base.lower() else ""
    if thickness and width > 0:
        size = f"{_format_mm(thickness)}×{width} mm"
    elif thickness:
        size = f"{_format_mm(thickness)} mm"
    else:
        size = ""
    return " · ".join(part for part in [base, detail, size] if part)


def _decor_name(snapshot: dict[str, Any]) -> str:
    """The decor's own name — `Sonoma eman`, never the whole generated string.

    `nomi` and `color` are consulted before `name` on purpose: see the key-
    collision note in the module docstring. Neither of them can occur in a
    current snapshot, so this still reads "current vocabulary first" in effect.
    """
    return _snapshot_text(snapshot, "nomi", "color", "name")


def _identity(snapshot: dict[str, Any], decor_name: str) -> str:
    """The name-slot of the base: decor code first, then whatever names exist.

    `name` is consulted before falling through to the decor name because a
    pre-reshape snapshot stored its server-generated material name there, and a
    historical row must keep rendering the string it always did.
    """
    return (
        _snapshot_text(snapshot, "code", "kod", "decor_code")
        or _snapshot_text(snapshot, "name")
        or decor_name
    )


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
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return fallback
