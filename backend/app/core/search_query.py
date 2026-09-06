"""One matcher behind every catalog search box.

`search_fold` normalizes *text*; this module turns a typed query into the SQL
that finds rows and the order they come back in, so the platform decor list,
the branch material table, the attach picker, inventory and both client pickers
all behave identically. Adding a surface means calling these functions, never
writing another `ilike`.

The shape, in one paragraph. The query is split on whitespace and every token
must match (AND) — a token matches when its fold is a substring of the row's
`search_key` **or** when the raw token is a dimension the row is sold in.
Matching rows are ordered by a relevance CASE (exact code, code prefix, word
start, anywhere) before the surface's own ordering. If that finds nothing the
same search runs again through two fallbacks: the keyboard-layout swap
(«Ыщтщьф» is `Sonoma` typed on the wrong layout), then `pg_trgm` similarity for
typos. `run_search_tiers` owns that ladder so no consumer re-implements it.

Two pure functions — `matches_search_key` and `rank_key` — mirror the SQL for
the one list that is filtered in the browser (the cutting editor's tape picker,
`web/src/shared/app/searchFold.ts`); they exist so the two implementations can
be tested against the same table of cases.
"""

# ruff: noqa: RUF001 -- the layout table pairs visually confusable Cyrillic and
# Latin characters on purpose; that is the whole point of the module.

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import ColumnElement, SQLColumnExpression, and_, case, func, literal, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.search_fold import fold

# How many rows the typo tier may return. It is a *last* resort — a wide net
# ranked by similarity — so it is capped rather than paged: past twenty rows the
# answer is "your query matched nothing", not "scroll".
FUZZY_LIMIT = 20

# `word_similarity(query, key)` scores the query against the closest run of
# words in the key rather than against the whole key, so a six-letter typo is
# not drowned by a long key. 0.3 admits one wrong letter in a short word
# (`sanoma` vs `sonoma` scores 0.4) without admitting unrelated words.
TRIGRAM_THRESHOLD = 0.3

# A folded token is alphanumeric by construction, so no token can ever carry a
# LIKE metacharacter. That is what lets every predicate below interpolate the
# token into the pattern without an ESCAPE clause.

# The separators a stored code may carry. `fold` drops every non-alphanumeric
# character, but SQL has no such function, so the code fold used for ranking
# strips this fixed list instead — enough for codes, which are ASCII
# alphanumerics with separators (`H 1145`, `H-1145`, `ST9/12`).
_SQL_CODE_SEPARATORS = " -_/·,.()'ʻʼ‘’`"


# --------------------------------------------------------------------------- #
# Keyboard layout (tier 2)
# --------------------------------------------------------------------------- #

# ЙЦУКЕН -> QWERTY, by physical key. A client typing `Sonoma` with the Russian
# layout still active produces «Ыщтщьф»; mapping it back is a one-table fix for
# what is otherwise a baffling empty result.
_CYRILLIC_TO_QWERTY: dict[str, str] = {
    "й": "q", "ц": "w", "у": "e", "к": "r", "е": "t", "н": "y", "г": "u",
    "ш": "i", "щ": "o", "з": "p", "х": "[", "ъ": "]",
    "ф": "a", "ы": "s", "в": "d", "а": "f", "п": "g", "р": "h", "о": "j",
    "л": "k", "д": "l", "ж": ";", "э": "'",
    "я": "z", "ч": "x", "с": "c", "м": "v", "и": "b", "т": "n", "ь": "m",
    "б": ",", "ю": ".", "ё": "`",
}  # fmt: skip

_QWERTY_TO_CYRILLIC: dict[str, str] = {
    latin: cyrillic for cyrillic, latin in _CYRILLIC_TO_QWERTY.items()
}

_CYRILLIC_KEYS = frozenset(_CYRILLIC_TO_QWERTY)


