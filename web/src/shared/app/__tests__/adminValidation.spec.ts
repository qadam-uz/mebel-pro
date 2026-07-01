import { describe, expect, it } from 'vitest'

import { coordinateFieldErrors, nonNegativeInteger } from '@/shared/app/adminValidation'

describe('coordinateFieldErrors', () => {
  it('accepts an empty pair', () => {
    expect(coordinateFieldErrors('', '')).toEqual({ latitude: null, longitude: null })
  })

  it('accepts a valid pair', () => {
    expect(coordinateFieldErrors('41.25', '69.12')).toEqual({ latitude: null, longitude: null })
  })

  it('requires the partner when only one coordinate is filled', () => {
    expect(coordinateFieldErrors('41.25', '')).toEqual({
      latitude: null,
      longitude: 'Lat va Lng birga kiritiladi.',
    })
    expect(coordinateFieldErrors('', '69.12')).toEqual({
      latitude: 'Lat va Lng birga kiritiladi.',
      longitude: null,
    })
  })

  it('reports only the range error and suppresses the pair nag when a value is out of range', () => {
    // Regression: an out-of-range latitude used to also trigger a contradictory
    // "enter both together" error on the empty longitude.
    expect(coordinateFieldErrors('999', '')).toEqual({
      latitude: '-90 dan 90 gacha kiriting.',
      longitude: null,
    })
    expect(coordinateFieldErrors('', '999')).toEqual({
      latitude: null,
      longitude: '-180 dan 180 gacha kiriting.',
    })
  })
})

describe('nonNegativeInteger', () => {
  it('treats blank as valid (optional field)', () => {
    expect(nonNegativeInteger('')).toBeNull()
    expect(nonNegativeInteger('   ')).toBeNull()
  })

  it('accepts non-negative integers', () => {
    expect(nonNegativeInteger('0')).toBeNull()
    expect(nonNegativeInteger('120000')).toBeNull()
  })

  it('rejects non-numeric and negative input with the given message', () => {
    expect(nonNegativeInteger('12a', 'Butun tiyin qiymatini kiriting.')).toBe(
      'Butun tiyin qiymatini kiriting.',
    )
    expect(nonNegativeInteger('-5')).toBe('Butun son kiriting.')
    expect(nonNegativeInteger('1.5')).toBe('Butun son kiriting.')
  })
})
