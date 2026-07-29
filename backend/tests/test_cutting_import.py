import json
from pathlib import Path

import pytest
from app.modules.cutting.imports.base import ImportParseError, ImportParseOptions
from app.modules.cutting.imports.common import draft_name_from_filename
from app.modules.cutting.imports.detect import decode_csv_text, sniff_csv_delimiter, sniff_format
from app.modules.cutting.imports.map_2dplace import _to_import_response, derive_map_cut_params
from app.modules.cutting.imports.map_parser import MapFile, MapRecord, MapSheet
from app.modules.cutting.imports.parser import guess_header, parse_import_file
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_cutting_api import _auth, _client_access

FIXTURES = Path(__file__).parent / "fixtures" / "cutting_import"
MAP_FIXTURES = FIXTURES / "map"


def _csv_bytes(text: str, *, encoding: str = "utf-8") -> bytes:
    return text.encode(encoding)


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _map_fixture(name: str) -> bytes:
    return (MAP_FIXTURES / name).read_bytes()


def test_detection_call_always_returns_mapping_preview_for_csv() -> None:
    response = parse_import_file(
        filename="minimal.csv",
        content=_csv_bytes("L;W;Qty\n720;450;2\n"),
    )

    assert response.status == "needs_mapping"
    assert response.grid[:2] == [["L", "W", "Qty"], ["720", "450", "2"]]
    assert response.guessed_mapping == {"length_mm": 0, "width_mm": 1, "quantity": 2}
    assert response.guessed_skip_rows == 1


def test_header_guesser_requires_two_tokens_and_maps_mebelshik_roles() -> None:
    no_header = [["Длина", "", ""], ["720", "450", "1"]]
    mebelshik_header = [
        [
            "Позиция",
            "Наименование",
            "Длина",
            "Ширина",
            "Толщина",
            "Кол-во",
            "Наименование материала",
            "Облицовка Д1",
            "Облицовка Д2",
            "Облицовка Ш1",
            "Облицовка Ш2",
        ]
    ]

    assert guess_header(no_header) == ({}, 0)
    mapping, skip_rows = guess_header(mebelshik_header)

    assert skip_rows == 1
    assert mapping == {
        "length_mm": 2,
        "width_mm": 3,
        "thickness_mm": 4,
        "quantity": 5,
        "material": 6,
        "edge_top": 7,
        "edge_bottom": 8,
        "edge_left": 9,
        "edge_right": 10,
    }


def test_full_mebelshik_project_csv_parse_reports_repeated_header_and_thickness_hints() -> None:
    response = parse_import_file(
        filename="bazis_mebelshik_project.csv",
        content=_fixture("bazis_mebelshik_project.csv"),
        options=ImportParseOptions(
            skip_rows=1,
            mapping={
                "length_mm": 2,
                "width_mm": 3,
                "thickness_mm": 4,
                "quantity": 5,
                "material": 6,
                "edge_top": 7,
                "edge_bottom": 8,
                "edge_left": 9,
                "edge_right": 10,
            },
        ),
    )

    assert response.status == "parsed"
    assert response.total_parts == 5
    assert response.total_pieces == 10
    assert response.parts[0].length_mm == 1832
    assert response.parts[0].width_mm == 482
    assert response.parts[0].quantity == 2
    assert response.parts[0].edges == {"top": "e1", "bottom": None, "left": "e2", "right": "e2"}
    assert [group.model_dump() for group in response.panel_materials] == [
        {
            "key": "m1",
            "label": "ЛДСП EGGER H1334 ST9 Дуб Сорано",
            "part_count": 3,
            "thickness_hint": "16",
        },
        {
            "key": "m2",
            "label": "МДФ Kronospan 0101 Белый",
            "part_count": 2,
            "thickness_hint": "18",
        },
    ]
    assert [group.model_dump() for group in response.edge_materials] == [
        {"key": "e1", "label": "2", "side_count": 10},
        {"key": "e2", "label": "0,4", "side_count": 3},
    ]
    assert [row.model_dump() for row in response.skipped_rows] == [
        {"row": 6, "reason": "non_numeric_length", "preview": "Позиция"}
    ]
    assert {warning.code: warning.rows for warning in response.warnings} == {
        "dimension_rounded": [2, 4],
    }


