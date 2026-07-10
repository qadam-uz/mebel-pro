"""Shared helpers for cutting import parsers."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from app.modules.cutting.imports.base import SkipReason, WarningCode

DimensionError = Literal["non_numeric", "dimension_not_positive", "dimension_too_large"]

_SPACE_RE = re.compile(r"[\s\u00a0\u2009]+")


@dataclass
class GroupRegistry:
    prefix: str
    special_labels: dict[str, str]
    counts: dict[str, int]
    labels: dict[str, str]
    keys_by_distinct: dict[str, str]

    def key_for(self, value: Any) -> str:
        text = cell_text(value)
        if not text:
            key = "__unspecified__"
            self.counts[key] = self.counts.get(key, 0) + 1
            self.labels[key] = self.special_labels[key]
            return key
        distinct = distinct_key(text)
        existing_key = self.keys_by_distinct.get(distinct)
        if existing_key is None:
            key = f"{self.prefix}{len(self.keys_by_distinct) + 1}"
            self.keys_by_distinct[distinct] = key
            self.labels[key] = text
        else:
            key = existing_key
        self.counts[key] = self.counts.get(key, 0) + 1
        return key

    def count_special(self, key: str) -> str:
        self.counts[key] = self.counts.get(key, 0) + 1
        self.labels[key] = self.special_labels[key]
        return key


def cell_text(value: Any) -> str:
    if value is None:
        return ""
    return _SPACE_RE.sub(" ", str(value).strip())


def distinct_key(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip()).casefold()


def parse_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        numeric = float(value)
    elif isinstance(value, str):
        text = _SPACE_RE.sub("", value.strip()).replace(",", ".")
        if not text:
            return None
        try:
            numeric = float(text)
        except ValueError:
            return None
    else:
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def parse_dimension(
    value: Any,
    row_number: int,
    warnings: dict[WarningCode, set[int]],
) -> tuple[int | None, DimensionError | None]:
    numeric = parse_number(value)
    if numeric is None:
        return None, "non_numeric"
    if numeric <= 0:
        return None, "dimension_not_positive"
    if numeric > 10_000:
        return None, "dimension_too_large"
    rounded = int(Decimal(str(numeric)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if not math.isclose(float(rounded), numeric):
        add_warning(warnings, "dimension_rounded", row_number)
    return rounded, None


def parse_quantity(
    value: Any,
    row_number: int,
    mapped: bool,
    warnings: dict[WarningCode, set[int]],
) -> tuple[int | None, SkipReason | None]:
    if not mapped:
        return 1, None
    if not cell_text(value):
        add_warning(warnings, "quantity_defaulted", row_number)
        return 1, None
    numeric = parse_number(value)
    if numeric is None:
        return None, "non_numeric_quantity"
    if not numeric.is_integer():
        return None, "quantity_not_integer"
    quantity = int(numeric)
    if quantity < 1:
        return None, "quantity_not_positive"
    return quantity, None


def format_thickness_hint(values: set[float]) -> str | None:
    if not values:
        return None
    return " / ".join(format_thickness_value(value) for value in sorted(values))


def format_thickness_value(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return format(Decimal(str(value)).normalize(), "f").rstrip("0").rstrip(".")


def add_warning(warnings: dict[WarningCode, set[int]], code: WarningCode, row: int) -> None:
    warnings.setdefault(code, set()).add(row)
