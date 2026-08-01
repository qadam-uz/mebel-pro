// Uzbek Latin → Uzbek Cyrillic.
//
// uz-Cyrl is not a translation of uz — it is the same language in a different
// script, so it is *derived* from the uz catalog rather than hand-maintained
// beside it. One catalog to edit means the two scripts can never drift; the
// alternative (a third message file) guarantees they do, the first time anyone
// fixes a sentence in one place only.
//
// The mapping is deterministic apart from a handful of cases the rules below
// name explicitly. Anything the rules get wrong is corrected per message key in
// `overrides/uz-Cyrl.json`, never by bending a rule that is right everywhere
// else.

/** Every apostrophe shape that has ever stood for a tutuq belgisi in this repo.
 *  DESIGN.md rule 8 mandates the ASCII one in src/, but the landing page uses
 *  U+02BB and pasted copy carries curly quotes, so all of them are accepted on
 *  input. */
const APOSTROPHE = "'ʻʼ‘’`"
const IS_APOSTROPHE = new RegExp(`[${APOSTROPHE}]`)

/** Ordered longest-first. The order is load-bearing — see `yo` below. */
const DIGRAPHS: ReadonlyArray<readonly [RegExp, string]> = [
  // Apostrophe letters first: `o'`/`g'` are single letters of the Latin
  // alphabet, not a letter plus punctuation.
  [new RegExp(`^o[${APOSTROPHE}]`, 'i'), 'ў'],
  [new RegExp(`^g[${APOSTROPHE}]`, 'i'), 'ғ'],
  // `yo` is ё only when the o is a plain o. In `yo'q` the o belongs to the
  // letter `o'`, so the y stands alone: yo'q → йўқ, not ёқ. The negative
  // lookahead is the whole difference between those two words.
  [new RegExp(`^yo(?![${APOSTROPHE}])`, 'i'), 'ё'],
  [/^yu/i, 'ю'],
  [/^ya/i, 'я'],
  // `ye` is е, never йэ: yer → ер.
  [/^ye/i, 'е'],
  [/^sh/i, 'ш'],
  [/^ch/i, 'ч'],
]

const SINGLES: Readonly<Record<string, string>> = {
  a: 'а',
  b: 'б',
  d: 'д',
  e: 'е', // word-initial e → э; handled in the scanner
  f: 'ф',
  g: 'г',
  h: 'ҳ',
  i: 'и',
  j: 'ж',
  k: 'к',
  l: 'л',
  m: 'м',
  n: 'н',
  o: 'о',
  p: 'п',
  q: 'қ',
  r: 'р',
  s: 'с',
  t: 'т',
  u: 'у',
  v: 'в',
  x: 'х',
  y: 'й',
  z: 'з',
  c: 'к', // only reaches here inside a non-protected loanword; ch is a digraph
  w: 'в',
}

/** Latin runs that must survive untouched: file formats, product names, units
 *  and the two third-party programs the import wizard talks about. Matched
 *  case-sensitively as whole words — `map` the Uzbek word would transliterate,
 *  `MAP` the file format does not. */
const PROTECTED = new Set([
  'PDF',
  'CSV',
  'XML',
  'JSON',
  'MAP',
  'XLS',
  'XLSX',
  'SVG',
  'PNG',
  'JPG',
  'WebP',
  'URL',
  // Operator diagnostics, not copy: a trace id is quoted to support as-is, so
  // the word introducing it stays the same token in every script.
  'trace',
  'Trace',
  // Pre-existing English in the Uzbek catalog (`orders.detail.pieces`). Kept
  // Latin rather than transliterated to `пкс` — the two Uzbek scripts must say
  // the same thing, and the fix belongs in the uz copy, not here.
  'pcs',
  'QR',
  'SMS',
  'OTP',
  'ID',
  'API',
  'Mebel',
  'Pro',
  'Excel',
  'Telegram',
  'mm',
  'sm',
  'kg',
  'm',
])

/** Whole strings that are a brand or a code and never transliterate. */
const PROTECTED_PHRASES: ReadonlyArray<RegExp> = [
  /^2D-Place$/i,
  /^[A-Z]-\d+$/, // document numbers: K-0007
]

function isLatinLetter(ch: string): boolean {
  return /[a-z]/i.test(ch)
}

/** Restores the source token's capitalisation onto its Cyrillic form.
 *  `Sh` → `Ш`, `SHER` → `ШЕР`, `sh` → `ш`. */
