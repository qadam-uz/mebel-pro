import { describe, expect, it } from 'vitest'

import {
  colorForMaterial,
  edgeFields,
  edgeSearchText,
  edgeShortLabel,
  edgeTinyLabel,
  sideLabels,
  snapshotEdgeLabel,
  snapshotMaterialLabel,
  snapshotShortLabel,
} from '@/shared/app/cuttingDisplay'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

function material(
  overrides: Partial<ClientCatalogMaterialOption> = {},
): ClientCatalogMaterialOption {
  return {
    id: 'm1',
    kind: 'edge',
    manufacturer_id: 'mf1',
    manufacturer_name: 'Egger Group',
    type: null,
    name: 'ABS H1334',
    thickness_mm: '0.4',
    color: 'White',
    decor_code: 'H1334',
    panel_length_mm: null,
    panel_width_mm: null,
    grain_direction: null,
    edge_width_mm: 19,
    image_file_id: null,
    branch_carried: true,
    price_tiyin: null,
    display_unit: 'm',
    ...overrides,
  }
}

describe('edge field constants', () => {
  it('lists the four sides in render order with Uzbek labels', () => {
    expect(edgeFields).toEqual(['edge_top', 'edge_bottom', 'edge_left', 'edge_right'])
    expect(sideLabels.edge_top).toBe('Yuqori')
    expect(sideLabels.edge_right).toBe("O'ng")
  })
})

describe('colorForMaterial', () => {
  it('maps named colours (uz + en) to fixed swatches', () => {
    expect(colorForMaterial('Oq')).toBe('#f7f4ec')
    expect(colorForMaterial('white gloss')).toBe('#f7f4ec')
    expect(colorForMaterial('Qora')).toBe('#2a2d33')
    expect(colorForMaterial('grey')).toBe('#a7adb5')
    expect(colorForMaterial('Dub')).toBe('#c9aa73')
  })

  it('is deterministic for unnamed colours and tolerates null', () => {
    expect(colorForMaterial('Sahara Beige')).toBe(colorForMaterial('Sahara Beige'))
    expect(colorForMaterial(null)).toMatch(/^hsl\(/)
    expect(colorForMaterial(undefined)).toMatch(/^hsl\(/)
  })
})

describe('edgeShortLabel', () => {
  it('uses the generated material name without adding duplicate suffixes', () => {
    expect(edgeShortLabel(material())).toBe('ABS H1334')
    expect(edgeShortLabel(material(), true)).toBe('ABS H1334')
  })

  it('renders "-" for no material', () => {
    expect(edgeShortLabel(null)).toBe('-')
  })
})

describe('edgeTinyLabel', () => {
  it('uses the first manufacturer word + thickness', () => {
    expect(edgeTinyLabel(material())).toBe('Egger 0.4')
    expect(edgeTinyLabel(null)).toBe('-')
  })
})

describe('edgeSearchText', () => {
  it('lower-cases a searchable blob of the material fields', () => {
    expect(edgeSearchText(material())).toBe('egger group abs h1334 white h1334 0.4 19')
    expect(edgeSearchText(material({ decor_code: null }))).toBe(
      'egger group abs h1334 white  0.4 19',
    )
  })
})

describe('snapshotShortLabel', () => {
  it('uses decor, then colour, then a name prefix', () => {
    expect(snapshotShortLabel({ decor_code: 'H1334', color: 'Oak', name: 'Panel' })).toBe('H1334')
    expect(snapshotShortLabel({ decor_code: null, color: 'Oak', name: 'Panel' })).toBe('Oak')
    expect(snapshotShortLabel({ name: 'Generated material label' })).toBe('Generated material')
  })

  it('builds fuller result labels for panel and edge snapshots', () => {
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
    expect(
      snapshotMaterialLabel({
        manufacturer_name: 'Kronospan',
        type: 'dsp',
        decor_code: 'TD-W18',
        color: 'White',
        thickness_mm: '18.0',
        panel_length_mm: 2800,
        panel_width_mm: 2070,
      }),
    ).toBe('LDSP Kronospan TD-W18 · White · 2800×2070×18 mm')
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
})
