"""Content detection and CSV text sniffing for cutting imports."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Literal
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.modules.cutting.imports.base import ImportParseError, SourceFormat

XLSX_ZIP_MAGIC = b"PK\x03\x04"
OLE2_MAGIC = b"\xd0\xcf\x11\xe0"
MAP_MAGIC = b"\x06KV_MAP"
XML_UNSUPPORTED_MESSAGE = (
    "Bu XML «Спецификация в XML» formati emas. БАЗИС-Мебельщик'dan "
    "Формирование проекта → «Спецификация в XML» orqali saqlang."
)


def unsupported_format_message() -> str:
    return (
        "Bu fayl turi qo'llab-quvvatlanmaydi — faqat CSV, XML yoki 2D-Place MAP. "
        "БАЗИС-Мебельщик'da «Спецификация в CSV»/«Спецификация в XML» orqali yoki "
        "2D-Place'dan .map qilib saqlang."
    )


def sniff_format(content: bytes, filename: str | None = None) -> SourceFormat:
    if content.startswith(XLSX_ZIP_MAGIC) or content.startswith(OLE2_MAGIC):
        raise ImportParseError(
            "unsupported_format",
            unsupported_format_message(),
        )
    if content.startswith(MAP_MAGIC):
        return "map_2dplace"
    if _looks_like_xml(content):
        try:
            root = ElementTree.fromstring(content)
        except DefusedXmlException as exc:
            raise ImportParseError("invalid_file", "XML faylni o'qib bo'lmadi") from exc
        except ParseError as exc:
            raise ImportParseError("invalid_file", "XML faylni o'qib bo'lmadi") from exc
        if _local_name(root.tag) != "Проект":
            raise ImportParseError("unsupported_format", XML_UNSUPPORTED_MESSAGE)
        return "bazis_xml"
    ensure_csv(content, filename)
    return "csv"


def ensure_csv(content: bytes, filename: str | None = None) -> None:
    if content.startswith(XLSX_ZIP_MAGIC) or content.startswith(OLE2_MAGIC):
        raise ImportParseError(
            "unsupported_format",
            unsupported_format_message(),
        )
    if _extension(filename) not in {"", ".csv"}:
        raise ImportParseError("unsupported_format", unsupported_format_message())


def decode_csv_text(content: bytes) -> str:
    candidates: tuple[str, ...]
    if content.startswith(b"\xff\xfe") or content.startswith(b"\xfe\xff"):
        candidates = ("utf-16",)
    else:
        candidates = ("utf-8-sig", "cp1251")
    for encoding in candidates:
        try:
            text = content.decode(encoding, errors="strict")
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - cp1251 is exhaustive for arbitrary bytes
        raise ImportParseError("unsupported_format", unsupported_format_message())
    if "\x00" in text or any(ord(char) < 32 and char not in "\r\n\t" for char in text):
        raise ImportParseError("unsupported_format", unsupported_format_message())
    return text


def sniff_csv_delimiter(text: str) -> str:
    sample = text[:4096]
    first = next((line for line in text.splitlines() if line.strip()), "")
    counts = {delimiter: first.count(delimiter) for delimiter in (";", "\t", ",")}
    max_count = max(counts.values()) if counts else 0
    if max_count > 0 and sum(1 for count in counts.values() if count == max_count) > 1:
        return ";"
    try:
        return csv.Sniffer().sniff(sample, delimiters=";\t,").delimiter
    except csv.Error:
        best_count = max(counts.values())
        for delimiter in (";", "\t", ","):
            if counts[delimiter] == best_count:
                return delimiter
        return ";"


def _extension(filename: str | None) -> str:
    return Path(filename or "").suffix.casefold()


def _looks_like_xml(content: bytes) -> bool:
    leading = _leading_text(content).lstrip()
    return leading.startswith("<?xml") or leading.startswith("<Проект") or leading.startswith("<")


def _leading_text(content: bytes) -> str:
    sample = content[:256]
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return sample.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
    return ""


def _local_name(tag: str | Literal[""]) -> str:
    text = str(tag)
    if "}" in text:
        return text.rsplit("}", 1)[1]
    return text
