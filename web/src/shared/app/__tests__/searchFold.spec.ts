import { describe, expect, it } from 'vitest'

import {
  SIMILARITY_THRESHOLD,
  buildSearchKey,
  fold,
  foldIncludes,
  foldTokens,
  layoutSwap,
  matchesQuery,
  querySimilarity,
  rankKey,
  similarity,
  tokenize,
} from '@/shared/app/searchFold'

// The canonical cases of SPEC_CATALOG_SMART_SEARCH §3. The Python suite asserts
// the same table against the server predicate; this one asserts everything a
// pure function can, so a divergence between the two folds shows up here rather
// than as "the picker finds it and the catalog does not".

/** `Sonoma eman · H1145 · Egger`, an LDSP — the spec's worked example. */
const SONOMA = buildSearchKey(['Sonoma eman', 'H1145', 'Egger', 'ldsp'])
const YONGOQ = buildSearchKey(["Yong'oq", 'H3734', 'Egger', 'ldsp'])
const KULRANG = buildSearchKey(['Kulrang eman', 'H1137', 'Egger', 'ldsp'])
const OQ = buildSearchKey(['Oq', 'W980', 'Kronospan', 'ldsp'])

describe('fold — the TS mirror of search_fold.py', () => {
  it('collapses script, apostrophe and confusable spelling onto one key', () => {
    expect(fold('Sonoma')).toBe('sonoma')
    expect(fold('сонома')).toBe('sonoma')
    expect(fold('SONOMA')).toBe('sonoma')
    // q→k and x→h run last, so Cyrillic `қ` and Latin `q` land together.
    expect(fold("Yong'oq")).toBe('yongok')
    expect(fold('yongoq')).toBe('yongok')
    expect(fold('yongok')).toBe('yongok')
    expect(fold('ёнғоқ')).toBe('yongok')
    expect(fold('yonģoq')).toBe('yongok')
    expect(fold('оқ')).toBe('ok')
    expect(fold('Qulrang')).toBe('kulrang')
    expect(fold('кулранг')).toBe('kulrang')
    // Separators and the multiplication sign are dropped, digits are kept.
    expect(fold('H 1145')).toBe('h1145')
    expect(fold('h-1145')).toBe('h1145')
    expect(fold('2800×2070')).toBe('28002070')
    expect(fold('')).toBe('')
  })

  it('keeps foldIncludes working for the combobox', () => {
    expect(foldIncludes('Sonoma eman', 'сонома')).toBe(true)
    expect(foldIncludes('Sonoma eman', '')).toBe(true)
    expect(foldIncludes('Sonoma eman', 'oq')).toBe(false)
  })
})

describe('tokenize / buildSearchKey', () => {
  it('splits on whitespace and the separators a decor code is written with', () => {
    expect(tokenize('Sonoma eman')).toEqual(['Sonoma', 'eman'])
    expect(tokenize('H-1145/W.980_x·y,z(1)')).toEqual([
      'H',
      '1145',
      'W',
      '980',
      'x',
      'y',
      'z',
      '1',
    ])
    expect(tokenize('')).toEqual([])
    expect(foldTokens("Yong'oq  H3734 ")).toEqual(['yongok', 'h3734'])
  })

  it('wraps the folded tokens in spaces so a word start is a plain substring', () => {
    expect(SONOMA).toBe(' sonoma eman sonomaeman h1145 egger ldsp ')
    // A code stored as `H 1145` keeps its separator-free fold beside its tokens,
    // which is what makes the spec's three spellings of it one key.
    expect(buildSearchKey(['H 1145'])).toBe(' h 1145 h1145 ')
    expect(matchesQuery(buildSearchKey(['Sonoma eman', 'H 1145']), 'h1145')).toBe(true)
    expect(matchesQuery(buildSearchKey(['Sonoma eman', 'H-1145']), 'h1145')).toBe(true)
    expect(buildSearchKey([])).toBe('')
    expect(buildSearchKey(['', ' · '])).toBe('')
    // One token per part, deduplicated — a single word is not repeated.
    expect(buildSearchKey(['Egger', 'egger'])).toBe(' egger ')
  })
})

describe('matchesQuery — every token must match, in any order', () => {
  it('finds the spec’s rows in either script', () => {
    for (const query of [
      'sonoma',
      'сонома',
      'SONOMA',
      'egger sonoma',
      'sonoma egger',
      'h1145',
      'H 1145',
      'h-1145',
      'эггер',
      'ldsp sonoma',
      'лдсп',
    ]) {
      expect(matchesQuery(SONOMA, query), query).toBe(true)
    }
    for (const query of ['yongoq', "yong'oq", 'yongok', 'ёнғоқ', 'yonģoq']) {
      expect(matchesQuery(YONGOQ, query), query).toBe(true)
    }
    for (const query of ['kulrang', 'кулранг', 'qulrang']) {
      expect(matchesQuery(KULRANG, query), query).toBe(true)
    }
    for (const query of ['oq', 'ok', 'оқ', 'w980', 'krono']) {
      expect(matchesQuery(OQ, query), query).toBe(true)
    }
  })

  it('ANDs the tokens rather than matching the query as one blob', () => {
    expect(matchesQuery(SONOMA, 'egger sonoma')).toBe(true)
    expect(matchesQuery(SONOMA, 'kronospan sonoma')).toBe(false)
    expect(matchesQuery(OQ, 'egger oq')).toBe(false)
  })

  it('matches everything on an empty or separator-only query', () => {
    expect(matchesQuery(SONOMA, '')).toBe(true)
    expect(matchesQuery(SONOMA, '   ')).toBe(true)
    expect(matchesQuery(SONOMA, ' - · ')).toBe(true)
  })
})