def test_bazis_xml_parse_returns_parsed_ir_without_mapping() -> None:
    response = parse_import_file(
        filename="bazis_mebelshik_spec.xml",
        content=_fixture("bazis_mebelshik_spec.xml"),
    )

    assert response.status == "parsed"
    assert response.source_format == "bazis_xml"
    assert response.total_parts == 3
    assert response.total_pieces == 7
    assert response.ignored_object_count == 1
    assert [part.model_dump() for part in response.parts] == [
        {
            "row": 1,
            "length_mm": 721,
            "width_mm": 450,
            "quantity": 4,
            "material_key": "m1",
            "follow_grain": True,
            "edges": {"top": "e1", "bottom": "e1", "left": "e1", "right": "e1"},
        },
        {
            "row": 2,
            "length_mm": 600,
            "width_mm": 300,
            "quantity": 2,
            "material_key": "m2",
            "follow_grain": True,
            "edges": {"top": "e2", "bottom": "e2", "left": None, "right": None},
        },
        {
            "row": 4,
            "length_mm": 800,
            "width_mm": 90,
            "quantity": 1,
            "material_key": "m1",
            "follow_grain": False,
            "edges": {"top": None, "bottom": None, "left": None, "right": None},
        },
    ]
    assert [group.model_dump() for group in response.panel_materials] == [
        {"key": "m1", "label": "ЛДСП EGGER H1334", "part_count": 2, "thickness_hint": "18"},
        {"key": "m2", "label": "МДФ Белый W980", "part_count": 1, "thickness_hint": "16"},
    ]
    assert [group.model_dump() for group in response.edge_materials] == [
        {"key": "e1", "label": "ABS H1334 0.4", "side_count": 4},
        {"key": "e2", "label": "ABS White", "side_count": 2},
    ]
    assert [row.model_dump() for row in response.skipped_rows] == [
        {"row": 3, "reason": "non_numeric_width", "preview": "Ошибка ширины"}
    ]
    assert {warning.code: warning.rows for warning in response.warnings} == {
        "dimension_rounded": [1],
        "edge_see_drawing": [2],
        "ignored_grooves": [2],
        "ignored_holes": [2],
        "non_rectangular": [2],
        "quantity_defaulted": [2],
    }


def test_bazis_xml_accepts_cp1251_declared_encoding() -> None:
    content = """<?xml version="1.0" encoding="windows-1251"?>
<Проект>
  <Изделие>
    <СписокЭлементов>
      <Объект>
        <ТипОбъекта>Панель</ТипОбъекта>
        <Длина>500</Длина>
        <Ширина>300</Ширина>
        <Количество>1</Количество>
      </Объект>
    </СписокЭлементов>
  </Изделие>
</Проект>
""".encode("cp1251")

    response = parse_import_file(filename="spec.xml", content=content)

    assert response.status == "parsed"
    assert response.source_format == "bazis_xml"
    assert response.parts[0].length_mm == 500


def test_xml_detection_rejects_non_project_and_entity_payloads() -> None:
    assert sniff_format(_fixture("bazis_mebelshik_spec.xml"), "spec.xml") == "bazis_xml"

    with pytest.raises(ImportParseError) as unsupported:
        parse_import_file(filename="objtree.xml", content=b"<?xml version='1.0'?><ObjTree />")
    assert unsupported.value.code == "unsupported_format"

    entity_payload = "<!DOCTYPE x [<!ENTITY boom 'boom'>]><Проект>&boom;</Проект>"
    with pytest.raises(ImportParseError) as unsafe_xml:
        parse_import_file(
            filename="entity.xml",
            content=entity_payload.encode(),
        )
    assert unsafe_xml.value.code == "invalid_file"


def test_map_parser_regression_and_range_expansion() -> None:
    from app.modules.cutting.imports.map_parser import parse_map_file

    single = parse_map_file(_map_fixture("6.map"), "6.map")
    repeated = parse_map_file(_map_fixture("9.map"), "9.map")

    assert len(single.sheets) == 1
    assert single.sheets[0].width_mm == 2750
    assert single.sheets[0].height_mm == 1830
    assert sum(not record.is_waste for record in single.sheets[0].records) == 6
    assert sum(record.is_remainder for record in single.sheets[0].records) == 1
    first = next(record for record in single.sheets[0].records if not record.is_waste)
    assert (first.x, first.y, first.width, first.height) == (5, 5, 2170, 330)
    assert first.edges == (True, False, True, True)
    assert [sheet.name for sheet in repeated.sheets] == ["1: Лист 1", "2: Лист 2", "3: Лист 3"]
    assert all(
        sum(not record.is_waste for record in sheet.records) == 3 for sheet in repeated.sheets
    )


