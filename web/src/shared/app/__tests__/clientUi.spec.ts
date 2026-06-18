import { describe, expect, it } from 'vitest'

import {
  clientErrorLabel,
  clientPhaseIndex,
  clientStatusPillClass,
  formatPercent,
  formatRelativeDate,
  isUzPhone,
  normalizeUzPhone,
} from '@/shared/app/clientUi'

describe('client UI helpers', () => {
  it('normalizes and validates Uzbek phone numbers', () => {
    expect(normalizeUzPhone('+998 90 123 45 67')).toBe('+998901234567')
    expect(normalizeUzPhone('901234567')).toBe('+998901234567')
    expect(normalizeUzPhone('0901234567')).toBe('+998901234567')
    expect(normalizeUzPhone('998901234567')).toBe('+998901234567')
    expect(normalizeUzPhone('8 998 90 123 45 67')).toBe('+998901234567')
    expect(isUzPhone('+998 90 123 45 67')).toBe(true)
    expect(isUzPhone('901234567')).toBe(true)
    expect(isUzPhone('+997901234567')).toBe(false)
  })

  it('maps client order phases and status pills', () => {
    expect(clientPhaseIndex('new')).toBe(0)
    expect(clientPhaseIndex('edge_banding')).toBe(2)
    expect(clientPhaseIndex('completed')).toBe(4)
    expect(clientPhaseIndex('cancelled')).toBe(-1)
    expect(clientStatusPillClass('ready')).toContain('client-pill-ready')
    expect(clientStatusPillClass('cancelled')).toContain('client-pill-danger')
  })

  it('formats optimizer waste ratios as percentages (0..1 fraction × 100)', () => {
    expect(formatPercent('0.1234')).toBe('12.34%')
    expect(formatPercent(0)).toBe('0.00%')
    expect(formatPercent(1)).toBe('100.00%')
    expect(formatPercent(null)).toBe('-')
    expect(formatPercent('')).toBe('-')
    expect(formatPercent('abc')).toBe('-')
  })

  it('uses stable numeric compact dates', () => {
    expect(formatRelativeDate(new Date(2026, 5, 2, 9, 4))).toBe('02.06 09:04')
  })

  it('maps client error codes to Uzbek copy, never leaking raw codes', () => {
    // known codes get specific Uzbek copy
    expect(clientErrorLabel('permission_denied')).toBe("Bu amal uchun ruxsat yo'q.")
    expect(clientErrorLabel('order_version_conflict')).toContain("o'zgardi")
    expect(clientErrorLabel('profile_update_failed')).toContain('Profilni')
    // unknown snake_case codes fall back to the generic Uzbek message, not the raw code
    expect(clientErrorLabel('some_unmapped_backend_code')).toBe(
      "Amal bajarilmadi. Qayta urinib ko'ring.",
    )
    expect(clientErrorLabel('some_unmapped_backend_code')).not.toContain('_')
    // null/empty → caller fallback (default or custom)
    expect(clientErrorLabel(null)).toBe("Amal bajarilmadi. Qayta urinib ko'ring.")
    expect(clientErrorLabel(undefined, 'Buyurtma yuborilmadi.')).toBe('Buyurtma yuborilmadi.')
    // an already-human sentence is returned unchanged
    expect(clientErrorLabel('Tarmoqqa ulanib bolmadi.')).toBe('Tarmoqqa ulanib bolmadi.')
  })
})
