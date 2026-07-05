import { describe, expect, it } from 'vitest'

import {
  formatDate,
  formatDateInputValue,
  formatRelativeUz,
  formatStockQuantity,
  formatStockUnit,
  formatTiyin,
  parseDisplayQuantity,
} from '@/shared/formatters'

describe('shared formatters', () => {
  it("formats tiyin as so'm without fractional digits", () => {
    expect(formatTiyin(0)).toBe("0 so'm")
    expect(formatTiyin(12_345_600)).toContain('123')
    expect(formatTiyin(12_345_600)).toMatch(/so'm$/)
  })

  it('formats calendar-relative age in Uzbek', () => {
    expect(formatRelativeUz(new Date())).toBe('bugun')
    const threeDaysAgo = new Date()
    threeDaysAgo.setDate(threeDaysAgo.getDate() - 3)
    expect(formatRelativeUz(threeDaysAgo)).toBe('3 kun oldin')
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
    expect(formatStockQuantity(2500, 'metre')).toBe('2.5 m')
    expect(formatStockQuantity(2530, 'm')).toBe('2.53 m')
    expect(formatStockQuantity(5, 'panel')).toBe('5 panel')
    expect(formatStockQuantity(12, 'piece')).toBe('12 dona')
  })

  it('localizes stock-unit enums, never surfacing a raw English enum', () => {
    expect(formatStockUnit('metre')).toBe('m')
    expect(formatStockUnit('m')).toBe('m')
    expect(formatStockUnit('panel')).toBe('panel')
    expect(formatStockUnit('pcs')).toBe('dona')
    expect(formatStockUnit('piece')).toBe('dona')
  })

  it('parses display quantities back to storage units (mm for metres)', () => {
    expect(parseDisplayQuantity('12,5', 'm')).toBe(12500)
    expect(parseDisplayQuantity('12,5', 'metre')).toBe(12500)
    expect(parseDisplayQuantity('12.5', 'm')).toBe(12500)
    expect(parseDisplayQuantity('3', 'piece')).toBe(3)
    expect(Number.isNaN(parseDisplayQuantity('abc', 'm'))).toBe(true)
  })
})
