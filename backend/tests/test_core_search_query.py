"""Unit tests for the pure half of the catalog matcher.

The SQL half is proven against a real database in `test_catalog_smart_search.py`.
What lives here is the logic no query can express — how a phrase becomes a key,
which keyboard layout a query was typed on, and what relevance band a row lands
in. `rank_key` and `matches_search_key` are also the contract the browser-side
tape picker mirrors (`web/src/shared/app/searchFold.ts`), so the cases below are
the same table the TypeScript suite asserts.
"""

# ruff: noqa: RUF001 -- the whole point is pairing visually confusable
# Cyrillic and Latin letters.
import pytest
from app.core.search_fold import build_search_key, fold_tokens
from app.core.search_query import (
    layout_swap,
    matches_search_key,
    query_tokens,
    rank_key,
    search_plans,
)

# The catalog row the spec's canonical cases are written against.
SONOMA = build_search_key("Sonoma eman", "H1145", "Egger", "ldsp")


def test_fold_tokens_splits_on_separators_a_catalog_actually_carries() -> None:
    assert fold_tokens("Sonoma eman") == ["sonoma", "eman"]
    assert fold_tokens("H-1145") == ["h", "1145"]
    assert fold_tokens("Egger (Austria)") == ["egger", "austria"]
    assert fold_tokens("2800/2070") == ["2800", "2070"]
    assert fold_tokens("   ") == []


def test_build_search_key_wraps_in_spaces_so_a_word_start_is_matchable() -> None:
    key = build_search_key("Sonoma eman", "H1145", "Egger")
    assert key.startswith(" ") and key.endswith(" ")
    assert " sonoma" in key
    # A one-word part contributes one token; a multi-word one also contributes
    # its separator-less fold, which is what keeps `h1145` finding `H 1145`.
    assert " h1145 " in build_search_key("Sonoma", "H 1145", "Egger")
    assert " sonomaeman " in key


def test_build_search_key_drops_duplicates_and_empty_parts() -> None:
    assert build_search_key("Oq", None, "Oq") == " ok "
    assert build_search_key(None, "", None) == ""


@pytest.mark.parametrize(
    "query",
    [
        "sonoma",
        "сонома",
        "SONOMA",
        "egger sonoma",
        "sonoma egger",
        "h1145",
        "H 1145",
        "h-1145",
        "эггер",
        "ldsp sonoma",
        "лдсп",
        "sonom",
        "sonoma eman",
    ],
)
def test_the_canonical_queries_all_reach_sonoma(query: str) -> None:
    assert matches_search_key(SONOMA, query), query


@pytest.mark.parametrize(
    ("entry", "queries"),
    [
        (("Yong'oq", "H3734", "Egger"), ["yongoq", "yong'oq", "yongok", "ёнғоқ", "yonģoq"]),
        (("Kulrang eman", "H1137", "Egger"), ["kulrang", "кулранг", "qulrang"]),
        (("Oq", "W980", "Kronospan"), ["oq", "ok", "оқ", "w980", "krono"]),
    ],
)
def test_spelling_variants_reach_their_row(entry: tuple[str, str, str], queries: list[str]) -> None:
    key = build_search_key(*entry)
    for query in queries:
        assert matches_search_key(key, query), query


def test_every_token_must_match() -> None:
    # AND, not OR: a query that names two things finds only rows that are both.
    assert not matches_search_key(SONOMA, "egger kronospan")
    assert not matches_search_key(SONOMA, "sonoma kronospan")


def test_ranking_puts_the_code_first_then_the_word_start() -> None:
    # 0 — the query *is* the code, however it was punctuated.
    assert rank_key("h1145", search_key=SONOMA, code="H1145") == 0
    assert rank_key("H-1145", search_key=SONOMA, code="H 1145") == 0
    # 1 — a prefix of the code.
    assert rank_key("h11", search_key=SONOMA, code="H1145") == 1
    # 2 — every token starts a word in the key.
    assert rank_key("son", search_key=SONOMA, code="H1145") == 2
    assert rank_key("egger sonom", search_key=SONOMA, code="H1145") == 2
    # 3 — matched mid-word, which is the weakest real match there is.
    assert rank_key("noma", search_key=SONOMA, code="H1145") == 3


def test_a_row_whose_name_contains_the_code_ranks_under_the_row_that_is_the_code() -> None:
    """The spec's `h1145` case: the code row wins over a name that mentions it."""

    other = build_search_key("Eman 1145", None, "Kronospan")
    assert rank_key("h1145", search_key=SONOMA, code="H1145") == 0
    assert rank_key("1145", search_key=other, code=None) > 0


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        # The spec's own example: `Sonoma` typed with ЙЦУКЕН still active.
        ("Ыщтщьф", "sonoma"),
        ("ыщтщьф", "sonoma"),
        ("sonoma", "ыщтщьф"),
        # Punctuation and digits ride along untouched.
        ("р1145", "h1145"),
    ],
)
def test_layout_swap_maps_between_the_two_keyboards(typed: str, expected: str) -> None:
    assert layout_swap(typed) == expected


@pytest.mark.parametrize("typed", ["", "18", "2800x2070 сонома", "---"])
def test_layout_swap_declines_what_is_not_a_layout_mistake(typed: str) -> None:
    # No letters at all, or a mix of both scripts: someone typing deliberately.
    assert layout_swap(typed) is None


def test_layout_swap_round_trips() -> None:
    swapped = layout_swap("sonoma")
    assert swapped is not None
    assert layout_swap(swapped) == "sonoma"


def test_the_tier_ladder_is_built_best_first() -> None:
    plans = search_plans("sonoma")
    assert [(plan.tier, plan.fuzzy) for plan in plans] == [(1, False), (2, False), (3, True)]
    # Tier 2 searches for the swapped string; tier 3 for what was typed, capped.
    assert plans[1].query == layout_swap("sonoma")
    assert plans[2].limit == 20


def test_a_query_with_no_layout_twin_skips_tier_two() -> None:
    # A number was not typed on the wrong keyboard, so there is nothing to swap.
    assert [plan.tier for plan in search_plans("18")] == [1, 3]


def test_an_empty_search_is_one_inert_plan() -> None:
    for empty in (None, "", "   "):
        plans = search_plans(empty)
        assert len(plans) == 1
        assert not plans[0].active


def test_query_tokens_splits_on_whitespace_only() -> None:
    # Unlike the key: `h-1145` is one thing the operator typed, and it has to
    # fold to the same `h1145` the key stores for a code written `H 1145`.
    assert query_tokens("h-1145") == ["h1145"]
    assert query_tokens("H 1145") == ["h", "1145"]
