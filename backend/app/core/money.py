"""So'm formatting shared by every document that prints a price.

Amounts are stored in tiyin everywhere; documents print so'm. The rounding and
the space grouping live here rather than in each renderer so the akt sverka and
the cutting document can never disagree about what a number looks like.
"""


def format_som(tiyin: int) -> str:
    """Tiyin as space-grouped so'm. The unit is stated once, by the caller."""

    return f"{round(tiyin / 100):,}".replace(",", " ")
