import { describe, expect, it } from 'vitest'

import { edgeRank, rankedEdges, recommendedEdge } from '@/shared/app/cuttingEdgeDisplay'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

function material(overrides: Partial<ClientCatalogMaterialOption>): ClientCatalogMaterialOption {
  return {
    id: 'x',
    kind: 'edge',
    manufacturer_id: 'm1',
    manufacturer_name: 'AGT',
    type: null,
    name: 'Tape',
    thickness_mm: '0.8',
    color: 'White',
    decor_code: null,
    panel_length_mm: null,
    panel_width_mm: null,
    grain_direction: null,
    image_file_id: null,
    branch_carried: true,
    price_tiyin: 0,
    display_unit: 'm',
    ...overrides,
  }
}

const panel = material({ id: 'panel', kind: 'panel', decor_code: 'H1334', color: 'Oak' })

describe('edgeRank (CB-130)', () => {
  it('ranks decor match 0, colour match 1, neither 2', () => {
    expect(edgeRank(panel, material({ decor_code: 'H1334', color: 'Other' }))).toBe(0)
    expect(edgeRank(panel, material({ decor_code: 'ZZ', color: 'oak' }))).toBe(1) // case-insensitive
    expect(edgeRank(panel, material({ decor_code: 'ZZ', color: 'Black' }))).toBe(2)
  })

  it('ranks 2 when there is no panel', () => {
    expect(edgeRank(null, material({ decor_code: 'H1334', color: 'Oak' }))).toBe(2)
  })
})

describe('rankedEdges (CB-130)', () => {
  it('sorts by rank, then thickness, then manufacturer+name', () => {
    const decor = material({ id: 'decor', decor_code: 'H1334', color: 'x', thickness_mm: '2' })
    const colorThin = material({ id: 'thin', decor_code: 'z', color: 'oak', thickness_mm: '0.4' })
    const colorThick = material({ id: 'thick', decor_code: 'z', color: 'oak', thickness_mm: '2' })
    const neither = material({ id: 'none', decor_code: 'z', color: 'black', thickness_mm: '0.4' })

    const ranked = rankedEdges(panel, [neither, colorThick, decor, colorThin])
    expect(ranked.map((entry) => entry.material.id)).toEqual(['decor', 'thin', 'thick', 'none'])
    expect(ranked.map((entry) => entry.rank)).toEqual([0, 1, 1, 2])
  })

  it('breaks rank+thickness ties by manufacturer then name (tertiary sort)', () => {
    // same rank (colour match) and same thickness — only manufacturer/name differ
    const egger = material({
      id: 'egger',
      decor_code: 'z',
      color: 'oak',
      manufacturer_name: 'Egger',
    })
    const agtTape = material({
      id: 'agtTape',
      decor_code: 'z',
      color: 'oak',
      manufacturer_name: 'AGT',
      name: 'Tape',
    })
    const agtBand = material({
      id: 'agtBand',
      decor_code: 'z',
      color: 'oak',
      manufacturer_name: 'AGT',
      name: 'Band',
    })

    const ranked = rankedEdges(panel, [egger, agtTape, agtBand])
    expect(ranked.map((entry) => entry.material.id)).toEqual(['agtBand', 'agtTape', 'egger'])
  })
})

describe('recommendedEdge (CB-130)', () => {
  const edges = [
    material({ id: 'a', decor_code: 'z', color: 'black' }),
    material({ id: 'match', decor_code: 'H1334', color: 'x' }),
    material({ id: 'remembered', decor_code: 'z', color: 'black' }),
  ]

  it('prefers the current pick over everything', () => {
    expect(recommendedEdge(panel, edges, 'a', 'remembered')?.id).toBe('a')
  })

  it('falls back to the remembered edge when nothing is picked', () => {
    expect(recommendedEdge(panel, edges, null, 'remembered')?.id).toBe('remembered')
  })

  it('falls back to the top-ranked edge when neither is set', () => {
    expect(recommendedEdge(panel, edges, null, null)?.id).toBe('match')
  })

  it('returns null when there are no edges', () => {
    expect(recommendedEdge(panel, [], null, null)).toBeNull()
  })
})
