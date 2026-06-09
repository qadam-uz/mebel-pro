import { describe, expect, it } from 'vitest'

import { formatDate, formatDateInputValue, formatTiyin } from '@/shared/formatters'
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

  it('has labels for each role app', () => {
    expect(Object.keys(i18nSeed)).toEqual(['client', 'workshop', 'admin'])
  })
})
