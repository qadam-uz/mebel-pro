import { describe, expect, it } from 'vitest'

import {
  colorForMaterial,
  edgeFields,
  edgeSearchKey,
  edgeShortLabel,
  edgeTinyLabel,
  sideLabels,
} from '@/shared/app/cuttingDisplay'
import { matchesQuery } from '@/shared/app/searchFold'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

function material(
  overrides: Partial<ClientCatalogMaterialOption> = {},
): ClientCatalogMaterialOption {
  return {
    id: 'm1',
    type: 'kromka',
    manufacturer_id: 'mf1',
    manufacturer_name: 'Egger Group',
    code: 'H1334',
    name: 'White',
    has_grain: false,
    image_file_id: null,
    thickness_mm: '0.4',
    length_mm: null,
    width_mm: null,
    tape_width_mm: 19,
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

describe('edgeSearchKey', () => {
  // Kept, not deleted: this narrows the rows already loaded into the open edge
  // picker (a keyboard jump), it is not the catalog search. It is now the folded,
  // space-wrapped key of SPEC_CATALOG_SMART_SEARCH §1 rather than a lower-cased
  // blob, so «сонома» reaches it the way it reaches the server's own list.
  it('folds the material fields into a spaced search key', () => {
    expect(edgeSearchKey(material())).toBe(' egger group eggergroup white h1334 kromka 04 19 ')
    expect(edgeSearchKey(material({ code: null }))).toBe(
      ' egger group eggergroup white kromka 04 19 ',
    )
  })

  it('is script- and spelling-insensitive, and ANDs the query tokens', () => {
    const key = edgeSearchKey(material({ manufacturer_name: 'Egger', name: 'Sonoma eman' }))
    expect(matchesQuery(key, 'сонома')).toBe(true)
    expect(matchesQuery(key, 'egger sonoma')).toBe(true)
    expect(matchesQuery(key, 'h1334')).toBe(true)
    expect(matchesQuery(key, 'kromka')).toBe(true)
    // The thickness still narrows the list, as the lower-cased blob did.
    expect(matchesQuery(key, '0.4')).toBe(true)
    expect(matchesQuery(key, 'kronospan sonoma')).toBe(false)
  })
})
