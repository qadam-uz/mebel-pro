// Script- and apostrophe-insensitive matching for client-side option filtering.
//
// A TS mirror of `backend/app/core/search_fold.py`, and it has to stay one: the
// server folds `dekorlar.search_key` the same way, so a query that finds a decor
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
