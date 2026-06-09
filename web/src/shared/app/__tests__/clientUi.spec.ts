import { describe, expect, it } from 'vitest'

import {
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
    expect(isUzPhone('+998 90 123 45 67')).toBe(true)
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

  it('formats optimizer waste ratios as percentages', () => {
    expect(formatPercent('0.1234')).toBe('12.34%')
    expect(formatPercent(18.5)).toBe('18.50%')
    expect(formatPercent(null)).toBe('-')
  })

  it('uses stable numeric compact dates', () => {
    expect(formatRelativeDate(new Date(2026, 5, 2, 9, 4))).toBe('02.06 09:04')
  })
})
