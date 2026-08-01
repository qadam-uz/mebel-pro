import { describe, expect, it } from 'vitest'

import {
  formatDate,
  formatDateInputValue,
  formatDateTime,
  formatRelative,
  formatStockQuantity,
  formatStockUnit,
  formatTiyin,
  formatTiyinParts,
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
    expect(formatRelative(new Date())).toBe('bugun')
    const threeDaysAgo = new Date()
    threeDaysAgo.setDate(threeDaysAgo.getDate() - 3)
    expect(formatRelative(threeDaysAgo)).toBe('3 kun oldin')
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
    expect(formatStockQuantity(5, 'panel')).toBe('5 list')
    expect(formatStockQuantity(12, 'piece')).toBe('12 dona')
  })

  it('localizes stock-unit enums, never surfacing a raw English enum', () => {
    expect(formatStockUnit('metre')).toBe('m')
    expect(formatStockUnit('m')).toBe('m')
    expect(formatStockUnit('panel')).toBe('list')
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

  it("pins the parser's deliberate policies: NBSP grouping and grouped-thousands dots", () => {
    // NBSP is what Intl.NumberFormat('uz-UZ') itself emits as the group separator.
    expect(parseSomToTiyin('12 500')).toBe(1_250_000)
    // "1.234" reads as grouped thousands (1 234 so'm), NOT as a 3-decimal fraction —
    // so'm amounts have no 3-decimal fractions, and misreading it 1000x down is the
    // exact bug the parser exists to prevent.
    expect(parseSomToTiyin('1.234')).toBe(123_400)
  })

  it('scales KPI money to mln/mlrd parts with the exact amount preserved in full', () => {
    const plain = formatTiyinParts(50_000_00)
    expect(plain.unit).toBe("so'm")
    expect(plain.full).toBe(formatTiyin(50_000_00))
    // amount + unit reassemble to the exact formatTiyin string (separator-proof).
    expect(`${plain.amount} ${plain.unit}`).toBe(formatTiyin(50_000_00))
    const millions = formatTiyinParts(12_500_000_00)
    expect(millions.amount).toBe('12,5')
    expect(millions.unit).toBe("mln so'm")
    expect(millions.full).toBe(formatTiyin(12_500_000_00))
    const billions = formatTiyinParts(2_400_000_000_00)
    expect(billions.amount).toBe('2,4')
    expect(billions.unit).toBe("mlrd so'm")
    // Negative net stays scaled with its sign.
    expect(formatTiyinParts(-12_500_000_00).unit).toBe("mln so'm")
    // Boundary quirk (documented): just under 1 mlrd renders as "1 000 mln so'm".
    expect(formatTiyinParts(999_999_999_00).unit).toBe("mln so'm")
  })

  it('parses display quantities back to storage units (mm for metres)', () => {
    expect(parseDisplayQuantity('12,5', 'm')).toBe(12500)
    expect(parseDisplayQuantity('12,5', 'metre')).toBe(12500)
    expect(parseDisplayQuantity('12.5', 'm')).toBe(12500)
    expect(parseDisplayQuantity('3', 'piece')).toBe(3)
    expect(Number.isNaN(parseDisplayQuantity('abc', 'm'))).toBe(true)
  })
})