def test_map_import_parse_returns_layout_and_material_groups() -> None:
    response = parse_import_file(filename="6.map", content=_map_fixture("6.map"))

    assert response.status == "parsed"
    assert response.source_format == "map_2dplace"
    assert response.total_parts == 3
    assert response.total_pieces == 6
    assert response.panel_materials[0].model_dump() == {
        "key": "m1",
        "label": "2750x1830 mm list",
        "part_count": 3,
        "thickness_hint": None,
    }
    assert response.material_groups[0].model_dump() == {
        "key": "m1",
        "label": "2750x1830 mm list",
        "width_mm": 2750,
        "height_mm": 1830,
        "sheet_count": 1,
        "hint": None,
    }
    assert response.edge_materials[0].side_count == 22
    assert response.map_layout is not None
    assert response.map_layout.sheets[0].parts_count == 6
    assert response.map_layout.sheets[0].remainder_count == 1
    assert response.map_layout.part_rows[0].part_ref == "map-1"


def test_map_import_keeps_undersized_parts_instead_of_rejecting_the_file() -> None:
    """A small part is a row the editor flags, never a reason to lose the drawing —
    the importer used to reject the whole file over a sub-50 mm record."""
    sheet = MapSheet(
        name="1: Лист 1",
        width_mm=2750,
        height_mm=1830,
        records=[
            MapRecord(
                x=0, y=0, width=30, height=20, name="tiny", edges=(False, False, False, False)
            ),
            MapRecord(
                x=0, y=100, width=600, height=400, name="normal", edges=(False, False, False, False)
            ),
        ],
    )
    map_file = MapFile(description="", customer_name="", order_type="", sheets=[sheet])

    response = _to_import_response(map_file)

    assert response.status == "parsed"
    assert sorted((part.length_mm, part.width_mm) for part in response.parts) == [
        (30, 20),
        (600, 400),
    ]


@pytest.mark.parametrize(
    ("filename", "expected_kerf_mm", "expected_edge_trim_mm"),
    [
        # These are the honest test data: a human measured kerf/trim directly
        # off each real fixture's placement geometry before this derivation
        # was built (see imports/map_2dplace.py:derive_map_cut_params).
        ("6.map", 4, 5),
        ("AFZAL.map", 4, 5),
        ("A1.map", 4, 5),
        ("9.map", 4, 10),
    ],
)
def test_derive_map_cut_params_matches_real_fixtures(
    filename: str, expected_kerf_mm: int, expected_edge_trim_mm: int
) -> None:
    response = parse_import_file(filename=filename, content=_map_fixture(filename))
    assert response.map_layout is not None

    kerf_mm, edge_trim_mm = derive_map_cut_params(response.map_layout)

    assert kerf_mm == expected_kerf_mm
    assert edge_trim_mm == expected_edge_trim_mm


def test_derive_map_cut_params_falls_back_to_zero_for_a_single_unadjacent_part() -> None:
    """A lone part with no neighbour (no kerf evidence) sitting far from every
    sheet edge (no trustworthy trim evidence — its nearest inset is well past
    the branch's own edge-trim bound) must not report an invented number.
    Falls back to 0/0, the prior hardcoded behaviour."""
    sheet = MapSheet(
        name="1: Лист 1",
        width_mm=2750,
        height_mm=1830,
        records=[
            MapRecord(
                x=500,
                y=500,
                width=100,
                height=100,
                name="lonely",
                edges=(False, False, False, False),
            ),
        ],
    )
    map_file = MapFile(description="", customer_name="", order_type="", sheets=[sheet])
    response = _to_import_response(map_file)
    assert response.map_layout is not None

    kerf_mm, edge_trim_mm = derive_map_cut_params(response.map_layout)

    assert kerf_mm == 0
    assert edge_trim_mm == 0


