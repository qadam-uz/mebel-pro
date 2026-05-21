import { describe, expect, it } from 'vitest'
import {
  buildSvgLayout,
  cycleEdge,
  financeOpen,
  isActive,
  phaseIndex,
  presetEdges,
  relativeTime,
  summariseDraft,
  totalSheets,
} from '../cutting'
import type { CuttingResult, Draft, Material, Placement } from '../../api/types'

describe('5-phase mapping', () => {
  it('collapses cutting + edge_banding into "in production" (index 2)', () => {
    expect(phaseIndex('new')).toBe(0)
    expect(phaseIndex('confirmed')).toBe(1)
    expect(phaseIndex('cutting')).toBe(2)
    expect(phaseIndex('edge_banding')).toBe(2)
    expect(phaseIndex('ready')).toBe(3)
    expect(phaseIndex('completed')).toBe(4)
  })

  it('classifies active vs terminal statuses', () => {
    expect(isActive('new')).toBe(true)
    expect(isActive('ready')).toBe(true)
    expect(isActive('completed')).toBe(false)
    expect(isActive('cancelled')).toBe(false)
  })

  it('opens finance only at ready/completed', () => {
    expect(financeOpen('new')).toBe(false)
    expect(financeOpen('cutting')).toBe(false)
    expect(financeOpen('ready')).toBe(true)
    expect(financeOpen('completed')).toBe(true)
  })
})

describe('edges cycle + presets', () => {
  it('cycles None → 0.4 → 2.0 → None', () => {
    expect(cycleEdge(null)).toBe(0.4)
    expect(cycleEdge(0.4)).toBe(2.0)
    expect(cycleEdge(2.0)).toBe(null)
  })

  it('preset sets all four sides', () => {
    expect(presetEdges(2.0)).toEqual({ t: 2.0, b: 2.0, l: 2.0, r: 2.0 })
    expect(presetEdges(null)).toEqual({ t: null, b: null, l: null, r: null })
  })
})

describe('SVG placement transform', () => {
  // A 2800×2070 sheet, 10mm trim, rendered at 800px wide.
  const sheetW = 2800
  const sheetH = 2070
  const trim = 10
  const px = 800

  it('scales the sheet to the target pixel width keeping aspect ratio', () => {
    const layout = buildSvgLayout([], sheetW, sheetH, trim, px)
    expect(layout.viewW).toBe(800)
    // 2070/2800 * 800 = 591.4 → 591
    expect(layout.viewH).toBe(Math.round((sheetH / sheetW) * px))
    expect(layout.scale).toBeCloseTo(px / sheetW)
  })

  it('flips the y axis: a placement at the usable bottom-left lands near the SVG bottom', () => {
    // part 600×400 at the bottom-left of the usable area (x=0,y=0 in usable coords)
    const p: Placement = {
      part_ref: 'p1',
      part_quantity_index: 0,
      x_mm: 0,
      y_mm: 0,
      length_mm: 600,
      width_mm: 400,
      rotated: false,
    }
    const layout = buildSvgLayout([p], sheetW, sheetH, trim, px)
    const r = layout.rects[0]
    const scale = px / sheetW
    // x = trim (sheet coords) → trim*scale
    expect(r.x).toBeCloseTo(trim * scale)
    // top of the rect in sheet coords = sheetH - (trim + 0 + 400) = 1660
    expect(r.y).toBeCloseTo((sheetH - (trim + 400)) * scale)
    expect(r.w).toBeCloseTo(600 * scale)
    expect(r.h).toBeCloseTo(400 * scale)
  })

  it('places a part at the usable top correctly', () => {
    // usable height = 2070 - 20 = 2050; a part at y just below top
    const p: Placement = {
      part_ref: 'p2',
      part_quantity_index: 0,
      x_mm: 0,
      y_mm: 1650, // bottom of part 1650mm above usable origin
      length_mm: 600,
      width_mm: 400,
      rotated: false,
    }
    const layout = buildSvgLayout([p], sheetW, sheetH, trim, px)
    const scale = px / sheetW
    // top = sheetH - (trim + 1650 + 400) = 2070 - 2060 = 10
    expect(layout.rects[0].y).toBeCloseTo((sheetH - (trim + 1650 + 400)) * scale)
  })

  it('preserves the rotated flag and dims', () => {
    const p: Placement = {
      part_ref: 'p3',
      part_quantity_index: 1,
      x_mm: 100,
      y_mm: 200,
      length_mm: 300,
      width_mm: 250,
      rotated: true,
    }
    const layout = buildSvgLayout([p], sheetW, sheetH, trim, px)
    expect(layout.rects[0].rotated).toBe(true)
    expect(layout.rects[0].lengthMm).toBe(300)
    expect(layout.rects[0].widthMm).toBe(250)
    expect(layout.rects[0].qtyIndex).toBe(1)
  })
})

describe('draft summarising', () => {
  const materials: Material[] = [
    {
      id: 'm1',
      kind: 'sheet',
      type: null,
      name: 'DSP 18mm Bel · 2800×2070',
      thickness_mm: 18,
      color: 'Bel',
      decor_code: null,
      sheet_length_mm: 2800,
      sheet_width_mm: 2070,
      grain_direction: false,
      image_file_id: null,
      status: 'active',
      created_at: '',
      updated_at: '',
    },
  ]
  const draft: Draft = {
    id: 'd1',
    client_id: 'c1',
    parts_snapshot: [
      {
        part_ref: 'p1',
        material_id: 'm1',
        material_source: 'shop',
        length_mm: 600,
        width_mm: 400,
        quantity: 4,
        edge_top_mm: null,
        edge_bottom_mm: null,
        edge_left_mm: null,
        edge_right_mm: null,
      },
    ],
    chosen_result_id: null,
    created_at: '',
    updated_at: '',
  }

  it('sums quantities and resolves the dominant material short label', () => {
    const s = summariseDraft(draft, materials, null)
    expect(s.totalParts).toBe(4)
    expect(s.dominantLabel).toBe('DSP 18mm Bel')
    expect(s.sheets).toBeNull()
  })

  it('reads sheets + waste from a chosen result', () => {
    const result: CuttingResult = {
      id: 'r1',
      draft_id: 'd1',
      algorithm_name: 'ffd',
      algorithm_version: '1.0',
      status: 'candidate',
      kerf_mm: 4,
      edge_trim_mm: 10,
      sheets_used_by_material: { m1: 2 },
      waste_percentage: 0.0984, // backend returns a 0..1 fraction
      total_cut_length_mm: 0,
      total_edge_length_mm: 0,
      edge_length_by_thickness: {},
      order_id: null,
      created_at: '',
      confirmed_at: null,
      invalidated_at: null,
      sheets: [],
    }
    const s = summariseDraft(draft, materials, result)
    expect(s.sheets).toBe(2)
    expect(s.wastePct).toBe(9.8)
    expect(totalSheets(result)).toBe(2)
  })
})

describe('relativeTime', () => {
  it('formats minutes / hours / days', () => {
    const now = new Date('2026-05-20T12:00:00Z').getTime()
    expect(relativeTime(new Date('2026-05-20T11:59:30Z').toISOString(), now)).toBe('hozir')
    expect(relativeTime(new Date('2026-05-20T11:30:00Z').toISOString(), now)).toBe(
      '30 daqiqa oldin',
    )
    expect(relativeTime(new Date('2026-05-20T09:00:00Z').toISOString(), now)).toBe('3 soat oldin')
    expect(relativeTime(new Date('2026-05-18T12:00:00Z').toISOString(), now)).toBe('2 kun oldin')
    expect(relativeTime(null, now)).toBe('')
  })
})
