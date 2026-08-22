import { describe, expect, it } from 'vitest'

import {
  normalizePanelSize,
  normalizeThickness,
  standardFormatSet,
} from '@/shared/app/standardFormats'

describe('standard format sets', () => {
  it('gives ldsp and dsp the same geometry', () => {
    // Same sheet, one with the laminate and one without: different products at
    // different prices, but a supplier cuts them from the same stock sizes, so
    // the platform form offers the same chips.
    expect(standardFormatSet('dsp')).toEqual(standardFormatSet('ldsp'))
    expect(standardFormatSet('ldsp').qalinliklar).toEqual(['10', '16', '18', '25'])
    expect(standardFormatSet('ldsp').olchamlar).toEqual([
      { length_mm: 2750, width_mm: 1830 },
      { length_mm: 2800, width_mm: 2070 },
      { length_mm: 2440, width_mm: 1830 },
    ])
  })

  it('gives kromka tape widths and no panel sizes', () => {
    const kromka = standardFormatSet('kromka')
    expect(kromka.olchamlar).toEqual([])
    expect(kromka.kromkaEnlar).toEqual([19, 22, 35, 42])
  })

  it('offers nothing for the types that have no common size', () => {
    // Solid timber and the "everything else" bucket have no standard sheet.
    // Offering one would put a number in front of the operator that no
    // manufacturer actually makes.
    for (const type of ['yogoch', 'boshqa'] as const) {
      expect(standardFormatSet(type)).toEqual({
        qalinliklar: [],
        olchamlar: [],
        kromkaEnlar: [],
      })
    }
  })
})

describe('normalizeThickness', () => {
  it('collapses the ways one thickness can be written', () => {
    // `18`, `18.0` and `18.00` are one format; comparing the raw text would
    // let the same product in twice under the natural key.
    expect(normalizeThickness('18.0')).toBe('18')
    expect(normalizeThickness('18.00')).toBe('18')
    expect(normalizeThickness('0.40')).toBe('0.4')
    expect(normalizeThickness('')).toBe('')
  })
})

describe('normalizePanelSize', () => {
  it('puts the longer side first, so a sheet has one spelling', () => {
    expect(normalizePanelSize(1830, 2750)).toEqual({ length_mm: 2750, width_mm: 1830 })
    expect(normalizePanelSize(2750, 1830)).toEqual({ length_mm: 2750, width_mm: 1830 })
    expect(normalizePanelSize(1525, 1525)).toEqual({ length_mm: 1525, width_mm: 1525 })
  })
})
