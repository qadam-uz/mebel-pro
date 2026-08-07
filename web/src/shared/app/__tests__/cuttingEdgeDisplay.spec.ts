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
    tur: 'kromka',
    manufacturer_id: 'm1',
    manufacturer_name: 'AGT',
    kod: null,
    nomi: 'White',
    tolali: false,
    image_file_id: null,
    qalinlik_mm: '0.8',
    uzunlik_mm: null,
    eni_mm: null,
    kromka_eni_mm: 19,
    price_tiyin: 0,
    price_unset: false,
    display_unit: 'm',
    ...overrides,
  }
}

const panel = material({ id: 'panel', tur: 'ldsp', kod: 'H1334', nomi: 'Oak' })

describe('edgeRank (CB-130)', () => {
  it('ranks decor match 0, colour match 1, neither 2', () => {
    expect(edgeRank(panel, material({ kod: 'H1334', nomi: 'Other' }))).toBe(0)
    expect(edgeRank(panel, material({ kod: 'ZZ', nomi: 'oak' }))).toBe(1) // case-insensitive
    expect(edgeRank(panel, material({ kod: 'ZZ', nomi: 'Black' }))).toBe(2)
  })

  it('ranks 2 when there is no panel', () => {
    expect(edgeRank(null, material({ kod: 'H1334', nomi: 'Oak' }))).toBe(2)
  })
})

describe('rankedEdges (CB-130)', () => {
  it('sorts by rank, then width fit, then thickness, then manufacturer+name', () => {
    const decor = material({
      id: 'decor',
      kod: 'H1334',
      nomi: 'x',
      qalinlik_mm: '2',
      kromka_eni_mm: 42,
    })
    const colorWide = material({
      id: 'wide',
      kod: 'z',
      nomi: 'oak',
      qalinlik_mm: '0.4',
      kromka_eni_mm: 42,
    })
    const colorClosest = material({
      id: 'closest',
      kod: 'z',
      nomi: 'oak',
      qalinlik_mm: '2',
      kromka_eni_mm: 19,
    })
    const neither = material({ id: 'none', kod: 'z', nomi: 'black', qalinlik_mm: '0.4' })

    const ranked = rankedEdges(panel, [neither, colorWide, decor, colorClosest])
    expect(ranked.map((entry) => entry.material.id)).toEqual(['decor', 'closest', 'wide', 'none'])
    expect(ranked.map((entry) => entry.rank)).toEqual([0, 1, 1, 2])
  })

  // RENAME, not a behaviour change: the tiebreak used to read the server's stored
  // `name`; that column is gone and `kod || nomi` is the identity slot that string
  // started with, so the distinguishing text moves into `kod` — the field the
  // implementation actually reads. Putting it in `nomi` would still pass here
  // while diverging for real data, where `kod` is usually set.
  it('breaks rank+thickness ties by manufacturer then identity (tertiary sort)', () => {
    // same rank (colour match) and same thickness — only manufacturer/kod differ
    const egger = material({
      id: 'egger',
      kod: 'Zebra',
      nomi: 'oak',
      manufacturer_name: 'Egger',
    })
    const agtTape = material({
      id: 'agtTape',
      kod: 'Tape',
      nomi: 'oak',
      manufacturer_name: 'AGT',
    })
    const agtBand = material({
      id: 'agtBand',
      kod: 'Band',
      nomi: 'oak',
      manufacturer_name: 'AGT',
    })

    const ranked = rankedEdges(panel, [egger, agtTape, agtBand])
    expect(ranked.map((entry) => entry.material.id)).toEqual(['agtBand', 'agtTape', 'egger'])
  })
})

describe('edge width guidance', () => {
  it('prefers covering tapes closest to panel thickness and sinks narrow tapes', () => {
    expect(widthPenalty(18, material({ kromka_eni_mm: 19 }))).toBe(1)
    expect(widthPenalty(18, material({ kromka_eni_mm: 42 }))).toBe(24)
    expect(widthPenalty(18, material({ kromka_eni_mm: 16 }))).toBe(10_002)
    expect(edgeTooNarrow(18, material({ kromka_eni_mm: 16 }))).toBe(true)
    expect(edgeTooNarrow(18, material({ kromka_eni_mm: 42 }))).toBe(false)
  })

  it('keeps rank dominant over width and treats 42mm on 18mm as normal covering tape', () => {
    const decorWide = material({
      id: 'decor-wide',
      kod: 'H1334',
      nomi: 'x',
      kromka_eni_mm: 42,
    })
    const colorClosest = material({
      id: 'color-closest',
      kod: 'z',
      nomi: 'oak',
      kromka_eni_mm: 19,
    })

    const ranked = rankedEdges(panel, [colorClosest, decorWide])
    expect(ranked.map((entry) => entry.material.id)).toEqual(['decor-wide', 'color-closest'])
    expect(edgeTooNarrow(18, decorWide)).toBe(false)
  })
})

describe('recommendedEdge (CB-130)', () => {
  const edges = [
    material({ id: 'a', kod: 'z', nomi: 'black' }),
    material({ id: 'match', kod: 'H1334', nomi: 'x' }),
    material({ id: 'remembered', kod: 'z', nomi: 'black' }),
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

  it('uses document edges only when they match the panel decor or colour', () => {
    expect(recommendedEdge(panel, edges, null, null, [], ['a', 'match'])?.id).toBe('match')
  })

  it('does not arm a catalog edge when the draft has no usage candidate', () => {
    expect(recommendedEdge(panel, edges, null, null)).toBeNull()
  })

  it('returns null when there are no edges', () => {
    expect(recommendedEdge(panel, [], null, null)).toBeNull()
  })
})
