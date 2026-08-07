import { describe, expect, it } from 'vitest'

import {
  dekorTurLabel,
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
    tur: 'kromka',
    manufacturer_id: 'mf1',
    manufacturer_name: 'Egger',
    kod: 'H1334 ST9',
    nomi: 'Sanoma',
    tolali: false,
    image_file_id: null,
    qalinlik_mm: '0.4',
    uzunlik_mm: null,
    eni_mm: null,
    kromka_eni_mm: 20,
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

describe('dekorTurLabel / isTape', () => {
  it('labels both ldsp and dsp LDSP, exactly like the backend map', () => {
    expect(dekorTurLabel('ldsp')).toBe('LDSP')
    expect(dekorTurLabel('dsp')).toBe('LDSP')
    expect(dekorTurLabel('mdf')).toBe('MDF')
    expect(dekorTurLabel('fanera')).toBe('Fanera')
    expect(dekorTurLabel('yogoch')).toBe("Yog'och")
    expect(dekorTurLabel('kromka')).toBe('Kromka')
    expect(dekorTurLabel('boshqa')).toBe('List')
  })

  it('still labels the legacy snapshot-only panel types', () => {
    // These live on frozen pre-reshape snapshots forever. Dropping them renders
    // every historical order with a raw enum token in the type slot.
    expect(dekorTurLabel('plywood')).toBe('Fanera')
    expect(dekorTurLabel('natural_wood')).toBe("Yog'och")
    expect(dekorTurLabel('other')).toBe('List')
  })

  it('echoes an unknown value and treats only kromka as tape-shaped', () => {
    expect(dekorTurLabel('carbon')).toBe('carbon')
    expect(dekorTurLabel(null)).toBe('')
    expect(isTape('kromka')).toBe(true)
    expect(isTape('ldsp')).toBe(false)
    expect(isTape(null)).toBe(false)
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
        tur: 'ldsp',
        kod: 'H1334 ST9',
        nomi: 'Sanoma',
        qalinlik_mm: '18',
        uzunlik_mm: 2800,
        eni_mm: 2070,
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
    ).toBe('LDSP Egger H1334 ST9 · Sanoma · 2800×2070×18 mm')
  })

  it('prefers the new key when a snapshot somehow carries both', () => {
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Egger',
        tur: 'mdf',
        type: 'dsp',
        kod: 'NEW',
        decor_code: 'OLD',
        nomi: 'Sanoma',
        qalinlik_mm: '18',
      }),
    ).toBe('MDF Egger NEW · Sanoma · 18 mm')
  })

  it('suppresses nomi when the base already says it', () => {
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Egger',
        tur: 'ldsp',
        nomi: 'Sonoma eman',
        qalinlik_mm: '18',
        uzunlik_mm: 2800,
        eni_mm: 2070,
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
    ).toBe('LDSP Kronospan TD-W18 · White · 2800×2070×18 mm')
  })

  it('falls back to the thickness-only detail when a size is missing', () => {
    // A kromka row has uzunlik_mm/eni_mm null — this must not print «null×null mm».
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Egger',
        tur: 'kromka',
        kod: 'H1334',
        nomi: 'Sanoma',
        qalinlik_mm: '2.0',
        uzunlik_mm: null,
        eni_mm: null,
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
        kod: 'H1334 ST9',
        nomi: 'Sanoma',
        qalinlik_mm: '0.4',
        kromka_eni_mm: 20,
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
        nomi: 'Sonoma eman',
        qalinlik_mm: '2',
        kromka_eni_mm: 36,
      }),
    ).toBe('Egger Sonoma eman · 2×36 mm')
  })
})

describe('snapshotShortLabel', () => {
  it('uses kod, then nomi, then a clipped legacy name — in both vocabularies', () => {
    expect(snapshotShortLabel({ kod: 'H1334', nomi: 'Oak' })).toBe('H1334')
    expect(snapshotShortLabel({ decor_code: 'H1334', color: 'Oak', name: 'Panel' })).toBe('H1334')
    expect(snapshotShortLabel({ kod: null, nomi: 'Oak' })).toBe('Oak')
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
          tur: 'ldsp',
          qalinlik_mm: '18',
          uzunlik_mm: 2800,
          eni_mm: 2070,
          kromka_eni_mm: null,
        }),
      ),
    ).toBe('LDSP Egger H1334 ST9 · Sanoma · 2800×2070×18 mm')
  })

  it('falls back to the first 8 characters of the branch-material id', () => {
    expect(materialOptionLabel(option({ manufacturer_name: '', kod: null, nomi: '' }))).toBe(
      'bm-12345 · 0.4×20 mm',
    )
  })
})
