import { describe, expect, it } from 'vitest'

import {
  deriveEdgeRegistry,
  edgeRegistryKey,
  groupCuttingParts,
  partDisplayName,
  previewEdgeAssignments,
  registryColorStyle,
  syncEdgeAssignments,
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
    // Keep this fixture in sync with backend/tests/test_cutting_pdf_document.py:
    // test_edge_registry_matches_web_first_use_order.
    const rows = [
      part({
        edge_top: { material_id: 'edge-a', source: 'shop' },
        edge_bottom: { material_id: 'edge-a', source: 'shop' },
      }),
      part({
        edge_left: { material_id: 'edge-a', source: 'own' },
        edge_right: { material_id: 'edge-b', source: 'shop' },
      }),
    ]
    const assignments = new Map<string, number>()
    syncEdgeAssignments(assignments, rows)
    const entries = deriveEdgeRegistry(rows, assignments)

    expect(entries.map((entry) => [entry.materialId, entry.source, entry.number])).toEqual([
      ['edge-a', 'shop', 1],
      ['edge-a', 'own', 2],
      ['edge-b', 'shop', 3],
    ])
  })

  it('keeps assignment numbers stable when used edges are removed and added later', () => {
    const assignments = new Map<string, number>()
    syncEdgeAssignments(assignments, [
      part({ edge_top: { material_id: 'edge-a', source: 'shop' } }),
      part({ edge_top: { material_id: 'edge-b', source: 'shop' } }),
    ])
    syncEdgeAssignments(assignments, [
      part({ edge_top: { material_id: 'edge-b', source: 'shop' } }),
    ])
    syncEdgeAssignments(assignments, [
      part({ edge_top: { material_id: 'edge-b', source: 'shop' } }),
      part({ edge_top: { material_id: 'edge-c', source: 'shop' } }),
    ])

    const entries = deriveEdgeRegistry(
      [
        part({ edge_top: { material_id: 'edge-b', source: 'shop' } }),
        part({ edge_top: { material_id: 'edge-c', source: 'shop' } }),
      ],
      assignments,
    )

    expect(assignments.get(edgeRegistryKey('edge-a', 'shop'))).toBe(1)
    expect(entries.map((entry) => [entry.materialId, entry.number])).toEqual([
      ['edge-b', 2],
      ['edge-c', 3],
    ])
  })

  it('previews new edge numbers without mutating the live assignments', () => {
    const assignments = new Map<string, number>([[edgeRegistryKey('edge-a', 'shop'), 2]])
    const preview = previewEdgeAssignments(assignments, [
      edgeRegistryKey('edge-new', 'shop'),
      edgeRegistryKey('edge-a', 'shop'),
      edgeRegistryKey('edge-other', 'shop'),
    ])

    expect([...preview.entries()]).toEqual([
      [edgeRegistryKey('edge-new', 'shop'), 3],
      [edgeRegistryKey('edge-a', 'shop'), 2],
      [edgeRegistryKey('edge-other', 'shop'), 4],
    ])
    expect([...assignments.entries()]).toEqual([[edgeRegistryKey('edge-a', 'shop'), 2]])
  })

  it('uses fixed registry colours first and generated colours after ten entries', () => {
    expect(registryColorStyle(2).bg).toBe('#D85A30')
    expect(registryColorStyle(11).bg).toMatch(/^hsl\(/)
  })
})
