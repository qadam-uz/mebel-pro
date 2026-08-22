import { describe, expect, it } from 'vitest'

import {
  deriveEdgeRegistry,
  edgeRegistryKey,
  groupCuttingParts,
  isGeometryNeutralEdit,
  partDisplayName,
  previewEdgeAssignments,
  registryColorStyle,
  shortMaterialName,
  syncEdgeAssignments,
} from '@/shared/app/cuttingEditorDerived'
import type { ClientCatalogMaterialOption, CuttingPart } from '@/shared/stores/cutting'

// WCAG 2.x relative luminance and contrast, on `#rrggbb` only — the ramp's fixed
// entries are all hex, and the generated ones are asserted by value, not ratio.
function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5].map((offset) => {
    const value = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }) as [number, number, number]
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}

function contrastRatio(foreground: string, background: string): number {
  const [light, dark] = [relativeLuminance(foreground), relativeLuminance(background)].sort(
    (a, b) => b - a,
  ) as [number, number]
  return (light + 0.05) / (dark + 0.05)
}

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: overrides.part_ref ?? `part-${Math.random()}`,
    name: null,
    material_id: '',
    material_source: 'shop',
    follow_grain: true,
    thickened: false,
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
            thickened: false,
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
    expect(registryColorStyle(1).bg).toBe('#49740e')
    expect(registryColorStyle(2).bg).toBe('#D85A30')
    expect(registryColorStyle(11).bg).toMatch(/^hsl\(/)
  })

  it('never paints a chip with the retired brand blue', () => {
    for (const number of [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 25]) {
      expect(registryColorStyle(number).bg.toLowerCase()).not.toBe('#4341c6')
    }
  })

  // The chip number renders at 12px on the fill, so it owes the full 4.5:1. Bone
  // (`--color-on-accent`) is specified for text on GRAPHITE — on a saturated
  // mid-tone it only costs contrast, and it took the green and the ochre under
  // the floor. This asserts the pairing rather than trusting the eye, because a
  // token swap in either direction passes every other gate.
  it('pairs a filled chip with white, never the bone on-accent', () => {
    for (const number of [1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 25]) {
      expect(registryColorStyle(number).fg).toBe('#ffffff')
    }
    // The one fill light enough to fail with any near-white takes ink instead.
    expect(registryColorStyle(5)).toMatchObject({ bg: '#ca8a04', fg: '#111827' })
  })

  it('clears 4.5:1 on the two fills the bone pairing had pushed under it', () => {
    const BONE = '#f4f2ee'
    for (const number of [8, 10]) {
      const style = registryColorStyle(number)
      expect(contrastRatio(style.fg, style.bg)).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(BONE, style.bg)).toBeLessThan(4.5)
    }
  })
})

// NOTE: every `material_id` in this file is a CuttingPart / CuttingEdgeBand field.
// The backend deliberately kept those names — only CuttingPanel, OrderItem and the
// inventory FKs became `branch_material_id`. A repo-wide rename breaks this file.
describe('shortMaterialName', () => {
  function option(overrides: Partial<ClientCatalogMaterialOption>): ClientCatalogMaterialOption {
    return {
      id: 'bm-abcdefgh-9999',
      type: 'ldsp',
      manufacturer_id: 'mf1',
      manufacturer_name: 'Egger',
      code: null,
      name: '',
      has_grain: false,
      image_file_id: null,
      thickness_mm: '18',
      length_mm: 2800,
      width_mm: 2070,
      tape_width_mm: null,
      price_tiyin: 0,
      price_unset: true,
      display_unit: 'sheet',
      ...overrides,
    }
  }

  // Three rungs now, not four: `name` is gone and `color` became `name`.
  it('prefers code, then name, then an id fragment', () => {
    expect(shortMaterialName(option({ code: 'H1334', name: 'Sanoma' }))).toBe('H1334')
    expect(shortMaterialName(option({ code: null, name: 'Sanoma' }))).toBe('Sanoma')
    expect(shortMaterialName(option({ code: null, name: '' }))).toBe('bm-abcde')
  })

  it('falls back to the catalog string when there is no material at all', () => {
    expect(shortMaterialName(null)).toBe('Material')
  })
})
