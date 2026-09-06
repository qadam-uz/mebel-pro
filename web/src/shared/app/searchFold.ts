// Script- and apostrophe-insensitive matching for client-side option filtering.
//
// A TS mirror of `backend/app/core/search_fold.py`, and it has to stay one: the
// server folds `decors.search_key` the same way, so a query that finds a decor
// in the picker must find it in a locally-filtered combobox too. A workshop types
// "сонома" on a Cyrillic keyboard for a decor stored as "Sonoma eman", and before
// this the two simply never met.
//
// Steps, in order — the order is load-bearing:
//   1. casefold
//   2. Cyrillic → Latin, longest match first (щ before ш before х)
//   3. drop every apostrophe shape a tutuq belgisi has ever taken
//   4. drop everything else non-alphanumeric
//   5. fold the pairs people actually mistype: q→k, x→h
//
// Step 5 applies to the OUTPUT of step 2, so `ёнғоқ`, `yong'oq`, `yongoq` and
// `yongok` all land on `yongok`. That is deliberate over-matching: a search box
// that returns a near miss beats one that returns nothing.

/** Longest-first: `щ` must be tried before `ш`, and both before single letters. */
const CYRILLIC: ReadonlyArray<readonly [string, string]> = [
  ['щ', 'sh'],
  ['ш', 'sh'],
  ['ч', 'ch'],
  ['ц', 'ts'],
  ['ю', 'yu'],
  ['я', 'ya'],
  ['ё', 'yo'],
  ['ж', 'j'],
  ['ў', 'o'],
  ['ғ', 'g'],
  ['қ', 'q'],
  ['ҳ', 'h'],
  ['х', 'h'],
  ['й', 'y'],
  ['ъ', ''],
  ['ь', ''],
  ['ы', 'i'],
  ['э', 'e'],
  ['є', 'e'],
  ['а', 'a'],
  ['б', 'b'],
  ['в', 'v'],
  ['г', 'g'],
  ['д', 'd'],
  ['е', 'e'],
  ['з', 'z'],
  ['и', 'i'],
  ['к', 'k'],
  ['л', 'l'],
  ['м', 'm'],
  ['н', 'n'],
  ['о', 'o'],
  ['п', 'p'],
  ['р', 'r'],
  ['с', 's'],
  ['т', 't'],
  ['у', 'u'],
  ['ф', 'f'],
]

export function fold(text: string): string {
  let out = (text ?? '').toLowerCase()
  for (const [from, to] of CYRILLIC) out = out.split(from).join(to)
  // Diacritics, *after* the Cyrillic pass — `ģ`/`ǵ` are how a phone keyboard
  // without `ʻ` writes the `g'` of «yong'oq», and NFD splits them into a bare
  // letter plus a combining mark we can drop. It has to run here and not before:
  // NFD would also pull `й` apart into `и` + breve, and the table above must see
  // the composed letter.
  out = out.normalize('NFD').replace(/\p{M}/gu, '')
  // `\p{L}\p{N}` rather than `\w`: this must keep folded Latin letters and digits
  // and drop apostrophes, dots, `×`, spaces and punctuation in one pass.
  out = out.replace(/[^\p{L}\p{N}]/gu, '')
  return out.replace(/q/g, 'k').replace(/x/g, 'h')
}

/** True when `haystack` contains `query` once both are folded. Empty query matches. */
export function foldIncludes(haystack: string, query: string): boolean {
  const needle = fold(query)
  return needle === '' || fold(haystack).includes(needle)
}

// ── Tokens, keys and matching ───────────────────────────────────────────────
//
// `fold` alone collapses a whole string into one blob, which is why «egger
// sonoma» used to find nothing: the stored key is `sonomaemanh1145egger` and the
// folded query `eggersonoma` is not a substring of it. The fix, server and web
// alike (SPEC_CATALOG_SMART_SEARCH §1), is a **spaced key**: fold per token,
// join with single spaces, wrap the whole thing in spaces so that `' ' + token`
// is a word-start test. Every query token must then match somewhere in the key
// (AND), in any order.

