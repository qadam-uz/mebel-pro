import { describe, expect, it } from 'vitest'

import {
  deriveEdgeRegistry,
  groupCuttingParts,
  partDisplayName,
} from '@/shared/app/cuttingEditorDerived'
import type { CuttingPart } from '@/shared/stores/cutting'

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: overrides.part_ref ?? `part-${Math.random()}`,
    name: null,
    material_id: '',
    material_source: 'shop',
    follow_grain: true,
    length_mm: 100,
    width_mm: 50,
    quantity: 1,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
    ...overrides,
  }
}

describe('cuttingEditorDerived', () => {
  it('falls back to row display names without storing them', () => {
    expect(partDisplayName(part({ name: null }), 2)).toBe('D3')
    expect(partDisplayName(part({ name: 'Shelf' }), 2)).toBe('Shelf')
  })

  it('groups parts by material in first-seen order with summaries', () => {
    const groups = groupCuttingParts(
      [
        part({ material_id: 'b', length_mm: 100, width_mm: 100, quantity: 2 }),
        part({ material_id: '', length_mm: 100, width_mm: 50, quantity: 1 }),
        part({ material_id: 'a', length_mm: 50, width_mm: 50, quantity: 4 }),
        part({ material_id: 'b', length_mm: 100, width_mm: 100, quantity: 1 }),
      ],
      (id) => (id ? `Material ${id}` : 'missing'),
    )

    expect(groups.map((group) => group.key)).toEqual(['b', '__unassigned__', 'a'])
    expect(groups[0]).toMatchObject({ label: 'Material b', quantity: 3 })
    expect(groups[0].areaM2).toBeCloseTo(0.03)
    expect(groups[1]).toMatchObject({ label: 'Material tanlanmagan', quantity: 1 })
  })

  it('numbers distinct edge material and source pairs in first-seen order', () => {
    const entries = deriveEdgeRegistry([
      part({
        edge_top: { material_id: 'edge-a', source: 'shop' },
        edge_bottom: { material_id: 'edge-a', source: 'shop' },
      }),
      part({
        edge_left: { material_id: 'edge-a', source: 'own' },
        edge_right: { material_id: 'edge-b', source: 'shop' },
      }),
    ])

    expect(entries.map((entry) => [entry.materialId, entry.source, entry.number])).toEqual([
      ['edge-a', 'shop', 1],
      ['edge-a', 'own', 2],
      ['edge-b', 'shop', 3],
    ])
  })
})
