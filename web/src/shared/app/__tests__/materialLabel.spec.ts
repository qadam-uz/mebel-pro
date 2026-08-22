import { describe, expect, it } from 'vitest'

import {
  decorTypeFilterGroups,
  decorTypeLabel,
  finishedSidesLabel,
  formatMm,
  isTape,
  materialOptionLabel,
  snapshotEdgeLabel,
  snapshotMaterialLabel,
  snapshotShortLabel,
} from '@/shared/app/materialLabel'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

function option(overrides: Partial<ClientCatalogMaterialOption> = {}): ClientCatalogMaterialOption {
  return {
    id: 'bm-12345678-abcd',
    type: 'kromka',
    manufacturer_id: 'mf1',
    manufacturer_name: 'Egger',
    code: 'H1334 ST9',
    name: 'Sanoma',
    has_grain: false,
    image_file_id: null,
    thickness_mm: '0.4',
    length_mm: null,
    width_mm: null,
    tape_width_mm: 20,
    price_tiyin: 0,
    price_unset: true,
    display_unit: 'm',
    ...overrides,
  }
}

describe('formatMm', () => {
  it('strips a trailing .0 but keeps real precision (mirrors _format_mm)', () => {
    expect(formatMm('18.0')).toBe('18')
    expect(formatMm('18.00')).toBe('18')
    expect(formatMm('2.0')).toBe('2')
    expect(formatMm('0.40')).toBe('0.4')
    expect(formatMm('0.8')).toBe('0.8')
    expect(formatMm('1.50')).toBe('1.5')
    expect(formatMm(18)).toBe('18')
  })

  it('echoes anything that is not a number and never turns "" into 0', () => {
    expect(formatMm('n/a')).toBe('n/a')
    expect(formatMm('')).toBe('')
    expect(formatMm(null)).toBe('')
  })
})

describe('decorTypeLabel / isTape', () => {
  it('gives every type its own label, exactly like the backend map', () => {
    // `dsp` used to borrow LDSP's word, which made chipboard and laminated
    // chipboard indistinguishable on every screen and document even though they
    // are different products at different prices.
    expect(decorTypeLabel('ldsp')).toBe('LDSP')
    expect(decorTypeLabel('dsp')).toBe('DSP')
    expect(decorTypeLabel('mdf')).toBe('MDF')
    expect(decorTypeLabel('fanera')).toBe('Fanera')
    expect(decorTypeLabel('yogoch')).toBe("Yog'och")
    expect(decorTypeLabel('kromka')).toBe('Kromka')
    expect(decorTypeLabel('boshqa')).toBe('List')
  })

  it('still labels the legacy snapshot-only panel types', () => {
    // These live on frozen pre-reshape snapshots forever. Dropping them renders
    // every historical order with a raw enum token in the type slot.
    expect(decorTypeLabel('plywood')).toBe('Fanera')
    expect(decorTypeLabel('natural_wood')).toBe("Yog'och")
    expect(decorTypeLabel('other')).toBe('List')
  })

  it('echoes an unknown value and treats only kromka as tape-shaped', () => {
    expect(decorTypeLabel('carbon')).toBe('carbon')
    expect(decorTypeLabel(null)).toBe('')
    expect(isTape('kromka')).toBe(true)
    expect(isTape('ldsp')).toBe(false)
    expect(isTape(null)).toBe(false)
  })
})

describe('finished sides', () => {
  it('prints «1 tomonlama» for a one-sided board and nothing for a two-sided one', () => {
    // Two-sided is the norm; saying so on every row would be noise. One-sided
    // is a different product at a different price, and the buyer has to see it.
    const base = {
      manufacturer_name: 'Egger',
      type: 'ldsp',
      code: 'H1334',
      name: 'Sanoma',
      thickness_mm: '18',
      length_mm: 2800,
      width_mm: 2070,
    }
    expect(snapshotMaterialLabel({ ...base, finished_sides: 1 })).toBe(
      'LDSP Egger H1334 · Sanoma · 2800×2070×18 mm · 1 tomonlama',
    )
    expect(snapshotMaterialLabel({ ...base, finished_sides: 2 })).toBe(
      'LDSP Egger H1334 · Sanoma · 2800×2070×18 mm',
    )
    // A kromka and a plank carry no finished-face count at all.
    expect(snapshotMaterialLabel({ ...base, finished_sides: null })).toBe(
      'LDSP Egger H1334 · Sanoma · 2800×2070×18 mm',
    )
  })

  it('labels the two values and ignores anything else', () => {
    expect(finishedSidesLabel(1)).toBe('1 tomonlama')
    expect(finishedSidesLabel(2)).toBe('2 tomonlama')
    expect(finishedSidesLabel(null)).toBe('')
    expect(finishedSidesLabel(0)).toBe('')
  })
})

describe('decorTypeFilterGroups', () => {
  it('offers one choice per label, with every wire value behind it', () => {
    // The grouping stays — it is what stops two types with one name showing the
    // same option twice — but now that `dsp` has its own word, every group
    // happens to hold exactly one value. The helper is kept rather than
    // inlined: the moment two types share a label again, the filter must not
    // silently start printing a duplicate choice.
    expect(decorTypeFilterGroups()).toEqual([
      { label: 'LDSP', types: ['ldsp'] },
      { label: 'DSP', types: ['dsp'] },
      { label: 'MDF', types: ['mdf'] },
      { label: 'Fanera', types: ['fanera'] },
      { label: "Yog'och", types: ['yogoch'] },
      { label: 'Kromka', types: ['kromka'] },
      { label: 'List', types: ['boshqa'] },
    ])
  })
})

