import { describe, expect, it } from 'vitest'

import {
  colorForMaterial,
  edgeFields,
  edgeSearchText,
  edgeShortLabel,
  edgeTinyLabel,
  sideLabels,
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
  it('formats manufacturer · decor + colour, optionally with thickness', () => {
    expect(edgeShortLabel(material())).toBe('Egger Group · H1334 White')
    expect(edgeShortLabel(material(), true)).toBe('Egger Group · H1334 White · 0.4 mm')
  })

  it('drops the decor prefix when absent and renders "-" for no material', () => {
    expect(edgeShortLabel(material({ decor_code: null }))).toBe('Egger Group · White')
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
    expect(edgeSearchText(material())).toBe('egger group abs h1334 white h1334 0.4')
    expect(edgeSearchText(material({ decor_code: null }))).toBe('egger group abs h1334 white  0.4')
  })
})
