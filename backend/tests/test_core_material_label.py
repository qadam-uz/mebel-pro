"""Unit tests for the canonical material/edge-band label formatters.

`material_label` and `edge_label` are the single source of truth for how a
material's catalog identity is displayed anywhere in the app (cutting PDF,
sales order summaries, workshop production views, finance ledger
pass-through) — see app/core/material_label.py's module docstring.
"""

# ruff: noqa: RUF001 -- expected labels reuse the display format's
# multiplication sign in dimensions.

from app.core.material_label import edge_label, material_label


def test_material_label_uses_catalog_identity_format() -> None:
    assert (
        material_label(
            {
                "type": "dsp",
                "manufacturer_name": "Egger",
                "decor_code": "H1334 ST9",
                "name": "Dub",
                "color": "Sanoma",
                "thickness_mm": "18.0",
                "panel_length_mm": 2750,
                "panel_width_mm": 1830,
            },
            "id",
        )
        == "LDSP Egger H1334 ST9 · Sanoma · 2750×1830×18 mm"
    )


def test_material_label_maps_panel_type_codes_to_display_names() -> None:
    assert (
        material_label(
            {
                "type": "mdf",
                "manufacturer_name": "MDF Altay",
                "name": "Natural",
                "color": "Natural",
                "thickness_mm": "16",
                "panel_length_mm": 2750,
                "panel_width_mm": 1830,
            },
            "id",
        )
        == "MDF MDF Altay Natural · 2750×1830×16 mm"
    )


def test_material_label_omits_color_already_implied_by_base() -> None:
    # "Sanoma" appears in the decor/name already used for `base`, so it must
    # not be repeated as a separate `· color` segment.
    label = material_label(
        {
            "type": "dsp",
            "manufacturer_name": "Egger",
            "name": "Sanoma Oak",
            "color": "Sanoma",
            "thickness_mm": "18",
            "panel_length_mm": 2750,
            "panel_width_mm": 1830,
        },
        "id",
    )
    assert label == "LDSP Egger Sanoma Oak · 2750×1830×18 mm"


def test_material_label_falls_back_to_name_only_without_identity_fields() -> None:
    assert material_label({"name": "Dub"}, "id") == "Dub"


def test_material_label_falls_back_to_material_id_prefix_when_snapshot_is_empty() -> None:
    assert material_label({}, "0123456789abcdef") == "01234567"


def test_material_label_uses_thickness_only_dims_when_panel_size_is_missing() -> None:
    assert (
        material_label({"manufacturer_name": "Egger", "name": "Dub", "thickness_mm": "18"}, "id")
        == "Egger Dub · 18 mm"
    )


def test_edge_label_uses_catalog_identity_format() -> None:
    assert (
        edge_label(
            {
                "manufacturer_name": "Egger",
                "decor_code": "H1334 ST9",
                "name": "Dub",
                "color": "Sanoma",
                "thickness_mm": "2",
                "edge_width_mm": 36,
            },
            "id",
        )
        == "Egger H1334 ST9 · Sanoma · 2×36 mm"
    )


def test_edge_label_has_no_length_by_width_dimension() -> None:
    # Edges don't carry panel_length_mm/panel_width_mm at all -- confirm the
    # label never grows a length-by-width segment even if such keys leak in.
    label = edge_label(
        {
            "manufacturer_name": "Egger",
            "name": "Dub",
            "thickness_mm": "2",
            "edge_width_mm": 36,
            "panel_length_mm": 2750,
            "panel_width_mm": 1830,
        },
        "id",
    )
    assert label == "Egger Dub · 2×36 mm"
    assert "2750" not in label


def test_edge_label_falls_back_to_thickness_only_when_edge_width_is_missing() -> None:
    assert (
        edge_label({"manufacturer_name": "Egger", "name": "Dub", "thickness_mm": "2"}, "id")
        == "Egger Dub · 2 mm"
    )


def test_edge_label_falls_back_to_name_only_without_identity_fields() -> None:
    assert edge_label({"name": "Dub"}, "id") == "Dub"


def test_edge_label_falls_back_to_material_id_prefix_when_snapshot_is_empty() -> None:
    assert edge_label({}, "0123456789abcdef") == "01234567"
