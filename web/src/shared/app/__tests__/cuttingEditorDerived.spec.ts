import { describe, expect, it } from 'vitest'

import {
  deriveEdgeRegistry,
  edgeRegistryKey,
  groupCuttingParts,
  isGeometryNeutralEdit,
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
  it.each([
    ['quantity', { quantity: 2 }],
    ['length_mm', { length_mm: 101 }],
    ['width_mm', { width_mm: 51 }],
    ['material_id', { material_id: 'panel-2' }],
    ['follow_grain', { follow_grain: false }],
  ] as const)('treats %s changes as geometry-affecting', (_field, change) => {
    expect(
      isGeometryNeutralEdit(
        [part({ part_ref: 'one', material_id: 'panel-1' })],
        [part({ part_ref: 'one', material_id: 'panel-1', ...change })],
      ),
    ).toBe(false)
  })

  it('treats adding or removing a part reference as geometry-affecting', () => {
    const original = [part({ part_ref: 'one', material_id: 'panel-1' })]
    expect(isGeometryNeutralEdit(original, [...original, part({ part_ref: 'two' })])).toBe(false)
    expect(isGeometryNeutralEdit([...original, part({ part_ref: 'two' })], original)).toBe(false)
  })

  it('keeps layouts for name, edge and material-source edits', () => {
    const original = part({
      part_ref: 'one',
      material_id: 'panel-1',
      edge_top: { material_id: 'edge-1', source: 'shop' },
    })
    expect(
      isGeometryNeutralEdit(
        [original],
        [
          {
            ...original,
            name: 'Shelf',
            material_source: 'own',
            edge_top: { material_id: 'edge-2', source: 'shop' },
          },
        ],
      ),
    ).toBe(true)
  })

  it('uses backend defaults for missing geometry fields', () => {
    expect(
      isGeometryNeutralEdit(
        [{ part_ref: 'one' }],
        [
          {
            part_ref: 'one',
            quantity: 0,
            length_mm: 0,
            width_mm: 0,
            material_id: null as unknown as string,
            follow_grain: true,
          },
        ],
      ),
    ).toBe(true)
  })

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

  it('compacts assignment numbers after an edge is removed', () => {
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
    ])

    const entries = deriveEdgeRegistry(
      [
        part({ edge_top: { material_id: 'edge-b', source: 'shop' } }),
        part({ edge_top: { material_id: 'edge-c', source: 'shop' } }),
      ],
      assignments,
    )

    expect(assignments.has(edgeRegistryKey('edge-a', 'shop'))).toBe(false)
    expect(entries.map((entry) => [entry.materialId, entry.number])).toEqual([['edge-b', 1]])
  })

  it('keeps a tape number when it is applied to more sides', () => {
    const assignments = new Map<string, number>()
    syncEdgeAssignments(assignments, [
      part({
        edge_top: { material_id: 'edge-a', source: 'shop' },
        edge_left: { material_id: 'edge-b', source: 'shop' },
      }),
    ])

    // B is now on three sides and occurs first in the side traversal. Its use
    // count must not change the established A=#1, B=#2 registry identity.
    syncEdgeAssignments(assignments, [
      part({
        edge_top: { material_id: 'edge-b', source: 'shop' },
        edge_bottom: { material_id: 'edge-b', source: 'shop' },
        edge_left: { material_id: 'edge-a', source: 'shop' },
        edge_right: { material_id: 'edge-b', source: 'shop' },
      }),
    ])

    expect([...assignments.entries()]).toEqual([
      [edgeRegistryKey('edge-a', 'shop'), 1],
      [edgeRegistryKey('edge-b', 'shop'), 2],
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
