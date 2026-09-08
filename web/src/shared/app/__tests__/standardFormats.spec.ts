import { describe, expect, it } from 'vitest'

import {
  formatDraftKey,
  formatDraftLabel,
  hasFinishedSides,
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

describe('format drafts', () => {
  const board = {
    type: 'ldsp' as const,
    thickness_mm: '18',
    length_mm: 2750,
    width_mm: 1830,
    tape_width_mm: null,
    finished_sides: 2,
  }
  const tape = {
    type: 'kromka' as const,
    thickness_mm: '0.8',
    length_mm: null,
    width_mm: null,
    tape_width_mm: 22,
    finished_sides: null,
  }

  it('keys a draft by every field that makes it a different product', () => {
    // A one-sided sheet is a different product at a different price, so the two
    // must never collapse into one row of the pending list.
    expect(formatDraftKey(board)).not.toBe(formatDraftKey({ ...board, finished_sides: 1 }))
    // …while `18` and `18.00` are the same thickness written twice.
    expect(formatDraftKey({ ...board, thickness_mm: '18.00' })).toBe(formatDraftKey(board))
  })

  it('reads a draft back in the order it was composed', () => {
    expect(formatDraftLabel(board)).toBe('18 mm · 2750×1830')
    expect(formatDraftLabel(tape)).toBe('0.8 mm · 22 mm')
    // Two finished faces is the norm and says nothing; one is the exception.
    expect(formatDraftLabel({ ...board, finished_sides: 1 }, '1 tomonlama')).toBe(
      '18 mm · 2750×1830 · 1 tomonlama',
    )
    expect(formatDraftLabel(board, '1 tomonlama')).toBe('18 mm · 2750×1830')
  })

  it('gives a finished-face count to the LAMINATED boards and nothing else', () => {
    // A finished face IS the laminate, so only LDSP and LMDF have one to count
    // (2026-09-08); bare DSP and MDF are raw on both faces, and the server
    // rejects the field on them.
    expect((['ldsp', 'lmdf'] as const).every(hasFinishedSides)).toBe(true)
    expect(
      (['dsp', 'mdf', 'fanera', 'yogoch', 'kromka', 'boshqa'] as const).some(hasFinishedSides),
    ).toBe(false)
  })

  it('offers LMDF the MDF chips — the press does not change what the mill cut', () => {
    expect(standardFormatSet('lmdf')).toEqual(standardFormatSet('mdf'))
    expect(standardFormatSet('lmdf').qalinliklar).toEqual(['3', '8', '16', '18'])
  })
})
