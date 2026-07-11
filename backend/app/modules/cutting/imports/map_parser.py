"""2D-Place ``.map`` parser ported from the MapsPrint reader."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path


class MapParseError(Exception):
    """Raised when bytes are not a supported 2D-Place map file."""


@dataclass(frozen=True)
class MapRecord:
    x: int
    y: int
    width: int
    height: int
    name: str
    edges: tuple[bool, bool, bool, bool]
    is_waste: bool = False
    is_remainder: bool = False


@dataclass(frozen=True)
class MapSheet:
    name: str
    width_mm: int
    height_mm: int
    records: list[MapRecord]


@dataclass(frozen=True)
class MapFile:
    description: str
    customer_name: str
    order_type: str
    sheets: list[MapSheet]


MAGIC_BYTES = b"KV_MAP"
ARIAL_PATTERN = b"\x05Arial"
SHEET_PATTERN = "Лист".encode("cp1251")
REMAINDER_MARKER = b"\x01\xff\x00\x00"
DUPLICATE_SHEET_RE = re.compile(
    r"^(?:(?P<prefix>\d+)\s*:\s*)?Лист[^\d]*(?P<start>\d+)\s*-\s*(?P<end>\d+)\s*$",
    re.IGNORECASE,
)

DESCRIPTION_OFFSET = 10
SHEET_DIMENSION_OFFSET = 156
FIRST_RECORD_COORDS_OFFSET = 140
FIRST_RECORD_WASTE_OFFSET = 157
NORMAL_RECORD_COORDS_OFFSET = 127
NORMAL_RECORD_WASTE_OFFSET = 144
SHORT_RECORD_THRESHOLD = 120
LONG_RECORD_THRESHOLD = 200
EDGE_CODE_OFFSETS = (41, 45, 49, 53)


def parse_map_file(content: bytes, filename: str | None = None) -> MapFile:
    _validate_header(content)
    sheet_positions = _find_all(content, SHEET_PATTERN)
    arial_positions = _find_all(content, ARIAL_PATTERN)
    parsed_sheets: list[MapSheet] = []

    for sheet_index, sheet_pattern_offset in enumerate(sheet_positions):
        sheet_end = (
            sheet_positions[sheet_index + 1]
            if sheet_index + 1 < len(sheet_positions)
            else len(content)
        )
        sheet_header_start = _sheet_header_start(content, sheet_pattern_offset)
        dims_offset = sheet_header_start + SHEET_DIMENSION_OFFSET
        if dims_offset + 4 > len(content):
            continue
        width = _read_i16(content, dims_offset)
        height = _read_i16(content, dims_offset + 2)
        if width is None or height is None or width <= 0 or height <= 0:
            continue

        sheet_arials = [
            offset for offset in arial_positions if offset >= dims_offset and offset < sheet_end
        ]
        records: list[MapRecord] = []
        pending_edge_index: int | None = None
        for record_index, record_start in enumerate(sheet_arials):
            record_end = (
                sheet_arials[record_index + 1]
                if record_index + 1 < len(sheet_arials)
                else sheet_end
            )
            record_length = record_end - record_start
            if record_length > LONG_RECORD_THRESHOLD or record_length < SHORT_RECORD_THRESHOLD:
                continue

            is_first_record = record_index == 0
            coords_offset = record_start + (
                FIRST_RECORD_COORDS_OFFSET if is_first_record else NORMAL_RECORD_COORDS_OFFSET
            )
            waste_offset = record_start + (
                FIRST_RECORD_WASTE_OFFSET if is_first_record else NORMAL_RECORD_WASTE_OFFSET
            )
            record = _read_record(
                content,
                record_start,
                coords_offset,
                waste_offset,
                width,
                height,
            )
            if record is None:
                continue

            companion_edges = _read_companion_edges(content, record_start, record_length)
            if pending_edge_index is not None and companion_edges is not None:
                previous = records[pending_edge_index]
                records[pending_edge_index] = MapRecord(
                    x=previous.x,
                    y=previous.y,
                    width=previous.width,
                    height=previous.height,
                    name=previous.name,
                    edges=companion_edges,
                    is_waste=previous.is_waste,
                    is_remainder=previous.is_remainder,
                )

            records.append(record)
            pending_edge_index = None if record.is_waste else len(records) - 1

        parsed_sheets.append(
            MapSheet(
                name=_read_sheet_name(
                    content, sheet_header_start, sheet_pattern_offset, sheet_index + 1
                ),
                width_mm=width,
                height_mm=height,
                records=records,
            )
        )

    sheets = [sheet for source in parsed_sheets for sheet in _expand_duplicate_sheets(source)]
    if not sheets:
        raise MapParseError("Map file contains no sheets")
    if not any(not record.is_waste for sheet in sheets for record in sheet.records):
        raise MapParseError("Map file contains no parts")

    customer_name, order_type = _filename_metadata(filename)
    return MapFile(
        description=_read_null_terminated(content, DESCRIPTION_OFFSET, 200),
        customer_name=customer_name,
        order_type=order_type,
        sheets=sheets,
    )


def _validate_header(content: bytes) -> None:
    if len(content) < 16:
        raise MapParseError(f"File too small: {len(content)} bytes")
    if content[0] != len(MAGIC_BYTES):
        raise MapParseError("Invalid magic length byte")
    if content[1 : 1 + len(MAGIC_BYTES)] != MAGIC_BYTES:
        raise MapParseError("Invalid magic string")


def _read_record(
    content: bytes,
    record_start: int,
    coords_offset: int,
    waste_offset: int,
    sheet_width: int,
    sheet_height: int,
) -> MapRecord | None:
    if coords_offset < 0 or coords_offset + 8 > len(content):
        return None
    if waste_offset < 0 or waste_offset + 4 > len(content):
        return None
    x = _read_i16(content, coords_offset)
    y = _read_i16(content, coords_offset + 2)
    width = _read_i16(content, coords_offset + 4)
    height = _read_i16(content, coords_offset + 6)
    if x is None or y is None or width is None or height is None:
        return None
    if not _valid_rect(x, y, width, height, sheet_width, sheet_height):
        return None
    marker = content[waste_offset : waste_offset + 4]
    is_remainder = marker == REMAINDER_MARKER
    is_waste = is_remainder or _legacy_waste_marker(content, record_start, waste_offset)
    name = "" if is_waste else _read_part_name(content, record_start, coords_offset)
    return MapRecord(
        x=x,
        y=y,
        width=width,
        height=height,
        name=name,
        edges=(False, False, False, False),
        is_waste=is_waste,
        is_remainder=is_remainder,
    )


def _valid_rect(
    x: int,
    y: int,
    width: int,
    height: int,
    sheet_width: int,
    sheet_height: int,
) -> bool:
    return (
        x >= 0
        and y >= 0
        and width > 0
        and height > 0
        and x <= sheet_width
        and y <= sheet_height
        and width <= sheet_width
        and height <= sheet_height
        and x + width <= sheet_width + 5
        and y + height <= sheet_height + 5
    )


def _legacy_waste_marker(content: bytes, record_start: int, waste_offset: int) -> bool:
    return (
        record_start + 73 < len(content)
        and waste_offset + 4 <= len(content)
        and content[record_start + 73] == 0x03
        and content[waste_offset : waste_offset + 4] == b"\x01\x00\x00\x00"
    )


def _read_companion_edges(
    content: bytes,
    record_start: int,
    record_length: int,
) -> tuple[bool, bool, bool, bool] | None:
    raw_codes: list[int] = []
    for relative in EDGE_CODE_OFFSETS:
        offset = record_start + relative
        if offset >= len(content) or offset >= record_start + record_length:
            return None
        raw_codes.append(content[offset])
    left, right, top, bottom = (code != 0 for code in raw_codes)
    return top, bottom, left, right


def _read_part_name(content: bytes, record_start: int, coords_offset: int) -> str:
    search_start = record_start + len(ARIAL_PATTERN)
    search_end = min(coords_offset, len(content))
    last_candidate = ""
    last_non_font_candidate = ""
    for offset in range(search_start, max(search_start, search_end - 1)):
        declared_length = content[offset]
        if (
            declared_length <= 0
            or declared_length > 64
            or offset + 1 + declared_length > search_end
        ):
            continue
        candidate_bytes = content[offset + 1 : offset + 1 + declared_length]
        if b"\x00" in candidate_bytes:
            continue
        candidate = candidate_bytes.decode("cp1251", errors="ignore").strip()
        if not candidate:
            continue
        last_candidate = candidate
        if candidate.casefold() != "arial":
            last_non_font_candidate = candidate
    return last_non_font_candidate or last_candidate


def _sheet_header_start(content: bytes, pattern_offset: int) -> int:
    start = pattern_offset
    for offset in range(pattern_offset - 1, max(-1, pattern_offset - 25), -1):
        if content[offset] == 0:
            start = offset + 1
            break
    return start


def _read_sheet_name(
    content: bytes,
    start: int,
    pattern_offset: int,
    fallback_index: int,
) -> str:
    end = pattern_offset
    while end < len(content) and content[end] != 0:
        end += 1
    if start < end and content[start] > 0:
        declared_length = content[start]
        content_start = start + 1
        if content_start + declared_length <= end:
            return content[content_start : content_start + declared_length].decode(
                "cp1251",
                errors="ignore",
            )
    if start < end:
        return content[start:end].decode("cp1251", errors="ignore")
    return f"{fallback_index}: Лист {fallback_index}"


def _expand_duplicate_sheets(sheet: MapSheet) -> list[MapSheet]:
    match = DUPLICATE_SHEET_RE.match(sheet.name.strip())
    if not match:
        return [sheet]
    start = int(match.group("start"))
    end = int(match.group("end"))
    if start <= 0 or end < start:
        return [sheet]
    return [
        MapSheet(
            name=f"{sheet_number}: Лист {sheet_number}",
            width_mm=sheet.width_mm,
            height_mm=sheet.height_mm,
            records=copy.deepcopy(sheet.records),
        )
        for sheet_number in range(start, end + 1)
    ]


def _filename_metadata(filename: str | None) -> tuple[str, str]:
    base_name = Path(filename or "").stem.strip()
    if not base_name:
        return "", ""
    if "__" not in base_name:
        return base_name, ""
    customer_name, order_type = base_name.split("__", 1)
    return customer_name.strip(), order_type.strip()


def _read_i16(content: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 2 > len(content):
        return None
    return int.from_bytes(content[offset : offset + 2], "little", signed=True)


def _read_null_terminated(content: bytes, offset: int, max_length: int) -> str:
    if offset < 0 or offset >= len(content):
        return ""
    limit = min(offset + max_length, len(content))
    end = offset
    while end < limit and content[end] != 0:
        end += 1
    if end <= offset:
        return ""
    return content[offset:end].decode("cp1251", errors="ignore")


def _find_all(content: bytes, pattern: bytes) -> list[int]:
    positions: list[int] = []
    if not pattern or len(content) < len(pattern):
        return positions
    last_start = len(content) - len(pattern)
    for offset in range(last_start + 1):
        if content[offset : offset + len(pattern)] == pattern:
            positions.append(offset)
    return positions