describe('rankKey — lower is better', () => {
  it('puts an exact code first and a code prefix second', () => {
    expect(rankKey(SONOMA, 'H1145', 'h1145')).toBe(0)
    expect(rankKey(SONOMA, 'H1145', 'H 1145')).toBe(0)
    expect(rankKey(SONOMA, 'H1145', 'h11')).toBe(1)
    // The same query against a row that carries `h1145` in its *name* and has a
    // code of its own: a word-start hit at best, so the code row sorts above it.
    const mentions = buildSearchKey(['Dekor h1145 tus', 'W980', 'Kronospan'])
    expect(rankKey(mentions, 'W980', 'h1145')).toBe(2)
    expect(rankKey(SONOMA, 'H1145', 'h1145')).toBeLessThan(rankKey(mentions, 'W980', 'h1145'))
  })

  it('ranks a word start above a match in the middle of a word', () => {
    expect(rankKey(SONOMA, 'H1145', 'son')).toBe(2)
    expect(rankKey(SONOMA, 'H1145', 'sonoma egger')).toBe(2)
    // `noma` sits inside `sonoma`, not at its start.
    expect(rankKey(SONOMA, 'H1145', 'noma')).toBe(3)
    expect(rankKey(SONOMA, 'H1145', 'son noma')).toBe(3)
  })

  it('treats a row with no code as rankable by its tokens alone', () => {
    expect(rankKey(OQ, null, 'oq')).toBe(2)
    expect(rankKey(OQ, undefined, 'krono')).toBe(2)
  })
})

describe('layoutSwap — QWERTY ↔ ЙЦУКЕН', () => {
  it('reads a query typed under the wrong layout, both directions', () => {
    expect(layoutSwap('Ыщтщьф')).toBe('sonoma')
    expect(layoutSwap('sonoma')).toBe('ыщтщьф')
    expect(layoutSwap(layoutSwap('sonoma'))).toBe('sonoma')
    expect(matchesQuery(SONOMA, layoutSwap('Ыщтщьф'))).toBe(true)
  })

  it('leaves a mixed or scriptless query alone', () => {
    expect(layoutSwap('h1145')).toBe('р1145')
    expect(layoutSwap('1145')).toBe('1145')
    expect(layoutSwap('sonoma сонома')).toBe('sonoma сонома')
    expect(layoutSwap('')).toBe('')
  })
})

describe('similarity — tier 3', () => {
  it('scores a one-letter typo above the threshold and strangers below it', () => {
    expect(similarity('sanoma', 'sonoma')).toBeCloseTo(0.6, 5)
    expect(similarity('sanoma', 'sonoma')).toBeGreaterThan(SIMILARITY_THRESHOLD)
    expect(similarity('сонама', 'Sonoma')).toBeGreaterThan(SIMILARITY_THRESHOLD)
    expect(similarity('sonma', 'sonoma')).toBeGreaterThan(SIMILARITY_THRESHOLD)
    expect(similarity('eger', 'egger')).toBeGreaterThan(SIMILARITY_THRESHOLD)
    expect(similarity('sonoma', 'sonoma')).toBe(1)
    expect(similarity('oq', 'sonoma')).toBe(0)
    expect(similarity('kulrang', 'sonoma')).toBeLessThan(SIMILARITY_THRESHOLD)
    // The pair the threshold is set by: a short key token must not read as a
    // typo of an unrelated six-letter query.
    expect(similarity('eman', 'sanoma')).toBeCloseTo(0.5, 5)
    expect(similarity('eman', 'sanoma')).toBeLessThan(SIMILARITY_THRESHOLD)
  })

  it('handles the degenerate lengths without dividing by zero', () => {
    expect(similarity('', '')).toBe(1)
    expect(similarity('a', 'a')).toBe(1)
    expect(similarity('a', 'b')).toBe(0)
    expect(similarity('a', '')).toBe(0)
  })

  it('scores a query against the key token by token, not as one blob', () => {
    // The whole-key comparison the server can afford scores this pair at 0.29;
    // per token it is the 0.60 of `sanoma` vs `sonoma`.
    expect(querySimilarity(SONOMA, 'sanoma')).toBeCloseTo(0.6, 5)
    expect(querySimilarity(SONOMA, 'sanoma')).toBeGreaterThan(SIMILARITY_THRESHOLD)
    expect(querySimilarity(KULRANG, 'sanoma')).toBeLessThan(SIMILARITY_THRESHOLD)
    // A row is only as good as the worst of the query's tokens.
    expect(querySimilarity(SONOMA, 'sanoma kronospan')).toBeLessThan(SIMILARITY_THRESHOLD)
    expect(querySimilarity(SONOMA, '')).toBe(0)
    expect(querySimilarity('', 'sanoma')).toBe(0)
  })
})
