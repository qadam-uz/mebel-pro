"""Unit tests for the canonical material/edge-band label formatters.

`material_label` and `edge_label` are the single source of truth for how a
material's catalog identity is displayed anywhere in the app (cutting PDF,
sales order summaries, workshop production views, finance ledger
pass-through) — see app/core/material_label.py's module docstring.

**Three** vocabularies are covered, on purpose — the app has written three over
its life and `order_items.material_snapshot` / `cutting_results.
material_snapshots` are frozen history that no migration rewrites, so the
database holds all three forever:

1. **current English** — `type`, `code`, `name`, `thickness_mm`, `length_mm`,
   `width_mm`, `tape_width_mm`, `finished_sides` (the decor/decor-format reshape).
2. **Uzbek** — `tur`, `kod`, `nomi`, `qalinlik_mm`, `uzunlik_mm`, `eni_mm`,
   `kromka_eni_mm` (written between the two English eras).
3. **pre-reshape English** — `type`, `decor_code`, `name`, `color`,
   `thickness_mm`, `panel_length_mm`, `panel_width_mm`, `edge_width_mm`.

The tests up to `test_edge_label_falls_back_to_material_id_prefix_when_snapshot_is_empty`
use vocabulary 3 and their expected strings are frozen. The block after it uses
vocabulary 1 and asserts the same output format, and
`test_material_label_resolves_all_three_snapshot_vocabularies` pins all three at
once. If any block is deleted, the snapshots it stands for silently render as an
8-character id fragment, with no error anywhere.
"""

# ruff: noqa: RUF001, RUF003 -- expected labels reuse the display format's
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
        == "DSP Egger H1334 ST9 · Sanoma · 2750×1830×18 mm"
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
    assert label == "DSP Egger Sanoma Oak · 2750×1830×18 mm"


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


# --------------------------------------------------------------------------- #
# Current snapshot vocabulary (decor identity + branch format).
# --------------------------------------------------------------------------- #


def test_material_label_reads_the_decor_snapshot_vocabulary() -> None:
    assert (
        material_label(
            {
                "manufacturer_name": "Egger",
                "type": "dsp",
                "code": "H1334 ST9",
                "name": "Sanoma",
                "thickness_mm": "18.0",
                "length_mm": 2750,
                "width_mm": 1830,
                "has_grain": True,
            },
            "id",
        )
        == "DSP Egger H1334 ST9 · Sanoma · 2750×1830×18 mm"
    )


def test_material_label_renders_every_decor_type() -> None:
    def label(type: str) -> str:
        return material_label(
            {"type": type, "manufacturer_name": "Egger", "name": "Sanoma", "thickness_mm": "18"},
            "id",
        )

    # `ldsp` and `dsp` are separate products and finally print separate words.
    # `dsp` used to borrow LDSP's label, which made laminated and bare chipboard
    # indistinguishable on every screen and document — including on the historical
    # snapshots above, which is why those now read «DSP» too.
    assert label("ldsp").startswith("LDSP ")
    assert label("dsp").startswith("DSP ")
    assert label("mdf").startswith("MDF ")
    assert label("fanera").startswith("Fanera ")
    assert label("yogoch").startswith("Yog'och ")
    assert label("boshqa").startswith("List ")
    assert label("kromka").startswith("Kromka ")


def test_material_label_omits_nomi_already_implied_by_the_kod() -> None:
    label = material_label(
        {
            "type": "dsp",
            "manufacturer_name": "Egger",
            "code": "Sanoma Oak",
            "name": "Sanoma",
            "thickness_mm": "18",
            "length_mm": 2750,
            "width_mm": 1830,
        },
        "id",
    )
    assert label == "DSP Egger Sanoma Oak · 2750×1830×18 mm"


def test_material_label_uses_nomi_as_the_base_when_the_decor_has_no_kod() -> None:
    # `boshqa` and `yogoch` decors routinely have no decor code at all: the
    # name moves into the base and must not also appear as a detail.
    assert (
        material_label(
            {
                "type": "yogoch",
                "manufacturer_name": "Egger",
                "name": "Sonoma eman",
                "thickness_mm": "18",
                "length_mm": 2750,
                "width_mm": 1830,
            },
            "id",
        )
        == "Yog'och Egger Sonoma eman · 2750×1830×18 mm"
    )


def test_edge_label_reads_the_decor_snapshot_vocabulary() -> None:
    assert (
        edge_label(
            {
                "manufacturer_name": "Egger",
                "type": "kromka",
                "code": "H1334 ST9",
                "name": "Sanoma",
                "thickness_mm": "2",
                "tape_width_mm": 36,
            },
            "id",
        )
        == "Egger H1334 ST9 · Sanoma · 2×36 mm"
    )


def test_edge_label_omits_nomi_already_implied_by_the_base() -> None:
    # Without this the code-less kromka reads "Egger Sonoma eman · Sonoma eman
    # · 2×36 mm" — the old shape could not hit this, because `name` and `color`
    # were two different columns.
    assert (
        edge_label(
            {
                "manufacturer_name": "Egger",
                "type": "kromka",
                "name": "Sonoma eman",
                "thickness_mm": "2",
                "tape_width_mm": 36,
            },
            "id",
        )
        == "Egger Sonoma eman · 2×36 mm"
    )


