import { describe, expect, it } from 'vitest'

import {
  edgeRank,
  edgeTooNarrow,
  rankedEdges,
  recommendedEdge,
  widthPenalty,
} from '@/shared/app/cuttingEdgeDisplay'
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

const panel = material({ id: 'panel', type: 'ldsp', code: 'H1334', name: 'Oak' })

describe('edgeRank (CB-130)', () => {
  it('ranks dekor match 0, colour match 1, neither 2', () => {
    expect(edgeRank(panel, material({ code: 'H1334', name: 'Other' }))).toBe(0)
    expect(edgeRank(panel, material({ code: 'ZZ', name: 'oak' }))).toBe(1) // case-insensitive
    expect(edgeRank(panel, material({ code: 'ZZ', name: 'Black' }))).toBe(2)
  })

  it('ranks 2 when there is no panel', () => {
    expect(edgeRank(null, material({ code: 'H1334', name: 'Oak' }))).toBe(2)
  })
})

describe('rankedEdges (CB-130)', () => {
  it('sorts by rank, then width fit, then thickness, then manufacturer+name', () => {
    const decor = material({
      id: 'decor',
      code: 'H1334',
      name: 'x',
      thickness_mm: '2',
      tape_width_mm: 42,
    })
    const colorWide = material({
      id: 'wide',
      code: 'z',
      name: 'oak',
      thickness_mm: '0.4',
      tape_width_mm: 42,
    })
    const colorClosest = material({
      id: 'closest',
      code: 'z',
      name: 'oak',
      thickness_mm: '2',
      tape_width_mm: 19,
    })
    const neither = material({ id: 'none', code: 'z', name: 'black', thickness_mm: '0.4' })

    const ranked = rankedEdges(panel, [neither, colorWide, decor, colorClosest])
    expect(ranked.map((entry) => entry.material.id)).toEqual(['decor', 'closest', 'wide', 'none'])
    expect(ranked.map((entry) => entry.rank)).toEqual([0, 1, 1, 2])
  })

  // RENAME, not a behaviour change: the tiebreak used to read the server's stored
  // `name`; that column is gone and `code || name` is the identity slot that string
  // started with, so the distinguishing text moves into `code` — the field the
  // implementation actually reads. Putting it in `name` would still pass here
  // while diverging for real data, where `code` is usually set.
  it('breaks rank+thickness ties by manufacturer then identity (tertiary sort)', () => {
    // same rank (colour match) and same thickness — only manufacturer/code differ
    const egger = material({
      id: 'egger',
      code: 'Zebra',
      name: 'oak',
      manufacturer_name: 'Egger',
    })
    const agtTape = material({
      id: 'agtTape',
      code: 'Tape',
      name: 'oak',
      manufacturer_name: 'AGT',
    })
    const agtBand = material({
      id: 'agtBand',
      code: 'Band',
      name: 'oak',
      manufacturer_name: 'AGT',
    })

    const ranked = rankedEdges(panel, [egger, agtTape, agtBand])
    expect(ranked.map((entry) => entry.material.id)).toEqual(['agtBand', 'agtTape', 'egger'])
  })
})

describe('edge width guidance', () => {
  it('prefers covering tapes closest to panel thickness and sinks narrow tapes', () => {
    expect(widthPenalty(18, material({ tape_width_mm: 19 }))).toBe(1)
    expect(widthPenalty(18, material({ tape_width_mm: 42 }))).toBe(24)
    expect(widthPenalty(18, material({ tape_width_mm: 16 }))).toBe(10_002)
    expect(edgeTooNarrow(18, material({ tape_width_mm: 16 }))).toBe(true)
    expect(edgeTooNarrow(18, material({ tape_width_mm: 42 }))).toBe(false)
  })

  it('keeps rank dominant over width and treats 42mm on 18mm as normal covering tape', () => {
    const decorWide = material({
      id: 'decor-wide',
      code: 'H1334',
      name: 'x',
      tape_width_mm: 42,
    })
    const colorClosest = material({
      id: 'color-closest',
      code: 'z',
      name: 'oak',
      tape_width_mm: 19,
    })

    const ranked = rankedEdges(panel, [colorClosest, decorWide])
    expect(ranked.map((entry) => entry.material.id)).toEqual(['decor-wide', 'color-closest'])
    expect(edgeTooNarrow(18, decorWide)).toBe(false)
  })
})

describe('recommendedEdge (CB-130)', () => {
  const edges = [
    material({ id: 'a', code: 'z', name: 'black' }),
    material({ id: 'match', code: 'H1334', name: 'x' }),
    material({ id: 'remembered', code: 'z', name: 'black' }),
  ]

  it('prefers the current pick over everything', () => {
    expect(recommendedEdge(panel, edges, 'a', 'remembered')?.id).toBe('a')
  })

  it('falls back to the remembered edge when nothing is picked', () => {
    expect(recommendedEdge(panel, edges, null, 'remembered')?.id).toBe('remembered')
  })

  it('falls back to a group-used edge before catalog ranking', () => {
    expect(recommendedEdge(panel, edges, null, null, ['remembered'])?.id).toBe('remembered')
  })

  it('uses document edges only when they match the panel dekor or colour', () => {
    expect(recommendedEdge(panel, edges, null, null, [], ['a', 'match'])?.id).toBe('match')
  })

  it('does not arm a catalog edge when the draft has no usage candidate', () => {
    expect(recommendedEdge(panel, edges, null, null)).toBeNull()
  })

  it('returns null when there are no edges', () => {
    expect(recommendedEdge(panel, [], null, null)).toBeNull()
  })
})