/** Separators a decor name, code or manufacturer is written with. */
const TOKEN_SEPARATORS = /[\s\-_/·,.()]+/

/** Raw (unfolded) non-empty tokens of `text`. */
export function tokenize(text: string): string[] {
  return (text ?? '').split(TOKEN_SEPARATORS).filter((token) => token !== '')
}

/** Folded non-empty tokens — `tokenize` then `fold`, empties dropped. */
export function foldTokens(text: string): string[] {
  return tokenize(text)
    .map(fold)
    .filter((token) => token !== '')
}

/**
 * `' sonoma eman h1145 egger kromka '` — the searchable key of one row, mirroring
 * `decors.search_key`. Wrapped in spaces so a word-start match is a plain
 * `includes(' ' + token)`; empty when `parts` carry no folded token at all.
 *
 * A part written with separators contributes **both** its tokens and its
 * separator-free fold: a code stored as `H 1145` has to stay reachable as
 * `h1145`, which is how every client types it (§1). Duplicates are dropped, so a
 * single-word part contributes exactly one token.
 */
export function buildSearchKey(parts: readonly string[]): string {
  const tokens: string[] = []
  const seen = new Set<string>()
  const push = (token: string) => {
    if (token === '' || seen.has(token)) return
    seen.add(token)
    tokens.push(token)
  }
  for (const part of parts) {
    const parted = foldTokens(part ?? '')
    for (const token of parted) push(token)
    if (parted.length > 1) push(parted.join(''))
  }
  return tokens.length === 0 ? '' : ` ${tokens.join(' ')} `
}

/** Every folded query token is a substring of `key`. An empty query matches. */
export function matchesQuery(key: string, query: string): boolean {
  const tokens = foldTokens(query)
  if (tokens.length === 0) return true
  return tokens.every((token) => key.includes(token))
}

/**
 * How well a row answers the query — **lower is better**, and the same ladder
 * the server orders by (§1):
 *
 * - `0` the folded query *is* the folded code (`h1145` typed at `H 1145`),
 * - `1` the folded code starts with it (`h11`),
 * - `2` every token sits at a word start (`son` → «**Son**oma eman»),
 * - `3` a substring match anywhere.
 *
 * Rows that do not match at all still get `3`; callers filter with
 * `matchesQuery` first.
 */
export function rankKey(key: string, code: string | null | undefined, query: string): number {
  const folded = fold(query)
  const foldedCode = fold(code ?? '')
  if (folded !== '' && foldedCode !== '') {
    if (folded === foldedCode) return 0
    if (foldedCode.startsWith(folded)) return 1
  }
  const tokens = foldTokens(query)
  if (tokens.length > 0 && tokens.every((token) => key.includes(` ${token}`))) return 2
  return 3
}

// ── Tier 2: the keyboard layout ─────────────────────────────────────────────
//
// Typing «Sonoma» with the layout still on ЙЦУКЕН produces «Ыщтщьф», and the
// reverse produces «cjyjvf». Both are a keystroke away from what the client
// meant, so a zero-result query is retried through this table before giving up.

/** QWERTY key → the ЙЦУКЕН letter on the same physical key. */
const QWERTY_TO_JCUKEN: Readonly<Record<string, string>> = {
  q: 'й',
  w: 'ц',
  e: 'у',
  r: 'к',
  t: 'е',
  y: 'н',
  u: 'г',
  i: 'ш',
  o: 'щ',
  p: 'з',
  '[': 'х',
  ']': 'ъ',
  a: 'ф',
  s: 'ы',
  d: 'в',
  f: 'а',
  g: 'п',
  h: 'р',
  j: 'о',
  k: 'л',
  l: 'д',
  ';': 'ж',
  "'": 'э',
  z: 'я',
  x: 'ч',
  c: 'с',
  v: 'м',
  b: 'и',
  n: 'т',
  m: 'ь',
  ',': 'б',
  '.': 'ю',
  '/': '.',
}

const JCUKEN_TO_QWERTY: Readonly<Record<string, string>> = Object.fromEntries(
  Object.entries(QWERTY_TO_JCUKEN).map(([latin, cyrillic]) => [cyrillic, latin]),
)

