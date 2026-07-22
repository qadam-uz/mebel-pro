"""БАЗИС-Мебельщик ``Спецификация в XML`` cutting import parser."""
# ruff: noqa: RUF001

from __future__ import annotations

from typing import Literal
from xml.etree.ElementTree import Element, ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.modules.cutting.imports.base import (
    MAX_IMPORT_PIECES,
    ImportEdgeMaterialGroup,
    ImportedPart,
    ImportPanelMaterialGroup,
    ImportParsedResponse,
    ImportParseError,
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
from app.modules.cutting.imports.detect import XML_UNSUPPORTED_MESSAGE

EdgeSide = Literal["top", "bottom", "left", "right"]

_PANEL_GROUP_LABELS = {
    "__unspecified__": "Material ko'rsatilmagan",
}
_EDGE_LISTS: tuple[tuple[str, EdgeSide], ...] = (
    ("СписокКромок1", "top"),
    ("СписокКромок2", "bottom"),
    ("СписокКромок3", "left"),
    ("СписокКромок4", "right"),
)


def parse_bazis_xml(content: bytes) -> ImportParsedResponse:
    try:
        root = ElementTree.fromstring(content)
    except DefusedXmlException as exc:
        raise ImportParseError("invalid_file", "XML faylni o'qib bo'lmadi") from exc
    except ParseError as exc:
        raise ImportParseError("invalid_file", "XML faylni o'qib bo'lmadi") from exc
    if _local_name(root.tag) != "Проект":
        raise ImportParseError("unsupported_format", XML_UNSUPPORTED_MESSAGE)

    panel_groups = GroupRegistry("m", _PANEL_GROUP_LABELS, {}, {}, {})
    edge_groups = GroupRegistry("e", {}, {}, {}, {})
    panel_thicknesses: dict[str, set[float]] = {}
    warnings: dict[WarningCode, set[int]] = {}
    skipped_rows: list[ImportSkippedRow] = []
    parts: list[ImportedPart] = []
    ignored_object_count = 0
    row_number = 0

    for product in _iter_descendants(root, "Изделие"):
        product_quantity, product_quantity_error = _product_quantity(product)
        for obj in _iter_product_objects(product):
            if _child_text(obj, "ТипОбъекта") != "Панель":
                ignored_object_count += 1
                continue
            row_number += 1
            if product_quantity_error is not None:
                skipped_rows.append(
                    ImportSkippedRow(
                        row=row_number,
                        reason=product_quantity_error,
                        preview=_object_preview(obj),
                    )
                )
                continue
            part, skip_reason, thickness_hint = _parse_panel_object(
                obj,
                row_number,
                product_quantity,
                panel_groups,
                edge_groups,
                warnings,
            )
            if skip_reason is not None:
                skipped_rows.append(
                    ImportSkippedRow(
                        row=row_number,
                        reason=skip_reason,
                        preview=_object_preview(obj),
                    )
                )
                continue
            assert part is not None
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
        source_format="bazis_xml",
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
        ignored_object_count=ignored_object_count,
        total_parts=len(parts),
        total_pieces=total_pieces,
    )


def _parse_panel_object(
    obj: Element,
    row_number: int,
    product_quantity: int,
    panel_groups: GroupRegistry,
    edge_groups: GroupRegistry,
    warnings: dict[WarningCode, set[int]],
) -> tuple[ImportedPart, None, float | None] | tuple[None, SkipReason, None]:
    length, length_error = parse_dimension(_dimension_text(obj, "Длина"), row_number, warnings)
    if length_error is not None:
        return None, "non_numeric_length" if length_error == "non_numeric" else length_error, None
    width, width_error = parse_dimension(_dimension_text(obj, "Ширина"), row_number, warnings)
    if width_error is not None:
        return None, "non_numeric_width" if width_error == "non_numeric" else width_error, None

    quantity_text = _child_text(obj, "Количество")
    part_quantity, quantity_error = parse_quantity(
        quantity_text,
        row_number,
        mapped=True,
        warnings=warnings,
    )
    if quantity_error is not None:
        return None, quantity_error, None

    material_key = panel_groups.key_for(_material_label(_child(obj, "ОсновнойМатериал")))
    thickness_hint = _thickness_hint(_child(obj, "ОсновнойМатериал"))
    _add_geometry_warnings(obj, row_number, warnings)

    return (
        ImportedPart(
            row=row_number,
            length_mm=length or 0,
            width_mm=width or 0,
            quantity=(part_quantity or 1) * product_quantity,
            material_key=material_key,
            follow_grain=_follow_grain(obj),
            edges=_edge_keys(obj, edge_groups, warnings, row_number),
        ),
        None,
        thickness_hint,
    )


