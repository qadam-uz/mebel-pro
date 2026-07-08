"""Content detection and CSV text sniffing for cutting imports."""

from __future__ import annotations

import csv
from pathlib import Path

from app.modules.cutting.imports.base import ImportParseError

XLSX_ZIP_MAGIC = b"PK\x03\x04"
OLE2_MAGIC = b"\xd0\xcf\x11\xe0"


def unsupported_format_message() -> str:
    return (
        "Bu fayl turi qo'llab-quvvatlanmaydi — faqat CSV. БАЗИС-Мебельщик'da "
        "«Спецификация в CSV» orqali, Excel'da «Сохранить как → CSV» qilib saqlang."
    )


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
