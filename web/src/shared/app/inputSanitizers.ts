// Type-time input sanitizers, mirroring PhoneInput's precedent: strip characters
// a field can never contain the moment they appear (typed or pasted), so invalid
// input never sticks. Structural validation stays with the submit-path parsers
// (parseSomToTiyin, parseDisplayQuantity) — these only constrain the alphabet.

// Money in so'm: digits plus everything parseSomToTiyin understands — grouping
// spaces (U+0020, U+00A0, U+202F — the latter two are what Intl 'uz-UZ' emits)
// and dot/comma as group or decimal marks.
export function sanitizeMoneyInput(value: string): string {
  return value.replace(/[^\d   .,]/g, '')
}

// Positive quantity: digits with at most one decimal separator (dot or comma).
export function sanitizeQuantityInput(value: string): string {
  let seenSeparator = false
  let out = ''
  for (const char of value) {
    if (char >= '0' && char <= '9') out += char
    else if ((char === '.' || char === ',') && !seenSeparator) {
      out += char
      seenSeparator = true
    }
  }
  return out
}

// Signed quantity: one leading + or − / - (typographic minus normalized), then
// positive-quantity rules; sign characters anywhere else are dropped.
export function sanitizeSignedQuantityInput(value: string): string {
  const normalized = value.replace(/−/g, '-')
  const first = normalized[0]
  const sign = first === '+' || first === '-' ? first : ''
  const rest = normalized.slice(sign ? 1 : 0).replace(/[+-]/g, '')
  return sign + sanitizeQuantityInput(rest)
}

// Whole millimetres — a cut dimension or a piece count. No separator at all:
// these are integers by definition, and the field they back is a plain text
// input (the handoff's, and the right control: a spinner on a cut size is a
// stray scroll wheel away from resizing a part).
export function sanitizeWholeNumberInput(value: string): string {
  return value.replace(/\D/g, '')
}