// The two vocabularies must produce IDENTICAL strings. The legacy cases are the
// regression guard for pre-reshape orders — the migration does not rewrite
// material_snapshot / material_snapshots, so both live in the database forever.
describe('snapshotMaterialLabel — dual vocabulary', () => {
  it('reads new keys', () => {
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Egger',
        type: 'ldsp',
        code: 'H1334 ST9',
        name: 'Sanoma',
        thickness_mm: '18',
        length_mm: 2800,
        width_mm: 2070,
      }),
    ).toBe('LDSP Egger H1334 ST9 · Sanoma · 2800×2070×18 mm')
  })

  it('reads legacy keys to the same string', () => {
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Egger',
        type: 'dsp',
        decor_code: 'H1334 ST9',
        color: 'Sanoma',
        thickness_mm: '18',
        panel_length_mm: 2800,
        panel_width_mm: 2070,
      }),
      // `dsp` reads «DSP» now — it stopped borrowing LDSP's word.
    ).toBe('DSP Egger H1334 ST9 · Sanoma · 2800×2070×18 mm')
  })

  it('prefers the new key when a snapshot somehow carries both', () => {
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Egger',
        type: 'mdf',
        tur: 'dsp',
        code: 'NEW',
        kod: 'UZ',
        decor_code: 'OLD',
        name: 'Sanoma',
        thickness_mm: '18',
      }),
    ).toBe('MDF Egger NEW · Sanoma · 18 mm')
  })

  it('suppresses nomi when the base already says it', () => {
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Egger',
        type: 'ldsp',
        name: 'Sonoma eman',
        thickness_mm: '18',
        length_mm: 2800,
        width_mm: 2070,
      }),
    ).toBe('LDSP Egger Sonoma eman · 2800×2070×18 mm')
  })

  it('keeps the legacy `name` in the identity slot ahead of nomi', () => {
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Kronospan',
        type: 'dsp',
        name: 'TD-W18',
        color: 'White',
        thickness_mm: '18.0',
        panel_length_mm: 2800,
        panel_width_mm: 2070,
      }),
    ).toBe('DSP Kronospan TD-W18 · White · 2800×2070×18 mm')
  })

  it('falls back to the thickness-only detail when a size is missing', () => {
    // A kromka row has length_mm/width_mm null — this must not print «null×null mm».
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Egger',
        type: 'kromka',
        code: 'H1334',
        name: 'Sanoma',
        thickness_mm: '2.0',
        length_mm: null,
        width_mm: null,
      }),
    ).toBe('Kromka Egger H1334 · Sanoma · 2 mm')
  })

  it('uses the fallback when the snapshot has no identity at all', () => {
    expect(snapshotMaterialLabel({}, 'abcd1234')).toBe('abcd1234')
    expect(snapshotMaterialLabel(undefined, 'abcd1234')).toBe('abcd1234')
  })
})

describe('snapshotEdgeLabel — dual vocabulary', () => {
  it('reads new keys', () => {
    expect(
      snapshotEdgeLabel({
        manufacturer_name: 'Egger',
        code: 'H1334 ST9',
        name: 'Sanoma',
        thickness_mm: '0.4',
        tape_width_mm: 20,
      }),
    ).toBe('Egger H1334 ST9 · Sanoma · 0.4×20 mm')
  })

  it('reads legacy keys to the same string', () => {
    expect(
      snapshotEdgeLabel({
        manufacturer_name: 'Egger',
        decor_code: 'H1334 ST9',
        color: 'Sanoma',
        thickness_mm: '0.4',
        edge_width_mm: 20,
      }),
    ).toBe('Egger H1334 ST9 · Sanoma · 0.4×20 mm')
  })

  it('suppresses nomi for a kod-less tape instead of repeating it', () => {
    // «Egger Sonoma eman · Sonoma eman · 2×36 mm» is the defect this guards.
    expect(
      snapshotEdgeLabel({
        manufacturer_name: 'Egger',
        name: 'Sonoma eman',
        thickness_mm: '2',
        tape_width_mm: 36,
      }),
    ).toBe('Egger Sonoma eman · 2×36 mm')
  })
})

describe('snapshotShortLabel', () => {
  it('uses kod, then nomi, then a clipped legacy name — in both vocabularies', () => {
    expect(snapshotShortLabel({ code: 'H1334', name: 'Oak' })).toBe('H1334')
    expect(snapshotShortLabel({ decor_code: 'H1334', color: 'Oak', name: 'Panel' })).toBe('H1334')
    expect(snapshotShortLabel({ code: null, name: 'Oak' })).toBe('Oak')
    expect(snapshotShortLabel({ decor_code: null, color: 'Oak', name: 'Panel' })).toBe('Oak')
    expect(snapshotShortLabel({ name: 'Generated material label' })).toBe('Generated material')
  })
})

describe('materialOptionLabel', () => {
  it('composes a tape option through the edge shape', () => {
    expect(materialOptionLabel(option())).toBe('Egger H1334 ST9 · Sanoma · 0.4×20 mm')
  })

  it('composes a panel option through the panel shape', () => {
    expect(
      materialOptionLabel(
        option({
          type: 'ldsp',
          thickness_mm: '18',
          length_mm: 2800,
          width_mm: 2070,
          tape_width_mm: null,
        }),
      ),
    ).toBe('LDSP Egger H1334 ST9 · Sanoma · 2800×2070×18 mm')
  })

  it('falls back to the first 8 characters of the branch-material id', () => {
    expect(materialOptionLabel(option({ manufacturer_name: '', code: null, name: '' }))).toBe(
      'bm-12345 · 0.4×20 mm',
    )
  })
})
