"""CSV cutting import parser."""

from __future__ import annotations

import csv
import io
from typing import Any, Literal

from app.modules.cutting.imports.base import (
    IMPORT_ROLES,
    MAX_IMPORT_FILE_BYTES,
    MAX_IMPORT_PIECES,
    MAX_SCAN_COLS,
    MAX_SCAN_ROWS,
    PREVIEW_COLS,
    PREVIEW_ROWS,
    ImportEdgeMaterialGroup,
    ImportedPart,
    ImportNeedsMappingResponse,
    ImportPanelMaterialGroup,
    ImportParsedResponse,
    ImportParseError,
    ImportParseOptions,
    ImportParseResponse,
    ImportRole,
    ImportSkippedRow,
    ImportWarning,
    SkipReason,
    WarningCode,
)
from app.modules.cutting.imports.common import (
    GroupRegistry,
    add_warning,
    cell_text,
    format_thickness_hint,
    parse_dimension,
    parse_number,
    parse_quantity,
)
from app.modules.cutting.imports.detect import (
    decode_csv_text,
    sniff_csv_delimiter,
    sniff_format,
)

Grid = list[list[Any]]
EdgeSide = Literal["top", "bottom", "left", "right"]

_HEADER_TOKENS: dict[ImportRole, tuple[str, ...]] = {
    "length_mm": ("длина", "length", "l", "uzunlik", "bo'y", "boy"),
    "width_mm": ("ширина", "width", "w", "eni", "kenglik"),
    "quantity": ("количество", "кол-во", "кол.", "шт", "qty", "soni", "dona", "miqdor"),
    "material": ("материал", "наименование материала", "material", "плита", "лдсп"),
    "thickness_mm": ("толщина", "thickness", "qalinlik"),
    "follow_grain": ("текстура", "ориентация", "tola", "grain", "направление"),
    "edge_top": ("д1", "l1", "кромка д1", "облицовка д1", "кромка l1"),
    "edge_bottom": ("д2", "l2", "кромка д2", "облицовка д2", "кромка l2"),
    "edge_left": ("ш1", "w1", "кромка ш1", "облицовка ш1", "кромка w1"),
    "edge_right": ("ш2", "w2", "кромка ш2", "облицовка ш2", "кромка w2"),
}

_TRUTHY_GRAIN = {"да", "есть", "+", "1", "true", "ha", "v", "✓", "x", "\u0445"}
_FALSY_GRAIN = {"нет", "-", "0", "false", "yo'q", "yoq"}
_FALSY_EDGE = {"", "-", "0", "нет", "yo'q", "yoq"}


def parse_import_file(
    *,
    filename: str | None,
    content: bytes,
    options: ImportParseOptions | None = None,
) -> ImportParseResponse:
    _ensure_file_size(content)
    parse_options = options or ImportParseOptions()
    source_format = sniff_format(content, filename)
    if source_format == "map_2dplace":
        from app.modules.cutting.imports.map_2dplace import parse_map_2dplace

        return parse_map_2dplace(content, filename)
    if source_format == "bazis_xml":
        from app.modules.cutting.imports.bazis_xml import parse_bazis_xml

        return parse_bazis_xml(content)
    grid = _read_csv(content)
    if parse_options.mapping is None:
        guessed_mapping, guessed_skip_rows = guess_header(grid)
        return ImportNeedsMappingResponse(
            grid=_preview_grid(grid),
            guessed_mapping=guessed_mapping,
            guessed_skip_rows=guessed_skip_rows,
        )
    mapping = _validate_mapping(parse_options.mapping)
    return _parse_grid(grid, mapping, parse_options.skip_rows)


def guess_header(grid: Grid) -> tuple[dict[ImportRole, int], int]:
    for row_index, row in enumerate(grid[:5], start=1):
        mapping: dict[ImportRole, int] = {}
        for col_index, value in enumerate(row[:MAX_SCAN_COLS]):
            role = _match_header_role(value)
            if role and role not in mapping:
                mapping[role] = col_index
        if len(mapping) >= 2:
            return mapping, row_index
    return {}, 0


