import { describe, expect, it } from 'vitest'

import {
  branchFormatFacets,
  carriedFormatKeys,
  formatKey,
  nonStandardFacets,
  normalizePanelSize,
  normalizeQalinlik,
  standardFormatSet,
} from '@/shared/app/standardFormats'
import type { BranchMaterial } from '@/shared/stores/workshop'

function row(overrides: Partial<BranchMaterial> = {}): BranchMaterial {
  return {
    id: 'bm-1',
    branch_id: 'branch-1',
    dekor_id: 'dekor-1',
    dekor: {} as BranchMaterial['dekor'],
    qalinlik_mm: '18',
    uzunlik_mm: 2800,
    eni_mm: 2070,
    kromka_eni_mm: null,
    price_tiyin: 0,
    price_unset: true,
    min_stock: 0,
    status: 'active',
    label: 'LDSP Egger H1334',
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    ...overrides,
  }
}

describe('standard format sets', () => {
  it('gives ldsp and dsp the same set', () => {
    expect(standardFormatSet('dsp')).toEqual(standardFormatSet('ldsp'))
    expect(standardFormatSet('ldsp').qalinliklar).toEqual(['10', '16', '18', '25'])
    expect(standardFormatSet('ldsp').olchamlar).toEqual([
      { uzunlik_mm: 2750, eni_mm: 1830 },
      { uzunlik_mm: 2800, eni_mm: 2070 },
      { uzunlik_mm: 2440, eni_mm: 1830 },
    ])
  })

  it('gives kromka tape widths instead of panel sizes', () => {
    const kromka = standardFormatSet('kromka')
    expect(kromka.qalinliklar).toEqual(['0.4', '0.8', '1', '2'])
    expect(kromka.kromkaEnlar).toEqual([19, 22, 35, 42])
    expect(kromka.olchamlar).toEqual([])
  })

  it('leaves yogoch and boshqa empty on purpose', () => {
    // There is no common sheet size for solid timber or the catch-all bucket;
    // prefilling one would seed the table with formats nobody stocks. Those two
    // are entered through "+ qo'shish" alone.
    for (const tur of ['yogoch', 'boshqa'] as const) {
      expect(standardFormatSet(tur).qalinliklar).toEqual([])
      expect(standardFormatSet(tur).olchamlar).toEqual([])
    }
  })
})

describe('normalization', () => {
  it('puts the longer side first so one size is never two chips', () => {
    expect(normalizePanelSize(1830, 2750)).toEqual({ uzunlik_mm: 2750, eni_mm: 1830 })
    expect(normalizePanelSize(2750, 1830)).toEqual({ uzunlik_mm: 2750, eni_mm: 1830 })
    expect(normalizePanelSize(1525, 1525)).toEqual({ uzunlik_mm: 1525, eni_mm: 1525 })
  })

  it('treats 18, 18.0 and 18.00 as one thickness', () => {
    expect(normalizeQalinlik('18.00')).toBe('18')
    expect(normalizeQalinlik('18.0')).toBe(normalizeQalinlik('18'))
    expect(normalizeQalinlik('0.40')).toBe('0.4')
  })

  it('keys a format past both normalizations', () => {
    expect(formatKey({ qalinlik_mm: '18.0', uzunlik_mm: 1830, eni_mm: 2750 })).toBe(
      formatKey({ qalinlik_mm: '18', uzunlik_mm: 2750, eni_mm: 1830 }),
    )
    expect(formatKey({ qalinlik_mm: '2', kromka_eni_mm: 19 })).not.toBe(
      formatKey({ qalinlik_mm: '2', kromka_eni_mm: 22 }),
    )
  })
})

describe('branch-derived facets', () => {
  const rows = [
    row({ id: 'a', qalinlik_mm: '18.0' }),
    row({ id: 'b', qalinlik_mm: '22', uzunlik_mm: 3050, eni_mm: 1300 }),
    // Stored short-side-first: must fold into the same chip as its normalized twin.
    row({ id: 'c', qalinlik_mm: '16', uzunlik_mm: 1830, eni_mm: 2750 }),
    row({ id: 'other-dekor', dekor_id: 'dekor-2', qalinlik_mm: '40' }),
  ]

  it('collects only this dekor’s formats, deduped and sorted', () => {
    const facets = branchFormatFacets(rows, 'dekor-1')
    expect(facets.qalinliklar).toEqual(['16', '18', '22'])
    expect(facets.olchamlar).toEqual([
      { uzunlik_mm: 2800, eni_mm: 2070 },
      { uzunlik_mm: 3050, eni_mm: 1300 },
      { uzunlik_mm: 2750, eni_mm: 1830 },
    ])
  })

  it('keeps only what the standard set does not already offer', () => {
    const custom = nonStandardFacets('ldsp', rows, 'dekor-1')
    expect(custom.qalinliklar).toEqual(['22'])
    expect(custom.olchamlar).toEqual([{ uzunlik_mm: 3050, eni_mm: 1300 }])
    expect(custom.kromkaEnlar).toEqual([])
  })

  it('derives tape widths, not panel sizes, for kromka', () => {
    const tapes = [
      row({ id: 't1', qalinlik_mm: '2', uzunlik_mm: null, eni_mm: null, kromka_eni_mm: 19 }),
      row({ id: 't2', qalinlik_mm: '2', uzunlik_mm: null, eni_mm: null, kromka_eni_mm: 28 }),
    ]
    const custom = nonStandardFacets('kromka', tapes, 'dekor-1')
    expect(custom.kromkaEnlar).toEqual([28])
    expect(custom.olchamlar).toEqual([])
  })

  it('lists the keys already carried so the cross product can disable them', () => {
    const keys = carriedFormatKeys(rows, 'dekor-1')
    expect(keys.has(formatKey({ qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070 }))).toBe(true)
    expect(keys.has(formatKey({ qalinlik_mm: '25', uzunlik_mm: 2800, eni_mm: 2070 }))).toBe(false)
    // A format of a different dekor is not this dekor's business.
    expect(keys.has(formatKey({ qalinlik_mm: '40', uzunlik_mm: 2800, eni_mm: 2070 }))).toBe(false)
  })
})
