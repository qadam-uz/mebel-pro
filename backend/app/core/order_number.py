"""Display and search rules for `Order.order_number`.

The number is the client-workshop handle: dictated over the phone, printed on
the cutting PDF, typed into a staff search box. New orders get six random
decimal digits (`sales.md`); legacy numbers (`#26-14-0003`, `ORD-2026-000123`)
are kept exactly as stored and pass through both helpers unchanged.

Minting the number belongs to the module that owns orders; only its *display*
and the *search* normalisation live here, because the cutting PDF renderer
needs them too and cutting must not import `sales`.
"""

import re

# U+2009 THIN SPACE, written as an escape so the separator stays visible to a
# reader of this file. Narrow enough that the six digits still read as one
# number, wide enough to break them into two speakable halves.
THIN_SPACE = "\u2009"

# U+2116 NUMERO SIGN, the prefix every rendered number carries. It is not copy
# — it is emitted in every locale — and it is in the bundled DejaVu fonts, so
# the PDF prints it rather than a box.
NUMBER_SIGN = "№"

# Six today, seven if the platform ever outgrows 900 000 numbers: the grouping
# below counts from the right, so widening the number moves nothing else.
_GENERATED_NUMBER = re.compile(r"^\d{6,7}$")

# `\s` is Unicode-aware for str patterns, so it already covers the thin space
# the formatter emits and any non-breaking space a paste carries in.
_QUERY_NOISE = re.compile(rf"[\s{NUMBER_SIGN}#]")


def format_order_number(raw: str) -> str:
    """`482917` -> the number sign, `482`, a thin space, `917`.

    Every legacy shape passes through unchanged — nothing reformats history.
    """
    if not _GENERATED_NUMBER.match(raw):
        return raw
    return f"{NUMBER_SIGN} {group_digits(raw)}"


def group_digits(digits: str) -> str:
    """Thin-space groups of three, counted from the right."""
    head = len(digits) % 3 or 3
    return THIN_SPACE.join(
        [digits[:head], *(digits[start : start + 3] for start in range(head, len(digits), 3))]
    )


def normalize_order_number_query(raw: str) -> str:
    """Strip what a client dictates around the digits.

    The displayed number, `482 917` and `482917` are the same number said three
    ways, and staff type whichever they heard. Legacy numbers keep matching on
    their raw text — the caller ORs this normalised form beside the raw one
    rather than replacing it, so `#26-14` still finds `#26-14-0003`.
    """
    return _QUERY_NOISE.sub("", raw)