def _ensure_file_size(content: bytes) -> None:
    if len(content) > MAX_IMPORT_FILE_BYTES:
        raise ImportParseError("file_too_large", "Fayl 1 MB dan katta")
    if len(content) == 0:
        raise ImportParseError("empty_file", "Fayl bo'sh")


def _read_csv(content: bytes) -> Grid:
    text = decode_csv_text(content)
    delimiter = sniff_csv_delimiter(text)
    rows: Grid = []
    reader = csv.reader(io.StringIO(text), delimiter=delimiter, quotechar='"')
    for index, row in enumerate(reader):
        if index >= MAX_SCAN_ROWS:
            break
        rows.append(row[:MAX_SCAN_COLS])
    if not _has_non_empty_cell(rows):
        raise ImportParseError("empty_file", "Fayl bo'sh")
    return rows


def _preview_grid(grid: Grid) -> list[list[str | None]]:
    preview: list[list[str | None]] = []
    for row in grid[:PREVIEW_ROWS]:
        preview.append([cell_text(value) or None for value in row[:PREVIEW_COLS]])
    return preview


def _validate_mapping(mapping: dict[ImportRole, int]) -> dict[ImportRole, int]:
    unknown = [role for role in mapping if role not in IMPORT_ROLES]
    required_missing = [role for role in ("length_mm", "width_mm") if role not in mapping]
    seen_columns: dict[int, ImportRole] = {}
    duplicate_columns: list[int] = []
    out_of_range: list[int] = []
    for role, column in mapping.items():
        if column < 0 or column >= MAX_SCAN_COLS:
            out_of_range.append(column)
        if column in seen_columns:
            duplicate_columns.append(column)
        seen_columns[column] = role
    if unknown or required_missing or duplicate_columns or out_of_range:
        raise ImportParseError(
            "invalid_mapping",
            "Invalid column mapping",
            details={
                "unknown_roles": unknown,
                "missing_roles": required_missing,
                "duplicate_columns": duplicate_columns,
                "out_of_range_columns": out_of_range,
            },
        )
    return mapping


def _parse_grid(
    grid: Grid,
    mapping: dict[ImportRole, int],
    skip_rows: int,
) -> ImportParsedResponse:
    panel_groups = GroupRegistry(
        "m",
        {"__all__": "Butun fayl uchun material", "__unspecified__": "Material ko'rsatilmagan"},
        {},
        {},
        {},
    )
    edge_groups = GroupRegistry("e", {}, {}, {}, {})
    warnings: dict[WarningCode, set[int]] = {}
    skipped_rows: list[ImportSkippedRow] = []
    parts: list[ImportedPart] = []
    panel_thicknesses: dict[str, set[float]] = {}
    for row_number, row in enumerate(grid, start=1):
        if row_number <= skip_rows:
            continue
        if _mapped_cells_empty(row, mapping):
            continue
        part, reason, thickness_hint = _parse_row(
            row,
            row_number,
            mapping,
            panel_groups,
            edge_groups,
            warnings,
        )
        if reason is not None:
            skipped_rows.append(
                ImportSkippedRow(row=row_number, reason=reason, preview=_row_preview(row))
            )
            continue
        if part is not None:
            parts.append(part)
            if thickness_hint is not None:
                panel_thicknesses.setdefault(part.material_key, set()).add(thickness_hint)
    total_pieces = sum(part.quantity for part in parts)
    if total_pieces > MAX_IMPORT_PIECES:
        raise ImportParseError(
            "too_many_parts",
            f"Faylda {total_pieces} dona detal — bir optimallashtirishga eng ko'pi 300 dona. "
            "Faylni bo'lib yuklang",
            details={"total_pieces": total_pieces},
        )
    return ImportParsedResponse(
        parts=parts,
        panel_materials=[
            ImportPanelMaterialGroup(
                key=key,
                label=panel_groups.labels[key],
                part_count=count,
                thickness_hint=format_thickness_hint(panel_thicknesses.get(key, set())),
            )
            for key, count in panel_groups.counts.items()
        ],
        edge_materials=[
            ImportEdgeMaterialGroup(key=key, label=edge_groups.labels[key], side_count=count)
            for key, count in edge_groups.counts.items()
        ],
        skipped_rows=skipped_rows,
        warnings=[
            ImportWarning(code=code, rows=sorted(rows))
            for code, rows in sorted(warnings.items(), key=lambda item: item[0])
        ],
        total_parts=len(parts),
        total_pieces=total_pieces,
    )


