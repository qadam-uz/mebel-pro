import { describe, expect, it } from 'vitest'

import {
  formatDate,
  formatDateInputValue,
  formatDateTime,
  formatRelativeUz,
  formatStockQuantity,
  formatStockUnit,
  formatTiyin,
  parseDisplayQuantity,
  parseSomToTiyin,
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

  it('formats date-only strings as the same calendar day in every timezone', () => {
    // "2026-07-05" must never render as 04.07 for UTC-negative users — the
    // parts are read directly instead of round-tripping through UTC midnight.
    // Pin a UTC-negative zone so this actually exercises the failure mode
    // (Node honors runtime TZ changes on POSIX; the sanity check guards that).
    const previousTz = process.env.TZ
    process.env.TZ = 'America/New_York'
    try {
      expect(new Date('2026-07-05').getDate()).toBe(4) // sanity: raw UTC parse shifts here
      expect(formatDate('2026-07-05')).toBe('05.07.2026')
      expect(formatDate('2026-01-01')).toBe('01.01.2026')
    } finally {
      if (previousTz === undefined) delete process.env.TZ
      else process.env.TZ = previousTz
    }
  })

  it('formats datetimes as DD.MM.YYYY HH:mm in local time', () => {
    expect(formatDateTime(new Date(2026, 6, 5, 14, 32))).toBe('05.07.2026 14:32')
    expect(formatDateTime(new Date(2026, 0, 9, 7, 5))).toBe('09.01.2026 07:05')
    // Full ISO strings with an offset parse through `new Date` (tz-aware).
    const parsed = new Date('2026-07-05T09:32:00+05:00')
    expect(formatDateTime('2026-07-05T09:32:00+05:00')).toBe(formatDateTime(parsed))
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

  it("parses human-entered so'm amounts into tiyin across local formats", () => {
    expect(parseSomToTiyin('12 500')).toBe(1_250_000)
    expect(parseSomToTiyin('12.500')).toBe(1_250_000)
    expect(parseSomToTiyin('12,500')).toBe(1_250_000)
    expect(parseSomToTiyin('1.500.000')).toBe(150_000_000)
    expect(parseSomToTiyin('12,5')).toBe(1_250)
    expect(parseSomToTiyin('12.5')).toBe(1_250)
    expect(parseSomToTiyin('340000')).toBe(34_000_000)
  })

  it("rejects unclear or non-positive so'm inputs instead of coercing to 0", () => {
    expect(parseSomToTiyin('')).toBeNull()
    expect(parseSomToTiyin('0')).toBeNull()
    expect(parseSomToTiyin('abc')).toBeNull()
    expect(parseSomToTiyin('-5')).toBeNull()
    expect(parseSomToTiyin('12.3456')).toBeNull()
    expect(parseSomToTiyin('1,23,45')).toBeNull()
  })

  it('parses display quantities back to storage units (mm for metres)', () => {
    expect(parseDisplayQuantity('12,5', 'm')).toBe(12500)
    expect(parseDisplayQuantity('12,5', 'metre')).toBe(12500)
    expect(parseDisplayQuantity('12.5', 'm')).toBe(12500)
    expect(parseDisplayQuantity('3', 'piece')).toBe(3)
    expect(Number.isNaN(parseDisplayQuantity('abc', 'm'))).toBe(true)
  })
})
