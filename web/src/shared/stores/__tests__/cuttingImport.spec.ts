import { describe, expect, it } from 'vitest'

import type { CuttingPart } from '@/shared/stores/cutting'
import {
  applyImportedParts,
  areImportMaterialPicksComplete,
  buildImportedParts,
  buildMapImportedParts,
  buildMapPanelPicks,
  isImportMappingComplete,
  type ImportParsedResponse,
} from '@/shared/stores/cuttingImport'

const parsed: ImportParsedResponse = {
  status: 'parsed',
  source_format: 'csv',
  total_parts: 2,
  total_pieces: 3,
  ignored_object_count: 0,
  panel_materials: [{ key: 'm1', label: 'EGGER H1334', part_count: 2, thickness_hint: '18' }],
  edge_materials: [{ key: 'e1', label: 'H1334 0.4', side_count: 2 }],
  skipped_rows: [],
  warnings: [],
  parts: [
    {
      row: 2,
      length_mm: 720,
      width_mm: 450,
      quantity: 2,
      material_key: 'm1',
      follow_grain: false,
      edges: { top: 'e1', bottom: 'e1', left: null, right: null },
    },
    {
      row: 3,
      length_mm: 300,
      width_mm: 200,
      quantity: 1,
      material_key: 'm1',
      follow_grain: true,
      edges: { top: null, bottom: null, left: null, right: null },
    },
  ],
}

function existingPart(): CuttingPart {
  return {
    part_ref: 'existing',
    name: null,
    material_id: 'panel-old',
    material_source: 'shop',
    follow_grain: true,
    length_mm: 100,
    width_mm: 100,
    quantity: 1,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
  }
}

describe('cutting import helpers', () => {
  it('builds CuttingPart rows with follow_grain, edge sides, and shop sources', () => {
    let nextId = 0

    const parts = buildImportedParts(
      parsed,
      { m1: 'panel-1' },
      { e1: 'edge-1' },
      () => `import-${++nextId}`,
    )

    expect(parts).toHaveLength(2)
    expect(parts[0]).toMatchObject({
      part_ref: 'import-1',
      name: null,
      material_id: 'panel-1',
      material_source: 'shop',
      follow_grain: false,
      length_mm: 720,
      width_mm: 450,
      quantity: 2,
      edge_top: { material_id: 'edge-1', source: 'shop' },
      edge_bottom: { material_id: 'edge-1', source: 'shop' },
      edge_left: null,
      edge_right: null,
    })
    expect(parts[1]).toMatchObject({
      part_ref: 'import-2',
      follow_grain: true,
      edge_top: null,
      edge_bottom: null,
      edge_left: null,
      edge_right: null,
    })
  })

  it('requires distinct length and width columns before parsing', () => {
    expect(isImportMappingComplete({ length_mm: 2 })).toBe(false)
    expect(isImportMappingComplete({ length_mm: 2, width_mm: 2 })).toBe(false)
    expect(isImportMappingComplete({ length_mm: 2, width_mm: 3 })).toBe(true)
  })

  it('requires every panel and edge group to be picked', () => {
    expect(areImportMaterialPicksComplete(parsed, { m1: 'panel-1' }, {})).toBe(false)
    expect(areImportMaterialPicksComplete(parsed, { m1: 'panel-1' }, { e1: 'edge-1' })).toBe(true)
  })

  it('applies imported rows by append or replace', () => {
    const existing = [existingPart()]
    const imported = buildImportedParts(parsed, { m1: 'panel-1' }, { e1: 'edge-1' }, () => 'new')

    expect(applyImportedParts(existing, imported, 'append').map((part) => part.part_ref)).toEqual([
      'existing',
      'new',
      'new',
    ])
    expect(applyImportedParts(existing, imported, 'replace')).toEqual(imported)
  })

  it('builds MAP import rows with stable part refs and panel picks', () => {
    const mapParsed: ImportParsedResponse = {
      ...parsed,
      source_format: 'map_2dplace',
      material_groups: [
        {
          key: 'm1',
          label: '2750x1830 mm list',
          width_mm: 2750,
          height_mm: 1830,
          sheet_count: 1,
          hint: null,
        },
      ],
      map_layout: {
        description: '',
        customer_name: '',
        order_type: '',
        sheets: [],
        part_rows: [
          {
            row: 1,
            part_ref: 'map-1',
            material_key: 'm1',
            length_mm: 720,
            width_mm: 450,
            quantity: 2,
            follow_grain: true,
            edges: { top: true, bottom: false, left: false, right: true },
            name: 'Side',
          },
        ],
      },
    }

    expect(buildMapPanelPicks(mapParsed, { m1: 'panel-1' })).toEqual({ m1: 'panel-1' })
    expect(buildMapImportedParts(mapParsed, { m1: 'panel-1' }, { e1: 'edge-1' })).toEqual([
      {
        part_ref: 'map-1',
        name: 'Side',
        material_id: 'panel-1',
        material_source: 'shop',
        follow_grain: true,
        length_mm: 720,
        width_mm: 450,
        quantity: 2,
        edge_top: { material_id: 'edge-1', source: 'shop' },
        edge_bottom: null,
        edge_left: null,
        edge_right: { material_id: 'edge-1', source: 'shop' },
      },
    ])
  })
})