def _parse_row(
    row: list[Any],
    row_number: int,
    mapping: dict[ImportRole, int],
    panel_groups: GroupRegistry,
    edge_groups: GroupRegistry,
    warnings: dict[WarningCode, set[int]],
) -> tuple[ImportedPart | None, SkipReason | None, float | None]:
    length, length_error = parse_dimension(
        _mapped_value(row, mapping["length_mm"]),
        row_number,
        warnings,
    )
    if length_error is not None:
        return None, "non_numeric_length" if length_error == "non_numeric" else length_error, None
    width, width_error = parse_dimension(
        _mapped_value(row, mapping["width_mm"]),
        row_number,
        warnings,
    )
    if width_error is not None:
        return None, "non_numeric_width" if width_error == "non_numeric" else width_error, None
    quantity, quantity_error = parse_quantity(
        _mapped_value(row, mapping.get("quantity")),
        row_number,
        "quantity" in mapping,
        warnings,
    )
    if quantity_error is not None:
        return None, quantity_error, None
    follow_grain = _parse_follow_grain(
        _mapped_value(row, mapping.get("follow_grain")),
        row_number,
        warnings,
    )
    if "material" in mapping:
        material_key = panel_groups.key_for(_mapped_value(row, mapping["material"]))
    else:
        material_key = panel_groups.count_special("__all__")
    thickness_hint = _parse_thickness_hint(_mapped_value(row, mapping.get("thickness_mm")))
    edges: dict[EdgeSide, str | None] = {
        "top": _edge_key(row, mapping.get("edge_top"), edge_groups),
        "bottom": _edge_key(row, mapping.get("edge_bottom"), edge_groups),
        "left": _edge_key(row, mapping.get("edge_left"), edge_groups),
        "right": _edge_key(row, mapping.get("edge_right"), edge_groups),
    }
    return (
        ImportedPart(
            row=row_number,
            length_mm=length or 0,
            width_mm=width or 0,
            quantity=quantity or 1,
            material_key=material_key,
            follow_grain=follow_grain,
            edges=edges,
        ),
        None,
        thickness_hint,
    )


def _parse_follow_grain(
    value: Any,
    row_number: int,
    warnings: dict[WarningCode, set[int]],
) -> bool:
    text = cell_text(value).casefold()
    if not text:
        return True
    if text in _TRUTHY_GRAIN:
        return True
    if text in _FALSY_GRAIN:
        return False
    add_warning(warnings, "grain_token_unknown", row_number)
    return True


def _parse_thickness_hint(value: Any) -> float | None:
    numeric = parse_number(value)
    if numeric is None or numeric <= 0:
        return None
    return numeric


def _edge_key(row: list[Any], column: int | None, edge_groups: GroupRegistry) -> str | None:
    if column is None:
        return None
    value = _mapped_value(row, column)
    text = cell_text(value)
    if text.casefold() in _FALSY_EDGE:
        return None
    return edge_groups.key_for(value)


def _mapped_cells_empty(row: list[Any], mapping: dict[ImportRole, int]) -> bool:
    return all(not cell_text(_mapped_value(row, column)) for column in mapping.values())


def _mapped_value(row: list[Any], column: int | None) -> Any:
    if column is None or column >= len(row):
        return None
    return row[column]


def _row_preview(row: list[Any]) -> str:
    for value in row:
        text = cell_text(value)
        if text:
            return text[:40]
    return ""


def _has_non_empty_cell(grid: Grid) -> bool:
    return any(cell_text(value) for row in grid for value in row)


def _match_header_role(value: Any) -> ImportRole | None:
    text = cell_text(value).casefold()
    if not text:
        return None
    for role, tokens in _HEADER_TOKENS.items():
        for token in tokens:
            normalized = token.casefold()
            if len(normalized) == 1:
                matched = text == normalized
            else:
                matched = text == normalized or text.startswith(normalized)
            if matched:
                return role
    return None