def test_derive_map_cut_params_ignores_a_one_off_gap_in_favour_of_the_dominant_one() -> None:
    """Three parts on one sheet: two are 4 mm apart (the dominant, real kerf),
    one is a stray 1 mm off — the derivation must pick the frequent 4 mm, not
    the minimum 1 mm (AFZAL.map has exactly this shape in the real data)."""
    sheet = MapSheet(
        name="1: Лист 1",
        width_mm=2750,
        height_mm=1830,
        records=[
            MapRecord(
                x=5, y=5, width=200, height=100, name="a", edges=(False, False, False, False)
            ),
            MapRecord(
                x=209, y=5, width=200, height=100, name="b", edges=(False, False, False, False)
            ),  # 4 mm gap from "a"
            MapRecord(
                x=413, y=5, width=200, height=100, name="c", edges=(False, False, False, False)
            ),  # 4 mm gap from "b"
            MapRecord(
                x=614, y=5, width=200, height=100, name="d", edges=(False, False, False, False)
            ),  # 1 mm stray gap from "c"
        ],
    )
    map_file = MapFile(description="", customer_name="", order_type="", sheets=[sheet])
    response = _to_import_response(map_file)
    assert response.map_layout is not None

    kerf_mm, _ = derive_map_cut_params(response.map_layout)

    assert kerf_mm == 4


def test_draft_name_from_filename_strips_extension_trims_and_caps() -> None:
    assert draft_name_from_filename("AFZAL.map") == "AFZAL"
    assert draft_name_from_filename("  spaced name.csv  ") == "spaced name"
    assert draft_name_from_filename("archive.tar.gz") == "archive.tar"
    assert draft_name_from_filename("x" * 100 + ".map") == "x" * 64


@pytest.mark.parametrize("filename", [None, "", "   "])
def test_draft_name_from_filename_returns_none_when_nothing_usable_remains(
    filename: str | None,
) -> None:
    assert draft_name_from_filename(filename) is None


def test_mebelshik_spec_csv_without_material_column_uses_all_group_and_silent_blank_line() -> None:
    response = parse_import_file(
        filename="bazis_mebelshik_spec.csv",
        content=_fixture("bazis_mebelshik_spec.csv"),
        options=ImportParseOptions(
            skip_rows=1,
            mapping={
                "length_mm": 2,
                "width_mm": 3,
                "quantity": 4,
                "edge_top": 5,
                "edge_bottom": 6,
                "edge_left": 7,
                "edge_right": 8,
            },
        ),
    )

    assert response.total_parts == 5
    assert response.total_pieces == 8
    assert response.skipped_rows == []
    assert [group.model_dump() for group in response.panel_materials] == [
        {
            "key": "__all__",
            "label": "Butun fayl uchun material",
            "part_count": 5,
            "thickness_hint": None,
        }
    ]


def test_thickness_hint_aggregation_sorts_distinct_numeric_values_per_panel_group() -> None:
    content = _csv_bytes(
        "L;W;Qty;Material;Толщина\n"
        "100;100;1;A;18\n"
        "100;100;1;A;16,5\n"
        "100;100;1;A;16\n"
        "100;100;1;B;bad\n"
    )

    response = parse_import_file(
        filename="mixed.csv",
        content=content,
        options=ImportParseOptions(
            skip_rows=1,
            mapping={
                "length_mm": 0,
                "width_mm": 1,
                "quantity": 2,
                "material": 3,
                "thickness_mm": 4,
            },
        ),
    )

    assert [group.model_dump() for group in response.panel_materials] == [
        {"key": "m1", "label": "A", "part_count": 3, "thickness_hint": "16 / 16.5 / 18"},
        {"key": "m2", "label": "B", "part_count": 1, "thickness_hint": None},
    ]


def test_cp1251_csv_decimal_commas_and_unknown_grain_warning() -> None:
    content = _csv_bytes(
        "Длина;Ширина;Количество;Материал;Текстура\n720,5;450;1;ЛДСП;maybe\n",
        encoding="cp1251",
    )

    response = parse_import_file(
        filename="bazis.csv",
        content=content,
        options=ImportParseOptions(
            skip_rows=1,
            mapping={
                "length_mm": 0,
                "width_mm": 1,
                "quantity": 2,
                "material": 3,
                "follow_grain": 4,
            },
        ),
    )

    assert response.parts[0].length_mm == 721
    assert response.parts[0].follow_grain is True
    assert {warning.code: warning.rows for warning in response.warnings} == {
        "dimension_rounded": [2],
        "grain_token_unknown": [2],
    }


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("archive.xlsx", b"PK\x03\x04not accepted", "unsupported_format"),
        ("legacy.xls", b"\xd0\xcf\x11\xe0old", "unsupported_format"),
        ("foo.txt", b"L;W\n100;100\n", "unsupported_format"),
        ("binary.csv", b"\x01\x02\x03", "unsupported_format"),
        ("empty.csv", b"", "empty_file"),
    ],
)
def test_rejected_files(filename: str, content: bytes, code: str) -> None:
    with pytest.raises(ImportParseError) as exc:
        parse_import_file(filename=filename, content=content)

    assert exc.value.code == code


