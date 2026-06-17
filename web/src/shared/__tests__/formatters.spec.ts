import { describe, expect, it } from 'vitest'

import {
  formatDate,
  formatDateInputValue,
  formatStockQuantity,
  formatTiyin,
  parseDisplayQuantity,
} from '@/shared/formatters'
import { i18nSeed } from '@/shared/i18n'

describe('shared formatters', () => {
  it('formats tiyin as UZS without fractional digits', () => {
    expect(formatTiyin(12_345_600)).toContain('123')
  })

  it('formats dates with the Uzbek locale seed', () => {
    expect(formatDate(new Date(2026, 5, 2))).toBe('02.06.2026')
  })

  it('formats date input values using the local calendar day', () => {
    expect(formatDateInputValue(new Date(2026, 5, 2))).toBe('2026-06-02')
  })

  it('formats edge-material metres with a dot decimal, not a 1000x-misreadable comma', () => {
    expect(formatStockQuantity(18000, 'm')).toBe('18 m')
    expect(formatStockQuantity(2500, 'm')).toBe('2.5 m')
    expect(formatStockQuantity(2530, 'm')).toBe('2.53 m')
    expect(formatStockQuantity(12, 'piece')).toBe('12 piece')
  })

  it('parses display quantities back to storage units (mm for metres)', () => {
    expect(parseDisplayQuantity('12,5', 'm')).toBe(12500)
    expect(parseDisplayQuantity('12.5', 'm')).toBe(12500)
    expect(parseDisplayQuantity('3', 'piece')).toBe(3)
    expect(Number.isNaN(parseDisplayQuantity('abc', 'm'))).toBe(true)
  })

  it('has labels for each role app', () => {
    expect(Object.keys(i18nSeed)).toEqual(['client', 'workshop', 'admin'])
  })
})
