import { describe, expect, it } from 'vitest'

import {
  sanitizeMoneyInput,
  sanitizeQuantityInput,
  sanitizeSignedQuantityInput,
  sanitizeWholeNumberInput,
} from '@/shared/app/inputSanitizers'

describe('inputSanitizers', () => {
  it('money keeps digits, grouping spaces, and dot/comma — strips everything else', () => {
    expect(sanitizeMoneyInput('12 500')).toBe('12 500')
    expect(sanitizeMoneyInput('1.500.000')).toBe('1.500.000')
    expect(sanitizeMoneyInput('12,5')).toBe('12,5')
    expect(sanitizeMoneyInput('12 500')).toBe('12 500') // NBSP grouping (Intl uz-UZ)
    expect(sanitizeMoneyInput('abc12x500!')).toBe('12500')
    expect(sanitizeMoneyInput('12345.67')).toBe('12345.67') // moneyInputValue prefill round-trip
    expect(sanitizeMoneyInput('-500')).toBe('500') // money fields are unsigned
  })

  it('quantity keeps digits with at most one decimal separator', () => {
    expect(sanitizeQuantityInput('12.5')).toBe('12.5')
    expect(sanitizeQuantityInput('12,5')).toBe('12,5')
    expect(sanitizeQuantityInput('1.2.3')).toBe('1.23')
    expect(sanitizeQuantityInput('abc')).toBe('')
    expect(sanitizeQuantityInput('2x,y5')).toBe('2,5')
    expect(sanitizeQuantityInput('-3')).toBe('3')
  })

  it('signed quantity keeps one leading sign only, normalizing the typographic minus', () => {
    expect(sanitizeSignedQuantityInput('-2')).toBe('-2')
    expect(sanitizeSignedQuantityInput('+1,5')).toBe('+1,5')
    expect(sanitizeSignedQuantityInput('−3')).toBe('-3') // − → -
    expect(sanitizeSignedQuantityInput('--2')).toBe('-2')
    expect(sanitizeSignedQuantityInput('2-')).toBe('2') // sign must lead
    expect(sanitizeSignedQuantityInput('a-2b')).toBe('2')
    expect(sanitizeSignedQuantityInput('+')).toBe('+') // mid-typing state stays editable
  })
  it('keeps a whole-number cell to digits', () => {
    // The cell backs a cut dimension: a letter that slipped through would be
    // coerced to 0 and silently resize the part.
    expect(sanitizeWholeNumberInput('2750')).toBe('2750')
    expect(sanitizeWholeNumberInput('27a50')).toBe('2750')
    expect(sanitizeWholeNumberInput('-27.5')).toBe('275')
    expect(sanitizeWholeNumberInput('e')).toBe('')
  })
})
