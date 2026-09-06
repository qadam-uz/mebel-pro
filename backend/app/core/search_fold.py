"""Script- and spelling-insensitive text folding for catalog search.

Uzbek is written in both Cyrillic and Latin, the Latin orthography has three
interchangeable apostrophe shapes (`o'`, `oʻ`, `o‘`), and the same decor name is
routinely typed as `yong'oq`, `yongoq`, `ёнғоқ` or `yongok`. A plain `ILIKE`
over the raw name finds none of those from each other.

`fold` collapses all of them onto one ASCII key. The same function is applied
to the stored `decors.search_key` and to the incoming query, so a token match
is a plain `ILIKE '%' || fold(token) || '%'` — no per-row Python.

`fold` handles one token. `fold_tokens` splits a phrase into folded words and
`build_search_key` assembles the stored `decors.search_key` from them; the
matcher that consumes the key lives in `app/core/search_query.py`.

Steps, in this order (the order is load-bearing — see `_LATIN_CONFUSABLES`):

1. `casefold`
2. Cyrillic to Latin, longest match first
3. drop every apostrophe shape: ``' ʻ ʼ ‘ ’ ` ``
4. drop every remaining non-alphanumeric character
5. fold confusable Latin pairs: ``q -> k``, ``x -> h``

Step 5 must run *after* step 2, so that Cyrillic `қ` (-> `q` -> `k`) and Latin
`q` land on the same letter.

This module deliberately has no imports from `app.modules` — it is imported by
an Alembic revision, which runs before the model registry is usable.
"""

# ruff: noqa: RUF001, RUF002 -- the transliteration table pairs visually confusable
# Cyrillic and Latin letters on purpose; that is the whole point of the module.

from __future__ import annotations

# Cyrillic -> Latin. Multi-character Latin outputs (sh, ch, ya, ...) are why
# lookups run longest-key-first rather than through a per-character dict.
_CYRILLIC_TO_LATIN: dict[str, str] = {
    "ш": "sh",
    "щ": "sh",
    "ч": "ch",
    "ц": "ts",
    "ж": "j",
    "я": "ya",
    "ю": "yu",
    "ё": "yo",
    "є": "e",
    "ы": "i",
    "э": "e",
    "ў": "o",
    "ғ": "g",
    "қ": "q",
    "ҳ": "h",
    "х": "h",
    "ъ": "",
    "ь": "",
    "й": "y",
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "з": "z",
    "и": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
}

_MAX_SOURCE_LENGTH = max(len(key) for key in _CYRILLIC_TO_LATIN)

_APOSTROPHES = frozenset("'ʻʼ‘’`")

# Applied last: `q`/`k` and `x`/`h` are used interchangeably in Uzbek Latin, and
# the Cyrillic map must have run first so `қ` has already become `q`.
_LATIN_CONFUSABLES = str.maketrans({"q": "k", "x": "h"})


def fold(text: str) -> str:
    """Return the folded form of one token — empty string for empty input."""
    lowered = text.casefold()
    transliterated = _transliterate(lowered)
    stripped = "".join(
        char for char in transliterated if char not in _APOSTROPHES and char.isalnum()
    )
    return stripped.translate(_LATIN_CONFUSABLES)


def _transliterate(text: str) -> str:
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        for size in range(min(_MAX_SOURCE_LENGTH, length - index), 0, -1):
            replacement = _CYRILLIC_TO_LATIN.get(text[index : index + size])
            if replacement is not None:
                out.append(replacement)
                index += size
                break
        else:
            out.append(text[index])
            index += 1
    return "".join(out)


# The key splits on these as well as on whitespace: `H-1145`, `2800/2070` and
# `Egger (Austria)` all carry word boundaries a plain `str.split()` misses.
_TOKEN_SEPARATORS = "-_/·,.()"  # noqa: S105 -- separators, not a secret

_SEPARATORS_TO_SPACE = str.maketrans(dict.fromkeys(_TOKEN_SEPARATORS, " "))


def fold_tokens(text: str) -> list[str]:
    """Split `text` on whitespace and `-_/·,.()`, fold each word, drop the empties."""

    return [
        folded for word in text.translate(_SEPARATORS_TO_SPACE).split() if (folded := fold(word))
    ]


def build_search_key(*parts: str | None) -> str:
    """The stored `decors.search_key`: `" " + folded words + " "`.

    Wrapped in spaces so a word-start match is a plain `LIKE '% son%'` — that is
    what makes ranking possible without a tokenizer in the database.

    Every part contributes its **words** and, when it has more than one, its
    whole separator-less fold as well. Both are load-bearing: the words are what
    make `egger sonoma` (two tokens, ANDed, in either order) find a row whose
    key concatenates them, and the whole fold is what keeps a query `h1145`
    finding a code stored as `H 1145` or `H-1145`.

    Duplicate words are dropped, so the key stays compact and its content is a
    pure function of the parts it was built from.
    """

    tokens: list[str] = []
    for part in parts:
        if not part:
            continue
        words = fold_tokens(part)
        whole = fold(part)
        for token in (*words, whole):
            if token and token not in tokens:
                tokens.append(token)
    if not tokens:
        return ""
    return f" {' '.join(tokens)} "
