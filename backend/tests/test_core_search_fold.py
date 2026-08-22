"""Unit tests for the catalog search fold.

`fold` is applied to both the stored `decors.search_key` and the incoming
query, so what these tests really pin is *which spellings find each other*: any
two inputs that fold to the same string are mutually findable, and any two that
do not, are not. See app/core/search_fold.py.
"""

# ruff: noqa: RUF001 -- the whole point is pairing visually confusable
# Cyrillic and Latin letters.
import pytest
from app.core.search_fold import fold


@pytest.mark.parametrize(
    ("spellings", "expected"),
    [
        # Script: the same decor typed in Cyrillic and in Latin.
        (["сонома", "Сонома", "Sonoma", "SONOMA"], "sonoma"),
        # Apostrophes: all three shapes, plus the spelling that omits it. The
        # `q -> k` fold is what also pulls `yongok` into the same bucket.
        (["ёнғоқ", "yong'oq", "yongʻoq", "yongʼoq", "yong‘oq", "yongoq", "yongok"], "yongok"),
        (["оқ", "oq", "ok"], "ok"),
        # `x -> h`: Uzbek Latin uses both for the same sound.
        (["хром", "xrom", "hrom"], "hrom"),
        # Decor codes survive as-is, minus separators and case.
        (["H1334", "h1334", "h 1334", "h-1334"], "h1334"),
        (["", "   ", "—"], ""),
    ],
)
def test_fold_collapses_equivalent_spellings(spellings: list[str], expected: str) -> None:
    for spelling in spellings:
        assert fold(spelling) == expected, spelling


def test_fold_joins_words_so_spacing_never_splits_a_match() -> None:
    # Separators are dropped rather than normalized, so "Sonoma eman" is found
    # by "sonomaeman" and by "Sonoma  eman" alike.
    assert fold("Sonoma eman") == "sonomaeman"
    assert fold("  Sonoma   eman  ") == "sonomaeman"


def test_fold_keeps_distinct_decors_distinct() -> None:
    assert fold("Sonoma") != fold("Sonata")
    assert fold("H1334") != fold("H1335")


def test_fold_is_idempotent() -> None:
    # search_key is stored folded; folding it again on read must not move it.
    for text in ["сонома", "yong'oq", "H1334 ST9", ""]:
        assert fold(fold(text)) == fold(text)


def test_fold_transliterates_multi_letter_cyrillic_before_single_letters() -> None:
    # `щ`/`ш` both produce "sh" and `ч` produces "ch": a naive per-character
    # pass that checked `ш` first would leave `щ` untouched.
    assert fold("шкаф") == "shkaf"
    assert fold("щётка") == "shyotka"
    assert fold("чёрный") == "chyorniy"
