import { describe, expect, it } from 'vitest'

import { nonNegativeAmount, nonNegativeInteger } from '@/shared/app/adminValidation'

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

describe('nonNegativeAmount', () => {
  it('treats blank as valid (optional field)', () => {
    expect(nonNegativeAmount('')).toBeNull()
    expect(nonNegativeAmount('   ')).toBeNull()
  })

  it('accepts non-negative integers and decimals (legacy tiyin round-trip)', () => {
    expect(nonNegativeAmount('0')).toBeNull()
    expect(nonNegativeAmount('5000')).toBeNull()
    expect(nonNegativeAmount('123.45')).toBeNull()
  })

  it('rejects non-numeric and negative input with the given message', () => {
    expect(nonNegativeAmount('12a', 'Narxni kiriting.')).toBe('Narxni kiriting.')
    expect(nonNegativeAmount('-5')).toBe("To'g'ri qiymat kiriting.")
  })
})
