import { describe, expect, it } from 'vitest'

import { formatDate, formatTiyin } from '@/shared/formatters'
import { i18nSeed } from '@/shared/i18n'

describe('shared formatters', () => {
  it('formats tiyin as UZS without fractional digits', () => {
    expect(formatTiyin(12_345_600)).toContain('123')
  })

  it('formats dates with the Uzbek locale seed', () => {
    expect(formatDate(new Date('2026-06-02T00:00:00Z'))).toContain('2026')
  })

  it('has labels for each role app', () => {
    expect(Object.keys(i18nSeed)).toEqual(['client', 'workshop', 'admin'])
  })
})