function matchCase(source: string, target: string): string {
  const letters = source.replace(IS_APOSTROPHE, '')
  if (!/[A-Z]/.test(letters)) return target
  if (letters.length > 1 && letters === letters.toUpperCase()) return target.toUpperCase()
  return target.charAt(0).toUpperCase() + target.slice(1)
}

/** True at a position that starts a word — the scanner needs it for `e`, which
 *  is э word-initially (ertaga → эртага) and е everywhere else (kel → кел). */
function atWordStart(text: string, index: number): boolean {
  if (index === 0) return true
  return !isLatinLetter(text[index - 1]) && !IS_APOSTROPHE.test(text[index - 1])
}

function isProtected(word: string): boolean {
  return PROTECTED.has(word) || PROTECTED_PHRASES.some((pattern) => pattern.test(word))
}

/** A protected name still takes Uzbek case endings: `Excel'da`, `БАЗИС'da`. The
 *  name stays Latin and only the suffix converts, and the apostrophe joining
 *  them stays an apostrophe — it is a separator here, not a tutuq belgisi. */
const SUFFIXED = new RegExp(`^([A-Za-z0-9-]+)[${APOSTROPHE}](.+)$`)

function transliterateWord(word: string): string {
  if (isProtected(word)) return word

  const suffixed = word.match(SUFFIXED)
  if (suffixed && isProtected(suffixed[1])) {
    return `${suffixed[1]}'${transliterateWord(suffixed[2])}`
  }

  let out = ''
  let i = 0
  while (i < word.length) {
    const rest = word.slice(i)
    const digraph = DIGRAPHS.find(([pattern]) => pattern.test(rest))
    if (digraph) {
      const source = rest.match(digraph[0])![0]
      out += matchCase(source, digraph[1])
      i += source.length
      continue
    }

    const ch = word[i]
    const lower = ch.toLowerCase()

    if (IS_APOSTROPHE.test(ch)) {
      // Not part of o'/g' — a bare tutuq belgisi: ta'minotchi → таъминотчи.
      out += 'ъ'
      i += 1
      continue
    }

    const mapped = SINGLES[lower]
    if (mapped === undefined) {
      out += ch
      i += 1
      continue
    }

    if (lower === 'e' && atWordStart(word, i)) {
      out += matchCase(ch, 'э')
    } else {
      out += matchCase(ch, mapped)
    }
    i += 1
  }
  return out
}

/** Segments a message into the parts that transliterate and the parts that must
 *  not: vue-i18n interpolation (`{count}`), linked messages (`@:some.key`) and
 *  literal blocks (`{'@'}`) all carry key names, not prose. Transliterating a
 *  placeholder would silently break the lookup with no error anywhere. */
// A glob'd file extension is a token, not a word: `*.csv` must not become
// `*.ксв`. The `*` is required — without it the pattern also swallowed the
// month in a date mask (`kk.oo.yyyy`), which is Uzbek letters and does convert.
const PASSTHROUGH = /(\{[^}]*\}|@[.:][A-Za-z0-9_.[\]-]+|<[^>]+>|\*\.[a-z]{2,4}\b)/g

export function transliterateText(text: string): string {
  return text
    .split(PASSTHROUGH)
    .map((segment, index) => {
      // Odd indices are the captured passthrough groups.
      if (index % 2 === 1) return segment
      // A token may open with a digit so that `2D-Place` and `K-0007` reach the
      // protected-phrase check whole; digits have no mapping and fall through
      // the scanner unchanged.
      return segment.replace(/[A-Za-z0-9][A-Za-z0-9'ʻʼ‘’`-]*/g, (word) => {
        // A trailing hyphen or apostrophe belongs to the punctuation around the
        // word, not to it (`Kirim — ` / `"Yuborildi"`).
        const trimmed = word.replace(/[-]+$/, '')
        const tail = word.slice(trimmed.length)
        return transliterateWord(trimmed) + tail
      })
    })
    .join('')
}

export type MessageTree = { readonly [key: string]: string | MessageTree }

/** Walks the uz catalog and returns its uz-Cyrl twin — same shape, same keys,
 *  Cyrillic values — applying `overrides` (mirroring the key paths) after the
 *  rules have run. */
export function transliterateMessages<T extends MessageTree>(
  messages: T,
  overrides: MessageTree = {},
): T {
  const out: Record<string, string | MessageTree> = {}
  for (const [key, value] of Object.entries(messages)) {
    const override = overrides[key]
    if (typeof value === 'string') {
      out[key] = typeof override === 'string' ? override : transliterateText(value)
    } else {
      out[key] = transliterateMessages(
        value,
        typeof override === 'object' && override !== null ? override : {},
      )
    }
  }
  return out as T
}
