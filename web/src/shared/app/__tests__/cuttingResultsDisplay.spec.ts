import { afterEach, describe, expect, it } from 'vitest'

import {
  clientResultFigures,
  deriveSnapshotEdgeRegistry,
  drawnSheetSize,
  groupPanelPlacements,
  offcutLabelMode,
  panelDisplayIndex,
  panelEdgeConsumedByMaterial,
  panelFillPercent,
  panelSheetSize,
  resultFillPercent,
  resultSheetPartGroups,
  resultTotals,
  sheetEdgeLine,
  snapshotShortLabel,
  squareMetres,
  workshopResultFigures,
} from '@/shared/app/cuttingResultsDisplay'
import { DEFAULT_LOCALE, setLocale } from '@/shared/i18n'
import type {
  CuttingPanel,
  CuttingPart,
  CuttingPlacement,
  CuttingResult,
} from '@/shared/stores/cutting'

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'part-a',
    name: null,
    material_id: 'panel-a',
    material_source: 'shop',
    follow_grain: true,
    thickened: false,
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

function placed(
  id: string,
  box: Pick<CuttingPlacement, 'x_mm' | 'y_mm' | 'length_mm' | 'width_mm'>,
) {
  return {
    id,
    part_ref: 'part-a',
    part_quantity_index: 1,
    rotated: false,
    ...box,
  } satisfies CuttingPlacement
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
    own_panel_counts: {},
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

  // panelFillPercent returns '-' when a size is missing, so a legacy snapshot read
  // through the new keys alone would silently show '-' on every historical result
  // — no error, no failing test. All three vocabularies are pinned.
  it('computes the fill percentage from any snapshot vocabulary', () => {
    const panel = (id: string): CuttingPanel => ({
      id,
      material_id: id,
      panel_index: 1,
      waste_area_mm2: 1_000_000,
      offcuts: [],
      placements: [],
    })
    const cuttingResult = result({
      panels: [panel('legacy'), panel('modern'), panel('uzbek'), panel('unknown')],
      material_snapshots: {
        legacy: { panel_length_mm: 2000, panel_width_mm: 1000 },
        modern: { length_mm: 2000, width_mm: 1000 },
        uzbek: { uzunlik_mm: 2000, eni_mm: 1000 },
      },
    })

    expect(panelFillPercent(cuttingResult, cuttingResult.panels[0])).toBe('50.0%')
    expect(panelFillPercent(cuttingResult, cuttingResult.panels[1])).toBe('50.0%')
    expect(panelFillPercent(cuttingResult, cuttingResult.panels[2])).toBe('50.0%')
    // Nothing to size the sheet by: no snapshot dimensions and an empty layout.
    expect(panelFillPercent(cuttingResult, cuttingResult.panels[3])).toBe('-')
  })

  // Twin of backend `rendering.sheet_size` — the screen map and the PDF must
  // scale a sheet identically. Regression: a snapshot with no size in any
  // vocabulary used to fall back to a flat 1000×700, drawing a 2800×2070 layout
  // at 2.8× with everything spilling outside its own frame.
  it('derives a missing sheet size from the layout, never from a constant', () => {
    const sheetPanel: CuttingPanel = {
      id: 'p',
      material_id: 'mat',
      panel_index: 1,
      waste_area_mm2: 0,
      placements: [
        placed('p1', { x_mm: 0, y_mm: 0, length_mm: 1200, width_mm: 900 }),
        placed('p2', { x_mm: 1200, y_mm: 0, length_mm: 800, width_mm: 600 }),
      ],
      // Offcuts fill everything the parts leave, so the extent is the sheet.
      offcuts: [
        { x_mm: 2000, y_mm: 0, length_mm: 800, width_mm: 2070, usable: true },
        { x_mm: 0, y_mm: 900, length_mm: 2000, width_mm: 1170, usable: false },
      ],
    }
    const sized = result({ panels: [sheetPanel], material_snapshots: { mat: { nomi: 'Panel' } } })

    expect(panelSheetSize(sized, sheetPanel)).toEqual({ length: 2800, width: 2070 })
    expect(drawnSheetSize(sized, sheetPanel)).toEqual({ length: 2800, width: 2070 })
  })

  it('widens the drawn sheet when a snapshot is smaller than its own layout', () => {
    const sheetPanel: CuttingPanel = {
      id: 'p',
      material_id: 'mat',
      panel_index: 1,
      waste_area_mm2: 0,
      placements: [placed('p1', { x_mm: 0, y_mm: 0, length_mm: 1200, width_mm: 900 })],
      offcuts: [],
    }
    const stale = result({
      panels: [sheetPanel],
      material_snapshots: { mat: { length_mm: 600, width_mm: 400 } },
    })

    // The recorded size is what the summary reports…
    expect(panelSheetSize(stale, sheetPanel)).toEqual({ length: 600, width: 400 })
    // …but the drawing covers the placements, so nothing leaves the frame.
    expect(drawnSheetSize(stale, sheetPanel)).toEqual({ length: 1200, width: 900 })
  })

  it('never hands a divisor of zero to a drawing of an empty panel', () => {
    const empty: CuttingPanel = {
      id: 'p',
      material_id: 'mat',
      panel_index: 1,
      waste_area_mm2: 0,
      placements: [],
      offcuts: [],
    }

    expect(drawnSheetSize(result({ panels: [empty] }), empty)).toEqual({ length: 1, width: 1 })
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

  it('attributes every part group to its own sheet across a multi-sheet result', () => {
    const placement = (id: string, partRef: string) => ({
      id,
      part_ref: partRef,
      part_quantity_index: 1,
      x_mm: 0,
      y_mm: 0,
      length_mm: 300,
      width_mm: 200,
      rotated: false,
    })
    const sheetOne: CuttingPanel = {
      id: 'sheet-one',
      material_id: 'panel-a',
      panel_index: 1,
      waste_area_mm2: 0,
      offcuts: [],
      // Placed b-then-a: the list must still read in parts_snapshot order.
      placements: [placement('p1', 'part-b'), placement('p2', 'part-a'), placement('p3', 'part-a')],
    }
    const sheetTwo: CuttingPanel = {
      id: 'sheet-two',
      material_id: 'panel-b',
      panel_index: 1,
      waste_area_mm2: 0,
      offcuts: [],
      placements: [placement('p4', 'part-b')],
    }
    const cuttingResult = result({
      panels: [sheetOne, sheetTwo],
      parts_snapshot: [
        part({ part_ref: 'part-a', name: 'Shelf' }),
        part({ part_ref: 'part-b', name: 'Door', material_id: 'panel-b' }),
      ],
      material_snapshots: {
        // Legacy vocabulary on purpose — this is the frozen-history guard.
        'panel-a': { name: 'Aloqa', panel_length_mm: 2800, panel_width_mm: 2070 },
        // New vocabulary beside it, so the dual read is proven in both directions.
        'panel-b': {
          manufacturer_name: 'Egger',
          type: 'ldsp',
          code: 'Bemor',
          name: 'Oq',
          thickness_mm: '18',
          length_mm: 2800,
          width_mm: 2070,
        },
      },
    })

    expect(
      resultSheetPartGroups(cuttingResult).map((sheet) => [
        sheet.panelId,
        sheet.sheetLabel,
        // materialLabel was previously unasserted, which left the snapshot-key
        // rename with no coverage at all. Both vocabularies are pinned here.
        sheet.materialLabel,
        sheet.groups.map((group) => `${group.name}×${group.count}`),
      ]),
    ).toEqual([
      ['sheet-one', 'List 1', 'Aloqa · 2800×2070 mm', ['Shelf×2', 'Door×1']],
      ['sheet-two', 'List 2', 'LDSP Egger Bemor · Oq · 2800×2070×18 mm', ['Door×1']],
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

describe('resultTotals', () => {
  // The aside's five figures. Every one of them is a fold over the payload, so
  // the risk is not arithmetic — it is folding the wrong field. Each case here
  // pins the field, not the sum.
  const placement = (partRef: string, id: string) => ({
    id,
    part_ref: partRef,
    part_quantity_index: 1,
    x_mm: 0,
    y_mm: 0,
    length_mm: 300,
    width_mm: 200,
    rotated: false,
  })
  const panel = (id: string, overrides: Partial<CuttingPanel> = {}): CuttingPanel => ({
    id,
    material_id: 'panel-a',
    panel_index: 1,
    waste_area_mm2: 0,
    offcuts: [],
    placements: [],
    ...overrides,
  })

  it('counts placed parts across every sheet against the quantities requested', () => {
    const totals = resultTotals(
      result({
        parts_snapshot: [part({ quantity: 3 }), part({ part_ref: 'part-b', quantity: 2 })],
        panels: [
          panel('one', { placements: [placement('part-a', 'p1'), placement('part-a', 'p2')] }),
          panel('two', { placements: [placement('part-b', 'p3')] }),
        ],
      }),
    )

    expect(totals.placedParts).toBe(3)
    expect(totals.requestedParts).toBe(5)
  })

  // Pre-snapshot results are still in the database. Dropping the `?? []` guard
  // throws on the read rather than degrading, and takes the whole aside with it.
  it('reads a result whose parts snapshot is absent as zero requested', () => {
    const legacy = result()
    // @ts-expect-error — the frozen legacy payload genuinely lacks the field
    delete legacy.parts_snapshot

    expect(resultTotals(legacy).requestedParts).toBe(0)
  })

  it('counts sheets per material, not per panel row', () => {
    const totals = resultTotals(
      result({ panels_used_by_material: { 'panel-a': 3, 'panel-b': 2 }, panels: [panel('one')] }),
    )

    expect(totals.sheets).toBe(5)
  })

  // `edge_length_*` is the geometric edge; `edge_consumed_*` adds the per-side
  // glue-and-trim overhang, which is what actually comes off the roll. Summing
  // the wrong pair understates every invoice.
  it('sums the consumed tape dicts and ignores the geometric ones', () => {
    const totals = resultTotals(
      result({
        edge_length_shop_by_material: { 'edge-a': 99_000 },
        edge_length_own_by_material: { 'edge-a': 99_000 },
        edge_consumed_shop_by_material: { 'edge-a': 1_000, 'edge-b': 500 },
        edge_consumed_own_by_material: { 'edge-a': 250 },
      }),
    )

    expect(totals.edgeConsumedMm).toBe(1_750)
  })

  it('reports no tape at all for a drawing with no banding', () => {
    expect(resultTotals(result()).edgeConsumedMm).toBe(0)
  })

  // `usable` is the same flag the drawing colours green and the label calls
  // "Qoldiq … — sizda qoladi". Scrap must not join the figure the client reads
  // as what they take home.
  it('counts and measures only the offcuts the layout marked usable', () => {
    const totals = resultTotals(
      result({
        panels: [
          panel('one', {
            offcuts: [
              { x_mm: 0, y_mm: 0, length_mm: 1000, width_mm: 500, usable: true },
              { x_mm: 0, y_mm: 0, length_mm: 100, width_mm: 40, usable: false },
            ],
          }),
          panel('two', {
            offcuts: [{ x_mm: 0, y_mm: 0, length_mm: 2000, width_mm: 1000, usable: true }],
          }),
        ],
      }),
    )

    expect(totals.usableOffcutCount).toBe(2)
    expect(totals.usableOffcutAreaMm2).toBe(2_500_000)
    expect(squareMetres(totals.usableOffcutAreaMm2)).toBe('2.50')
  })
})

/**
 * «Chiqim», the workshop's fifth figure. Three properties are load-bearing and
 * none of them shows up in a screenshot: the mean is **area-weighted** (an
 * unweighted one over the sheets lets a small offcut-heavy board outvote the big
 * ones the money is in), each sheet is measured through `panelSheetSize` — so a
 * snapshot with no size in any vocabulary is sized off its own layout rather
 * than dropped — and a sheet with nothing at all to measure is left out of the
 * arithmetic entirely rather than counted as zero area.
 */
describe('resultFillPercent', () => {
  const panel = (
    id: string,
    wasteMm2: number,
    layout: Partial<Pick<CuttingPanel, 'placements' | 'offcuts'>> = {},
  ): CuttingPanel => ({
    id,
    material_id: id,
    panel_index: 1,
    waste_area_mm2: wasteMm2,
    offcuts: [],
    placements: [],
    ...layout,
  })

  it('weights the yield by sheet area rather than averaging the sheets', () => {
    const fill = resultFillPercent(
      result({
        // 4 m² fully used beside 1 m² half wasted: weighted 90%, a plain mean of
        // the two sheets would say 75%.
        panels: [panel('big', 0), panel('small', 500_000)],
        material_snapshots: {
          big: { length_mm: 2000, width_mm: 2000 },
          small: { length_mm: 1000, width_mm: 1000 },
        },
      }),
    )

    expect(fill).toBeCloseTo(90, 5)
  })

  // The yield reads its sheets through `panelSheetSize`, so it inherits the
  // extent fallback: a frozen snapshot with no size in any vocabulary is sized
  // off the placements + offcuts that cover the sheet, not skipped. Measure it
  // some other way and «Chiqim» silently disagrees with the sheet badges and the
  // PDF drawn from the same layout.
  it('sizes a sheet with no recorded size from its own layout', () => {
    const cuttingResult = result({
      panels: [
        panel('sizeless', 500_000, {
          placements: [placed('p1', { x_mm: 0, y_mm: 0, length_mm: 1500, width_mm: 1000 })],
          // 2 m² of sheet under the layout, half a square metre of it wasted.
          offcuts: [{ x_mm: 1500, y_mm: 0, length_mm: 500, width_mm: 1000, usable: false }],
        }),
      ],
      material_snapshots: { sizeless: { nomi: 'Panel' } },
    })

    expect(resultFillPercent(cuttingResult)).toBeCloseTo(75, 5)
  })

  it('leaves out a sheet with nothing to measure instead of scoring it zero', () => {
    const cuttingResult = result({
      // Neither a recorded size nor a layout to derive one from: the second sheet
      // contributes no area and no waste rather than dragging the yield to 0.
      panels: [panel('modern', 500_000), panel('unmeasurable', 250_000)],
      material_snapshots: { modern: { length_mm: 2000, width_mm: 1000 } },
    })

    expect(resultFillPercent(cuttingResult)).toBeCloseTo(75, 5)
  })

  // The only `null` left. With the extent fallback in place a real result always
  // measures, so an em dash on this screen means an empty result — nothing laid
  // on any sheet — and never "we lost the sheet size".
  it('has no yield at all when nothing is laid on any sheet', () => {
    expect(resultFillPercent(result({ panels: [panel('unmeasurable', 0)] }))).toBeNull()
    expect(resultFillPercent(result({ panels: [] }))).toBeNull()
  })
})

/**
 * The workshop reads the client's four figures plus «Chiqim» (§13 W3) — one
 * composer behind both apps, so a figure cannot be worded one way at the counter
 * and another way at home. «Arra yo'li» is gone from both: the propil length
 * stayed on this screen long after anyone read it off there.
 */
describe('workshopResultFigures', () => {
  const panel = (): CuttingPanel => ({
    id: 'panel-1',
    material_id: 'panel-a',
    panel_index: 1,
    waste_area_mm2: 400_000,
    offcuts: [],
    placements: [],
  })
  const workshopResult = () =>
    result({
      panels: [panel()],
      material_snapshots: { 'panel-a': { length_mm: 2000, width_mm: 1000 } },
      total_cut_length_mm: 53_800,
    })

  it('adds Chiqim to the client four, in the client order', () => {
    const figures = workshopResultFigures(workshopResult())

    expect(figures.map((figure) => figure.key)).toEqual([
      'parts',
      'sheets',
      'edge',
      'offcuts',
      'yield',
    ])
    expect(figures.map((figure) => figure.label)).toEqual([
      'Detallar',
      'Listlar',
      'Kromka',
      'Foydali qoldiq',
      'Chiqim',
    ])
    expect(figures.at(-1)?.value).toBe('80%')
  })

  it('says exactly what the client says about the four they share', () => {
    const cuttingResult = workshopResult()

    expect(workshopResultFigures(cuttingResult).slice(0, 4)).toEqual(
      clientResultFigures(cuttingResult),
    )
  })

  // An empty sheet is the whole of "cannot be derived" now — a sheet that
  // carries anything is sized off its layout even with no snapshot at all.
  it('prints an em dash rather than 0% for a result with nothing on any sheet', () => {
    const figures = workshopResultFigures(result({ panels: [panel()] }))

    expect(figures.find((figure) => figure.key === 'yield')?.value).toBe('—')
  })

  // Same sheet, same waste, no snapshot: the extent fallback still yields a
  // figure, so the workshop's fifth number survives frozen pre-reshape history.
  it('still states a yield when the sheet size is only in the layout', () => {
    const figures = workshopResultFigures(
      result({
        panels: [
          {
            ...panel(),
            placements: [placed('p1', { x_mm: 0, y_mm: 0, length_mm: 1600, width_mm: 1000 })],
            offcuts: [{ x_mm: 1600, y_mm: 0, length_mm: 400, width_mm: 1000, usable: true }],
          },
        ],
      }),
    )

    expect(figures.find((figure) => figure.key === 'yield')?.value).toBe('80%')
  })
})

// The sheet card's own tape figure. The result-wide dicts cannot answer it, and
// the overhang behind it is recovered from those dicts rather than fetched — so
// both the attribution and the recovery are pinned here.
describe('panelEdgeConsumedByMaterial', () => {
  const placement = (partRef: string, id: string): CuttingPlacement => ({
    id,
    part_ref: partRef,
    part_quantity_index: 0,
    x_mm: 0,
    y_mm: 0,
    length_mm: 300,
    width_mm: 200,
    rotated: false,
  })
  const panel = (overrides: Partial<CuttingPanel> = {}): CuttingPanel => ({
    id: 'panel-1',
    material_id: 'panel-a',
    panel_index: 1,
    waste_area_mm2: 0,
    offcuts: [],
    placements: [],
    ...overrides,
  })
  const band = (materialId: string) => ({ material_id: materialId, source: 'shop' as const })

  // One 300×200 part, banded top and left: 300 + 200 of visible edge, plus the
  // 10 mm overhang each banded side eats — recovered from the dicts, not read
  // from the branch, which may have re-set it since this result was cut.
  function bandedResult(overrides: Partial<CuttingResult> = {}) {
    return result({
      parts_snapshot: [part({ edge_top: band('edge-a'), edge_left: band('edge-a') })],
      edge_length_by_material: { 'edge-a': 500 },
      edge_consumed_shop_by_material: { 'edge-a': 520 },
      edge_banded_sides_by_material: { 'edge-a': { shop: 2, own: 0 } },
      ...overrides,
    })
  }

  it('charges each banded side its own edge plus the overhang', () => {
    const consumed = panelEdgeConsumedByMaterial(
      bandedResult(),
      panel({ placements: [placement('part-a', 'p1')] }),
    )

    expect(consumed.get('edge-a:shop')).toBe(520)
  })

  // Two copies of the same part on one sheet cost twice the tape; the
  // result-wide dict would have said the same thing for one.
  it('counts every placement on the sheet, not the part once', () => {
    const consumed = panelEdgeConsumedByMaterial(
      bandedResult(),
      panel({ placements: [placement('part-a', 'p1'), placement('part-a', 'p2')] }),
    )

    expect(consumed.get('edge-a:shop')).toBe(1_040)
  })

  it('leaves a sheet with no banding empty rather than at zero metres', () => {
    const consumed = panelEdgeConsumedByMaterial(
      result({ parts_snapshot: [part()] }),
      panel({ placements: [placement('part-a', 'p1')] }),
    )

    expect(consumed.size).toBe(0)
  })

  it('keeps two tapes apart on the same sheet', () => {
    const consumed = panelEdgeConsumedByMaterial(
      result({
        parts_snapshot: [part({ edge_top: band('edge-a'), edge_left: band('edge-b') })],
        edge_length_by_material: { 'edge-a': 300, 'edge-b': 200 },
        edge_consumed_shop_by_material: { 'edge-a': 300, 'edge-b': 200 },
        edge_banded_sides_by_material: {
          'edge-a': { shop: 1, own: 0 },
          'edge-b': { shop: 1, own: 0 },
        },
      }),
      panel({ placements: [placement('part-a', 'p1')] }),
    )

    // Top follows the part's length, left its width — no overhang in this result.
    expect(consumed.get('edge-a:shop')).toBe(300)
    expect(consumed.get('edge-b:shop')).toBe(200)
  })

  // A placement whose part is missing from the snapshot (pre-snapshot results)
  // must not throw the caption — it simply carries no tape.
  it('skips a placement with no part in the snapshot', () => {
    const consumed = panelEdgeConsumedByMaterial(
      bandedResult({ parts_snapshot: [] }),
      panel({ placements: [placement('part-a', 'p1')] }),
    )

    expect(consumed.size).toBe(0)
  })
})

// The caption under a sheet card. Its branches are where the prototype and this
// app part ways, so each is pinned: one tape gives metres alone, several give
// each its own figure, and no banding gives nothing at all.
describe('sheetEdgeLine', () => {
  const placement = (partRef: string, id: string): CuttingPlacement => ({
    id,
    part_ref: partRef,
    part_quantity_index: 0,
    x_mm: 0,
    y_mm: 0,
    length_mm: 300,
    width_mm: 200,
    rotated: false,
  })
  const sheet = (): CuttingPanel => ({
    id: 'panel-1',
    material_id: 'panel-a',
    panel_index: 1,
    waste_area_mm2: 0,
    offcuts: [],
    placements: [placement('part-a', 'p1')],
  })
  const band = (materialId: string) => ({ material_id: materialId, source: 'shop' as const })

  // The card is the only place this screen names a tape at all — its summary row
  // says "Kromka lentasi" and a result-wide figure, never which roll.
  it('names the tape by its code even when the result runs on one', () => {
    const parts = [part({ edge_top: band('edge-a') })]
    const line = sheetEdgeLine(
      result({
        parts_snapshot: parts,
        material_snapshots: { 'edge-a': { manufacturer_name: 'Egger', code: 'H1137' } },
      }),
      sheet(),
      deriveSnapshotEdgeRegistry(parts),
    )

    expect(line).toBe('H1137 · 0.30 m')
  })

  // The composed label is three `·`-separated fields; dropped into a caption
  // that already uses `·`, it wraps the card three lines deep.
  it('keeps the composed label out of the caption', () => {
    const parts = [part({ edge_top: band('edge-a') })]
    const line = sheetEdgeLine(
      result({
        parts_snapshot: parts,
        material_snapshots: {
          'edge-a': {
            manufacturer_name: 'Egger',
            code: 'H1137',
            name: 'Kulrang eman',
            thickness_mm: '2',
            tape_width_mm: 19,
          },
        },
      }),
      sheet(),
      deriveSnapshotEdgeRegistry(parts),
    )

    expect(line).toBe('H1137 · 0.30 m')
  })

  // 17.52 m off two different rolls is the one figure the operator cannot act on.
  it('splits the figure per tape, in registry order', () => {
    const parts = [part({ edge_top: band('edge-b'), edge_left: band('edge-a') })]
    const line = sheetEdgeLine(
      result({
        parts_snapshot: parts,
        material_snapshots: {
          'edge-a': { manufacturer_name: 'Egger', code: 'H1137' },
          'edge-b': { manufacturer_name: 'Egger', code: 'H1145' },
        },
      }),
      sheet(),
      deriveSnapshotEdgeRegistry(parts),
    )

    // edge_top is walked first, so H1145 takes registry number 1 and leads.
    expect(line).toBe('H1145 · 0.30 m, H1137 · 0.20 m')
  })

  it('says nothing at all for a sheet with no banding', () => {
    const parts = [part()]

    expect(sheetEdgeLine(result({ parts_snapshot: parts }), sheet(), [])).toBeNull()
  })
})

/**
 * Russian agrees the unit noun with the number in front of it, and the catalog
 * carries the three forms — but only a call that hands vue-i18n the *count*
 * reaches them. This figure used to read `translate('cutting.unit.sheet')` with
 * no count at all, so a Russian client saw «2 лист» on the result stage, the
 * phone summary card and the order confirmation alike. The counts below are the
 * three Russian classes: 1 → one, 2 → few, 5 → many.
 */
describe('clientResultFigures — the sheets figure agrees with its number', () => {
  afterEach(async () => {
    await setLocale(DEFAULT_LOCALE)
  })

  function sheetsFigure(sheets: number): string {
    const figures = clientResultFigures(result({ panels_used_by_material: { 'panel-a': sheets } }))
    return figures.find((figure) => figure.key === 'sheets')!.value
  }

  it.each([
    [1, '1 лист'],
    [2, '2 листа'],
    [5, '5 листов'],
  ])('renders %i sheets as «%s» in Russian', async (sheets, expected) => {
    await setLocale('ru')

    expect(sheetsFigure(sheets)).toBe(expected)
  })

  // Uzbek has one form, so the same call must leave it exactly as it was —
  // passing a count is not allowed to start inflecting a language that doesn't.
  it.each([1, 2, 5])('leaves the single Uzbek form alone at %i sheets', async (sheets) => {
    await setLocale('uz')

    expect(sheetsFigure(sheets)).toBe(`${sheets} list`)
  })

  // uz-Cyrl is transliterated from uz, so it inherits that single form; the
  // count must not split it into anything else.
  it.each([1, 2, 5])('transliterates the same single form at %i sheets', async (sheets) => {
    await setLocale('uz-Cyrl')

    expect(sheetsFigure(sheets)).toBe(`${sheets} лист`)
  })
})