def layout_swap(query: str) -> str | None:
    """`query` retyped on the other keyboard layout, or None if that is not it.

    Only a query written **entirely** in one script is swapped: a mixed query is
    someone typing deliberately, not someone who forgot to switch layouts.
    Returns None when the swap changes nothing or produces no letters.
    """

    lowered = query.casefold()
    letters = [char for char in lowered if char.isalpha()]
    if not letters:
        return None
    if all(char in _CYRILLIC_KEYS for char in letters):
        table = _CYRILLIC_TO_QWERTY
    elif all("a" <= char <= "z" for char in letters):
        table = _QWERTY_TO_CYRILLIC
    else:
        return None
    swapped = "".join(table.get(char, char) for char in lowered)
    if swapped == lowered or not any(char.isalnum() for char in swapped):
        return None
    return swapped


# --------------------------------------------------------------------------- #
# Tier 1: tokens ANDed over the folded key
# --------------------------------------------------------------------------- #


def query_tokens(query: str) -> list[str]:
    """The folded tokens of a typed query — split on whitespace only.

    Whitespace only, unlike the *key*: `h-1145` is one thing the operator typed
    and folds to `h1145`, which is exactly the form `build_search_key` also
    stores for a code written `H 1145`.
    """

    return [folded for word in query.split() if (folded := fold(word))]


def search_predicate(
    query: str,
    key_column: SQLColumnExpression[str],
    *,
    dimension_arms: Callable[[str], Sequence[ColumnElement[bool]]] | None = None,
) -> ColumnElement[bool] | None:
    """Every token of `query` matches the key or a dimension — ANDed.

    `dimension_arms` is the surface's own answer to "what numbers can this row
    be found by": the branch table matches the format on its joined row, the
    decor-level pickers wrap the same arms in an EXISTS. Surfaces that have no
    number to offer pass nothing.

    Returns None for an empty query so the caller can skip the filter entirely
    rather than AND in a tautology.
    """

    clauses: list[ColumnElement[bool]] = []
    for word in query.split():
        arms: list[ColumnElement[bool]] = []
        folded = fold(word)
        if folded:
            arms.append(key_column.ilike(f"%{folded}%"))
        if dimension_arms is not None:
            arms.extend(dimension_arms(word))
        if arms:
            clauses.append(or_(*arms))
    if not clauses:
        return None
    return and_(*clauses)


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #


def folded_code_expression(code_column: SQLColumnExpression[str | None]) -> ColumnElement[str]:
    """The SQL-side fold of a stored code, for the two code-first rank bands.

    Deliberately narrower than `fold`: it lowercases, strips the separators a
    code can carry and folds `q`/`x`, but does not transliterate — a decor
    *code* is a manufacturer's ASCII article number (`H1145`, `W980`, `ST9`),
    never Cyrillic. Nested `replace()` rather than `translate()` so the same
    expression runs on Postgres and on the tests' SQLite.
    """

    expression: Any = func.lower(func.coalesce(code_column, ""))
    for char in _SQL_CODE_SEPARATORS:
        expression = func.replace(expression, char, "")
    expression = func.replace(expression, "q", "k")
    return func.replace(expression, "x", "h")


def rank_expression(
    query: str,
    key_column: SQLColumnExpression[str],
    code_column: SQLColumnExpression[str | None] | None = None,
) -> ColumnElement[int]:
    """Relevance, lowest first — the CASE every search ORDERs by.

    0. the query **is** the code (`h1145` typed at `H-1145`);
    1. the code starts with the query (`h11`);
    2. every token starts a word in the key (`son` at `Sonoma`);
    3. matched somewhere else — mid-word, or only by a dimension.

    Band 3 is where a dimension-only match lands: a number the row is sold in is
    a real match and a weak one, so it sorts under every textual hit.
    """

    whens: list[tuple[ColumnElement[bool], int]] = []
    folded_query = fold(query)
    if folded_query and code_column is not None:
        folded_code = folded_code_expression(code_column)
        whens.append((and_(code_column.is_not(None), folded_code == folded_query), 0))
        whens.append((and_(code_column.is_not(None), folded_code.like(f"{folded_query}%")), 1))
    tokens = query_tokens(query)
    if tokens:
        whens.append((and_(*[key_column.ilike(f"% {token}%") for token in tokens]), 2))
    if not whens:
        return literal(0)
    return case(*whens, else_=3)


