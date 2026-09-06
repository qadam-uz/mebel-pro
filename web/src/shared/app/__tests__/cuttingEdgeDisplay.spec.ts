import { describe, expect, it } from 'vitest'

import { edgeTooNarrow } from '@/shared/app/cuttingEdgeDisplay'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

function material(overrides: Partial<ClientCatalogMaterialOption>): ClientCatalogMaterialOption {
  return {
    id: 'x',
    type: 'kromka',
    manufacturer_id: 'm1',
    manufacturer_name: 'AGT',
    code: null,
    name: 'White',
    has_grain: false,
    image_file_id: null,
    thickness_mm: '0.8',
    length_mm: null,
    width_mm: null,
    tape_width_mm: 19,
    price_tiyin: 0,
    price_unset: false,
    display_unit: 'm',
    ...overrides,
  }
}

describe('edgeTooNarrow', () => {
  it('flags a tape narrower than the edge it has to cover', () => {
    expect(edgeTooNarrow(18, material({ tape_width_mm: 16 }))).toBe(true)
    expect(edgeTooNarrow(18, material({ tape_width_mm: 19 }))).toBe(false)
    // 42mm on an 18mm edge is the normal covering tape, trimmed flush — not a
    // warning.
    expect(edgeTooNarrow(18, material({ tape_width_mm: 42 }))).toBe(false)
  })

  it('says nothing when either side of the comparison is missing', () => {
    expect(edgeTooNarrow(null, material({ tape_width_mm: 16 }))).toBe(false)
    expect(edgeTooNarrow(18, null)).toBe(false)
    expect(edgeTooNarrow(18, material({ tape_width_mm: null }))).toBe(false)
  })
})