def test_edge_label_has_no_length_by_width_dimension_in_the_new_vocabulary() -> None:
    label = edge_label(
        {
            "manufacturer_name": "Egger",
            "type": "kromka",
            "name": "Sanoma",
            "thickness_mm": "2",
            "tape_width_mm": 36,
            "length_mm": 2750,
            "width_mm": 1830,
        },
        "id",
    )
    assert label == "Egger Sanoma · 2×36 mm"
    assert "2750" not in label


# --------------------------------------------------------------------------- #
# finished_sides — the one-sided board is the exception a buyer must see.
# --------------------------------------------------------------------------- #


def _board(**overrides: object) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "type": "ldsp",
        "manufacturer_name": "Egger",
        "code": "H1334 ST9",
        "name": "Sonoma eman",
        "thickness_mm": "18",
        "length_mm": 2750,
        "width_mm": 1830,
    }
    snapshot.update(overrides)
    return snapshot


def test_material_label_marks_a_one_sided_board() -> None:
    # One-sided is the norm for facade MDF and the cheap white LDSP used for
    # hidden parts, and it is a different product at a different price — the
    # label has to say so or the two are indistinguishable on the order.
    assert (
        material_label(_board(finished_sides=1), "id")
        == "LDSP Egger H1334 ST9 · Sonoma eman · 2750×1830×18 mm · 1 tomonlama"
    )


def test_material_label_says_nothing_extra_for_a_two_sided_board() -> None:
    # Two-sided is the norm; printing «2 tomonlama» on every row would be noise.
    two_sided = material_label(_board(finished_sides=2), "id")
    assert two_sided == "LDSP Egger H1334 ST9 · Sonoma eman · 2750×1830×18 mm"
    # And a snapshot that predates the column at all reads exactly the same.
    assert two_sided == material_label(_board(), "id")


def test_material_label_resolves_all_three_snapshot_vocabularies() -> None:
    """One physical board, written three ways across the app's life, one label.

    These three literals are the contract of app/core/material_label.py's
    three-vocabulary reader. The two traps it has to survive are both here:
    `name` means the decor name in vocabulary 1 but the whole generated material
    name in vocabulary 3 (which is why the pre-reshape dict below also carries
    `color`), and the decor code lives under three different keys.
    """

    current_english = {
        "type": "ldsp",
        "manufacturer_name": "Egger",
        "code": "H1334 ST9",
        "name": "Sonoma eman",
        "thickness_mm": "18",
        "length_mm": 2750,
        "width_mm": 1830,
        "has_grain": True,
        "finished_sides": 2,
    }
    uzbek = {
        "tur": "ldsp",
        "manufacturer_name": "Egger",
        "kod": "H1334 ST9",
        "nomi": "Sonoma eman",
        "qalinlik_mm": "18",
        "uzunlik_mm": 2750,
        "eni_mm": 1830,
        "tolali": True,
    }
    pre_reshape_english = {
        "type": "ldsp",
        "manufacturer_name": "Egger",
        "decor_code": "H1334 ST9",
        # The generated material name, not the decor's — the collision the
        # reader disambiguates by consulting `color` for the decor-name slot.
        "name": "LDSP Egger H1334 ST9 Sonoma eman",
        "color": "Sonoma eman",
        "thickness_mm": "18",
        "panel_length_mm": 2750,
        "panel_width_mm": 1830,
    }

    expected = "LDSP Egger H1334 ST9 · Sonoma eman · 2750×1830×18 mm"
    assert material_label(current_english, "id") == expected
    assert material_label(uzbek, "id") == expected
    assert material_label(pre_reshape_english, "id") == expected


def test_edge_label_resolves_all_three_snapshot_vocabularies() -> None:
    # Same three eras for the tape's own width key: `tape_width_mm` /
    # `kromka_eni_mm` / `edge_width_mm`.
    current_english = {
        "type": "kromka",
        "manufacturer_name": "Egger",
        "code": "H1334 ST9",
        "name": "Sonoma eman",
        "thickness_mm": "0.4",
        "tape_width_mm": 22,
    }
    uzbek = {
        "tur": "kromka",
        "manufacturer_name": "Egger",
        "kod": "H1334 ST9",
        "nomi": "Sonoma eman",
        "qalinlik_mm": "0.4",
        "kromka_eni_mm": 22,
    }
    pre_reshape_english = {
        "type": "kromka",
        "manufacturer_name": "Egger",
        "decor_code": "H1334 ST9",
        "name": "Kromka Egger H1334 ST9 Sonoma eman",
        "color": "Sonoma eman",
        "thickness_mm": "0.4",
        "edge_width_mm": 22,
    }

    expected = "Egger H1334 ST9 · Sonoma eman · 0.4×22 mm"
    assert edge_label(current_english, "id") == expected
    assert edge_label(uzbek, "id") == expected
    assert edge_label(pre_reshape_english, "id") == expected