def rank_key(query: str, *, search_key: str, code: str | None) -> int:
    """`rank_expression` in pure Python — the browser-side list's copy.

    Kept beside the SQL so the two can be held to one table of cases; the
    TypeScript port in `web/src/shared/app/searchFold.ts` mirrors this function.
    """

    folded_query = fold(query)
    if folded_query and code:
        folded_code = fold(code)
        if folded_code == folded_query:
            return 0
        if folded_code.startswith(folded_query):
            return 1
    tokens = query_tokens(query)
    if tokens and all(f" {token}" in search_key for token in tokens):
        return 2
    return 3


def matches_search_key(search_key: str, query: str) -> bool:
    """`search_predicate` in pure Python, without the dimension arms."""

    return all(token in search_key for token in query_tokens(query))


# --------------------------------------------------------------------------- #
# Tier 3: trigram similarity
# --------------------------------------------------------------------------- #


def trigram_predicate(
    query: str,
    key_column: SQLColumnExpression[str],
    *,
    threshold: float = TRIGRAM_THRESHOLD,
) -> ColumnElement[bool] | None:
    """Every token is *close to* a word of the key — Postgres `pg_trgm` only.

    Per token rather than over the whole query so `egger sanoma` still narrows
    the way `egger sonoma` does. Returns None when there is nothing to match.
    """

    tokens = query_tokens(query)
    if not tokens:
        return None
    return and_(*[func.word_similarity(token, key_column) >= threshold for token in tokens])


def trigram_rank_expression(
    query: str, key_column: SQLColumnExpression[str]
) -> ColumnElement[float]:
    """How well the typo tier matched — ordered descending, best first."""

    tokens = query_tokens(query)
    if not tokens:
        return literal(0.0)
    total: Any = func.word_similarity(tokens[0], key_column)
    for token in tokens[1:]:
        total = total + func.word_similarity(token, key_column)
    return cast("ColumnElement[float]", total)


# --------------------------------------------------------------------------- #
# The tier ladder
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SearchPlan:
    """One attempt at a search: what to look for and how forgiving to be."""

    query: str | None
    tier: int
    fuzzy: bool = False
    limit: int | None = None

    @property
    def active(self) -> bool:
        """True when this plan is actually filtering — an empty search is not."""

        return bool(self.query)


NO_SEARCH = SearchPlan(query=None, tier=1)


def search_plans(search: str | None) -> list[SearchPlan]:
    """The ladder for one typed query, best-first. Tried until one finds rows."""

    typed = (search or "").strip()
    if not typed:
        return [NO_SEARCH]
    plans = [SearchPlan(query=typed, tier=1)]
    swapped = layout_swap(typed)
    if swapped is not None:
        plans.append(SearchPlan(query=swapped, tier=2))
    plans.append(SearchPlan(query=typed, tier=3, fuzzy=True, limit=FUZZY_LIMIT))
    return plans


def capped(limit: int | None, cap: int | None) -> int | None:
    """The tighter of a caller's page size and a tier's own cap."""

    if limit is None:
        return cap
    if cap is None:
        return limit
    return min(limit, cap)


async def run_search_tiers[T](
    db: AsyncSession,
    search: str | None,
    run: Callable[[SearchPlan], Awaitable[T]],
    *,
    empty: Callable[[T], bool] | None = None,
) -> T:
    """Run `run` down the tier ladder and return the first result that has rows.

    The whole fallback policy lives here — the consumer supplies one coroutine
    that builds and executes its own query for a given plan, and gets back
    exactly what it would have returned anyway. Nothing in the response says
    which tier produced it: a fallback result is simply the result.

    The typo tier is skipped where it cannot run — SQLite in the test suite, or
    a Postgres without `pg_trgm` — so a database missing the extension degrades
    to "no rows found" instead of erroring. The check costs one catalog query
    and only ever runs on the path where the first two tiers found nothing.
    """

    is_empty = empty if empty is not None else _is_empty
    plans = search_plans(search)
    result = await run(plans[0])
    for plan in plans[1:]:
        if not is_empty(result):
            return result
        if plan.fuzzy and not await trigram_available(db):
            continue
        result = await run(plan)
    return result


async def trigram_available(db: AsyncSession) -> bool:
    """Whether this database can run the typo tier at all."""

    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    installed = await db.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"))
    return installed is not None


def _is_empty(result: Any) -> bool:
    return not result