def test_invalid_mapping_and_too_many_parts_raise_422_codes() -> None:
    with pytest.raises(ImportParseError) as invalid:
        parse_import_file(
            filename="minimal.csv",
            content=_csv_bytes("100;100\n"),
            options=ImportParseOptions(mapping={"length_mm": 0}),
        )
    assert invalid.value.code == "invalid_mapping"

    at_cap = parse_import_file(
        filename="at_cap.csv",
        content=_csv_bytes("L;W;Qty\n100;100;300\n"),
        options=ImportParseOptions(
            skip_rows=1,
            mapping={"length_mm": 0, "width_mm": 1, "quantity": 2},
        ),
    )
    assert at_cap.total_pieces == 300

    with pytest.raises(ImportParseError) as too_many:
        parse_import_file(
            filename="too_many.csv",
            content=_csv_bytes("L;W;Qty\n100;100;301\n"),
            options=ImportParseOptions(
                skip_rows=1,
                mapping={"length_mm": 0, "width_mm": 1, "quantity": 2},
            ),
        )
    assert too_many.value.code == "too_many_parts"

    panel = (
        "<Объект><ТипОбъекта>Панель</ТипОбъекта><Длина>100</Длина><Ширина>100</Ширина>"
        "<Количество>301</Количество></Объект>"
    )
    too_many_xml_content = (
        f"<Проект><Изделие><СписокЭлементов>{panel}</СписокЭлементов></Изделие></Проект>"
    )
    with pytest.raises(ImportParseError) as too_many_xml_error:
        parse_import_file(
            filename="too_many.xml",
            content=too_many_xml_content.encode(),
        )
    assert too_many_xml_error.value.code == "too_many_parts"


def test_encoding_fallback_and_delimiter_tie_rule() -> None:
    assert decode_csv_text("Длина".encode("cp1251")) == "Длина"
    assert sniff_csv_delimiter("A;B,C\n1;2,3\n") == ";"
    assert sniff_format(_map_fixture("6.map"), "6.map") == "map_2dplace"


async def test_client_cutting_import_parse_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _ = await _client_access(db_session, phone="+998901111030")
    unauthenticated = await client.post(
        "/api/v1/client/cutting/import/parse",
        files={"file": ("minimal.csv", _csv_bytes("L;W;Qty\n100;80;1\n"), "text/csv")},
    )
    detected = await client.post(
        "/api/v1/client/cutting/import/parse",
        headers=_auth(access),
        files={"file": ("minimal.csv", _csv_bytes("L;W;Qty\n100;80;1\n"), "text/csv")},
    )
    parsed = await client.post(
        "/api/v1/client/cutting/import/parse",
        headers=_auth(access),
        data={
            "options": json.dumps(
                {"skip_rows": 1, "mapping": {"length_mm": 0, "width_mm": 1, "quantity": 2}}
            )
        },
        files={"file": ("minimal.csv", _csv_bytes("L;W;Qty\n100;80;1\n"), "text/csv")},
    )

    assert unauthenticated.status_code == 401
    assert detected.status_code == 200
    assert detected.json()["status"] == "needs_mapping"
    assert detected.json()["source_format"] == "csv"
    assert parsed.status_code == 200
    assert parsed.json()["status"] == "parsed"
    assert parsed.json()["parts"][0] == {
        "row": 2,
        "length_mm": 100,
        "width_mm": 80,
        "quantity": 1,
        "material_key": "__all__",
        "follow_grain": True,
        "edges": {"top": None, "bottom": None, "left": None, "right": None},
    }

    xml = await client.post(
        "/api/v1/client/cutting/import/parse",
        headers=_auth(access),
        files={
            "file": (
                "spec.xml",
                _fixture("bazis_mebelshik_spec.xml"),
                "application/xml",
            )
        },
    )

    assert xml.status_code == 200
    assert xml.json()["status"] == "parsed"
    assert xml.json()["source_format"] == "bazis_xml"
    assert xml.json()["ignored_object_count"] == 1

    map_response = await client.post(
        "/api/v1/client/cutting/import/parse",
        headers=_auth(access),
        files={"file": ("6.map", _map_fixture("6.map"), "application/octet-stream")},
    )

    assert map_response.status_code == 200
    assert map_response.json()["status"] == "parsed"
    assert map_response.json()["source_format"] == "map_2dplace"
    assert map_response.json()["map_layout"]["sheets"][0]["width_mm"] == 2750
