import { describe, expect, it } from 'vitest'

import {
  deriveSnapshotEdgeRegistry,
  groupPanelPlacements,
  offcutLabelMode,
  panelDisplayIndex,
  snapshotShortLabel,
} from '@/shared/app/cuttingResultsDisplay'
import type { CuttingPanel, CuttingPart, CuttingResult } from '@/shared/stores/cutting'

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'part-a',
    name: null,
    material_id: 'panel-a',
    material_source: 'shop',
    follow_grain: true,
    length_mm: 300,
    width_mm: 200,
    quantity: 1,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
    ...overrides,
  }
}

function result(overrides: Partial<CuttingResult> = {}): CuttingResult {
  return {
    id: 'result-a',
    draft_id: 'draft-a',
    algorithm_name: 'guillotine',
    algorithm_version: '1',
    source: 'optimizer',
    status: 'candidate',
    kerf_mm: 4,
    edge_trim_mm: 5,
    panels_used_by_material: { 'panel-a': 1 },
    waste_percentage: '0.12',
    total_cut_length_mm: 0,
    total_edge_length_mm: 0,
    edge_length_by_material: {},
    parts_snapshot: [],
    material_snapshots: {},
    edge_length_shop_by_material: {},
    edge_length_own_by_material: {},
    edge_consumed_shop_by_material: {},
    edge_consumed_own_by_material: {},
    edge_banded_sides_by_material: {},
    order_id: null,
    created_at: '',
    confirmed_at: null,
    invalidated_at: null,
    panels: [],
    ...overrides,
  }
}

describe('cutting results display helpers', () => {
  it('uses one snapshot short-label ladder', () => {
    expect(snapshotShortLabel({ decor_code: 'H1334', color: 'Oak', name: 'Long name' })).toBe(
      'H1334',
    )
    expect(snapshotShortLabel({ decor_code: null, color: 'Oak', name: 'Long name' })).toBe('Oak')
    expect(snapshotShortLabel({ name: 'Very long generated material name' })).toBe(
      'Very long generate',
    )
  })

  it('chooses offcut label modes without clipping narrow remnants', () => {
    expect(
      offcutLabelMode({ x_mm: 0, y_mm: 0, length_mm: 700, width_mm: 120, usable: true }, 0.4),
    ).toEqual({ text: 'Qoldiq 700×120', orientation: 'horizontal' })
    expect(
      offcutLabelMode({ x_mm: 0, y_mm: 0, length_mm: 322, width_mm: 1820, usable: true }, 0.27)
        ?.orientation,
    ).toBe('vertical')
    expect(
      offcutLabelMode({ x_mm: 0, y_mm: 0, length_mm: 30, width_mm: 30, usable: true }, 0.4),
    ).toBeNull()
  })

  it('derives snapshot edge registry in first-use order', () => {
    const entries = deriveSnapshotEdgeRegistry([
      part({ edge_top: { material_id: 'edge-a', source: 'shop' } }),
      part({ edge_top: { material_id: 'edge-b', source: 'shop' } }),
    ])

    expect(entries.map((entry) => [entry.materialId, entry.number])).toEqual([
      ['edge-a', 1],
      ['edge-b', 2],
    ])
  })

  it('groups active sheet placements by part with counts and rotation', () => {
    const panel: CuttingPanel = {
      id: 'panel-a',
      material_id: 'panel-a',
      panel_index: 1,
      waste_area_mm2: 0,
      offcuts: [],
      placements: [
        {
          id: 'p1',
          part_ref: 'part-a',
          part_quantity_index: 1,
          x_mm: 0,
          y_mm: 0,
          length_mm: 300,
          width_mm: 200,
          rotated: false,
        },
        {
          id: 'p2',
          part_ref: 'part-a',
          part_quantity_index: 2,
          x_mm: 300,
          y_mm: 0,
          length_mm: 200,
          width_mm: 300,
          rotated: true,
        },
      ],
    }
    const cuttingResult = result({
      parts_snapshot: [
        part({
          name: 'Shelf',
          edge_top: { material_id: 'edge-a', source: 'shop' },
          edge_left: { material_id: 'edge-b', source: 'shop' },
        }),
      ],
      panels: [panel],
    })

    expect(groupPanelPlacements(cuttingResult, panel)).toEqual([
      {
        partRef: 'part-a',
        name: 'Shelf',
        length_mm: 300,
        width_mm: 200,
        count: 2,
        rotatedCount: 1,
      },
    ])
  })

  it('uses drawing-wide panel order for displayed list numbers', () => {
    const first: CuttingPanel = {
      id: 'first',
      material_id: 'panel-a',
      panel_index: 1,
      waste_area_mm2: 0,
      offcuts: [],
      placements: [],
    }
    const secondMaterialFirstPanel: CuttingPanel = {
      id: 'second-material-first',
      material_id: 'panel-b',
      panel_index: 1,
      waste_area_mm2: 0,
      offcuts: [],
      placements: [],
    }
    const cuttingResult = result({ panels: [first, secondMaterialFirstPanel] })

    expect(panelDisplayIndex(cuttingResult, secondMaterialFirstPanel)).toBe(2)
  })
})
