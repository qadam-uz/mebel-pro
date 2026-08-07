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
    tur: 'kromka',
    manufacturer_id: 'mf1',
    manufacturer_name: 'Egger Group',
    kod: 'H1334',
    nomi: 'White',
    tolali: false,
    image_file_id: null,
    qalinlik_mm: '0.4',
    uzunlik_mm: null,
    eni_mm: null,
    kromka_eni_mm: 19,
    price_tiyin: 0,
    price_unset: true,
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
  // BEHAVIOUR CHANGE driven by the reshape: the option used to carry the server's
  // stored `name` ('ABS H1334') and this echoed it. That column is gone, so the
  // label is composed through the one composer — the same string the order review,
  // the PDF and the production card show for this tape.
  it('composes the canonical edge label without adding duplicate suffixes', () => {
    expect(edgeShortLabel(material())).toBe('Egger Group H1334 · White · 0.4×19 mm')
    expect(edgeShortLabel(material(), true)).toBe('Egger Group H1334 · White · 0.4×19 mm')
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
  // Kept, not deleted: this narrows the rows already loaded into the open edge
  // picker (a keyboard jump), it is not the catalog search. `name` left the blob
  // with the column; `kod` and `nomi` carry the signal now.
  it('lower-cases a searchable blob of the material fields', () => {
    expect(edgeSearchText(material())).toBe('egger group white h1334 0.4 19')
    expect(edgeSearchText(material({ kod: null }))).toBe('egger group white  0.4 19')
  })
})