def _product_quantity(product: Element) -> tuple[int, SkipReason | None]:
    text = _child_text(product, "Количество")
    if not text:
        return 1, None
    warnings: dict[WarningCode, set[int]] = {}
    quantity, error = parse_quantity(text, 0, mapped=True, warnings=warnings)
    return quantity or 1, error


def _dimension_text(obj: Element, base_name: str) -> str:
    preferred = _child_text(obj, f"{base_name}_детали_без_облицовки")
    return preferred or _child_text(obj, base_name)


def _follow_grain(obj: Element) -> bool:
    text = _child_text(obj, "ОриентацияТекстуры")
    return text in {"Горизонтальная", "Вертикальная"}


def _edge_keys(
    obj: Element,
    edge_groups: GroupRegistry,
    warnings: dict[WarningCode, set[int]],
    row_number: int,
) -> dict[EdgeSide, str | None]:
    edges: dict[EdgeSide, str | None] = {
        "top": None,
        "bottom": None,
        "left": None,
        "right": None,
    }
    for list_name, side in _EDGE_LISTS:
        edge_list = _child(obj, list_name)
        edge = _first_child(edge_list, "Кромка") if edge_list is not None else None
        if edge is not None:
            edges[side] = edge_groups.key_for(_material_label(edge))
    see_drawing = _child(obj, "СписокКромокСМЧертеж")
    if see_drawing is not None and _has_content(see_drawing):
        add_warning(warnings, "edge_see_drawing", row_number)
    return edges


def _add_geometry_warnings(
    obj: Element,
    row_number: int,
    warnings: dict[WarningCode, set[int]],
) -> None:
    if _child_text(obj, "Прямоугольная").casefold() == "n":
        add_warning(warnings, "non_rectangular", row_number)
    holes = _child(obj, "Отверстия")
    if holes is not None and _first_child(holes, "Отверстие") is not None:
        add_warning(warnings, "ignored_holes", row_number)
    grooves = _child(obj, "СписокПазов")
    if grooves is not None and _first_child(grooves, "Паз") is not None:
        add_warning(warnings, "ignored_grooves", row_number)


def _material_label(node: Element | None) -> str:
    if node is None:
        return ""
    name = _child_text(node, "Наименование") or cell_text(node.text)
    code = _child_text(node, "Код")
    return " ".join(part for part in (name, code) if part)


def _thickness_hint(node: Element | None) -> float | None:
    if node is None:
        return None
    value = parse_number(_child_text(node, "Толщина"))
    return value if value is not None and value > 0 else None


def _object_preview(obj: Element) -> str:
    return (
        _child_text(obj, "Наименование")
        or _material_label(_child(obj, "ОсновнойМатериал"))
        or _child_text(obj, "ТипОбъекта")
    )[:40]


def _iter_product_objects(product: Element) -> list[Element]:
    elements = _child(product, "СписокЭлементов")
    if elements is None:
        return []
    return [child for child in list(elements) if _local_name(child.tag) == "Объект"]


def _iter_descendants(root: Element, name: str) -> list[Element]:
    return [element for element in root.iter() if _local_name(element.tag) == name]


def _child(node: Element, name: str) -> Element | None:
    return next((child for child in list(node) if _local_name(child.tag) == name), None)


def _first_child(node: Element | None, name: str) -> Element | None:
    if node is None:
        return None
    return next((child for child in list(node) if _local_name(child.tag) == name), None)


def _child_text(node: Element, name: str) -> str:
    child = _child(node, name)
    return "" if child is None else cell_text(child.text)


def _has_content(node: Element) -> bool:
    return bool(cell_text(node.text)) or any(True for _ in list(node))


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag
