import json
from pathlib import Path

import pytest
from app.modules.cutting.imports.base import ImportParseError, ImportParseOptions
from app.modules.cutting.imports.detect import decode_csv_text, sniff_csv_delimiter
from app.modules.cutting.imports.parser import guess_header, parse_import_file
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_cutting_api import _auth, _client_access

FIXTURES = Path(__file__).parent / "fixtures" / "cutting_import"


def _csv_bytes(text: str, *, encoding: str = "utf-8") -> bytes:
    return text.encode(encoding)


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


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

    with pytest.raises(ImportParseError) as too_many:
        parse_import_file(
            filename="too_many.csv",
            content=_csv_bytes("L;W;Qty\n100;100;101\n"),
            options=ImportParseOptions(
                skip_rows=1,
                mapping={"length_mm": 0, "width_mm": 1, "quantity": 2},
            ),
        )
    assert too_many.value.code == "too_many_parts"


def test_encoding_fallback_and_delimiter_tie_rule() -> None:
    assert decode_csv_text("Длина".encode("cp1251")) == "Длина"
    assert sniff_csv_delimiter("A;B,C\n1;2,3\n") == ";"


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
    assert "source_format" not in detected.json()
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