const HAS_LATIN = /\p{Script=Latin}/u
const HAS_CYRILLIC = /\p{Script=Cyrillic}/u

/**
 * The query as it would have come out under the other keyboard layout, or the
 * query unchanged when the script is mixed (nothing sensible to swap) — «Ыщтщьф»
 * → «sonoma», «cjyjvf» → «сонома».
 */
export function layoutSwap(query: string): string {
  const text = (query ?? '').toLowerCase()
  const latin = HAS_LATIN.test(text)
  const cyrillic = HAS_CYRILLIC.test(text)
  if (latin === cyrillic) return query ?? ''
  const table = cyrillic ? JCUKEN_TO_QWERTY : QWERTY_TO_JCUKEN
  return [...text].map((char) => table[char] ?? char).join('')
}

// ── Tier 3: typos ───────────────────────────────────────────────────────────
//
// The server reaches for `pg_trgm`; a preloaded list of a few hundred tapes is
// small enough to score in the browser. Dice over character bigrams is the
// cheapest measure that survives a transposed or swapped vowel («sanoma» ≈
// «sonoma» = 0.60) while keeping unrelated decors near zero.

function bigrams(text: string): Map<string, number> {
  const counts = new Map<string, number>()
  for (let index = 0; index + 1 < text.length; index += 1) {
    const gram = text.slice(index, index + 2)
    counts.set(gram, (counts.get(gram) ?? 0) + 1)
  }
  return counts
}

/**
 * Sørensen–Dice coefficient over the character bigrams of `fold(a)` and
 * `fold(b)`, in `[0, 1]`. Strings shorter than two characters have no bigram, so
 * they score 1 when equal and 0 otherwise.
 */
export function similarity(a: string, b: string): number {
  const left = fold(a)
  const right = fold(b)
  if (left === '' || right === '') return left === right ? 1 : 0
  if (left.length < 2 || right.length < 2) return left === right ? 1 : 0
  const leftGrams = bigrams(left)
  const rightGrams = bigrams(right)
  let shared = 0
  let leftTotal = 0
  for (const [gram, count] of leftGrams) {
    leftTotal += count
    shared += Math.min(count, rightGrams.get(gram) ?? 0)
  }
  let rightTotal = 0
  for (const count of rightGrams.values()) rightTotal += count
  return (2 * shared) / (leftTotal + rightTotal)
}

/**
 * The typo threshold for tier 3, and the number to move if the tier ever reads
 * too eager or too deaf.
 *
 * Dice-over-bigrams runs higher than the trigram `similarity()` the server
 * compares against 0.3 — «sanoma»/«sonoma» scores 0.60 here and ~0.33 there — so
 * this is the equivalent cut rather than the same number. 0.55 is where the two
 * measured populations separate: one wrong, missing or transposed letter stays
 * in (`sanoma`/`sonoma` 0.60, `sonma`/`sonoma` 0.67, `eger`/`egger` 0.86) and the
 * short unrelated tokens every decor key carries stay out — `eman` against
 * `sanoma` is 0.50, which at 0.45 would have made every «… eman» decor a typo
 * hit for any six-letter query.
 */
export const SIMILARITY_THRESHOLD = 0.55

/**
 * How close a query comes to a row's key, token by token: each query token is
 * scored against the key's *best* token and the row is only as good as its worst
 * one. Comparing the whole key instead would punish a long name for being long —
 * «sanoma» against ` sonoma eman h1145 egger kromka ` scores 0.29 as one blob and
 * 0.60 the way it is read here.
 */
export function querySimilarity(key: string, query: string): number {
  const keyTokens = key.split(' ').filter((token) => token !== '')
  const queryTokens = foldTokens(query)
  if (queryTokens.length === 0 || keyTokens.length === 0) return 0
  let worst = 1
  for (const token of queryTokens) {
    let best = 0
    for (const keyToken of keyTokens) best = Math.max(best, similarity(token, keyToken))
    worst = Math.min(worst, best)
    if (worst === 0) return 0
  }
  return worst
}
