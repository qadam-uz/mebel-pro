import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import type {
  CuttingEdgeBand,
  CuttingPanel,
  CuttingPart,
  CuttingPlacement,
  CuttingResult,
} from '@/shared/stores/cutting'

const panel: CuttingPanel = {
  id: 'panel-1',
  branch_material_id: 'mat-1',
  panel_index: 1,
  waste_area_mm2: 0,
  offcuts: [],
  placements: [
    {
      id: 'placement-1',
      part_ref: 'A',
      part_quantity_index: 1,
      x_mm: 0,
      y_mm: 0,
      length_mm: 300,
      width_mm: 200,
      rotated: false,
    },
  ],
}

const result = {
  id: 'result-1',
  panels: [panel],
  material_snapshots: {
    'mat-1': {
      name: 'Panel',
      panel_length_mm: 1000,
      panel_width_mm: 700,
    },
  },
  panels_used_by_material: { 'mat-1': 1 },
  own_panel_counts: {},
  total_cut_length_mm: 0,
  total_edge_length_mm: 0,
  waste_percentage: '0',
} as unknown as CuttingResult

describe('CuttingPanelSvg', () => {
  it('keeps placements out of the keyboard tab order while preserving mouse selection', async () => {
    const wrapper = mount(CuttingPanelSvg, {
      props: {
        result,
        panel,
        activePlacementId: null,
      },
    })

    expect(wrapper.find('[role="button"]').exists()).toBe(false)
    expect(wrapper.get('svg').attributes('aria-label')).toBe('List 1 joylashuvi')
    const placement = wrapper.get('.placement')
    expect(placement.attributes('tabindex')).toBeUndefined()
    expect(placement.attributes('aria-hidden')).toBe('true')

    await placement.trigger('click')
    expect(wrapper.emitted('select-placement')?.[0]).toEqual([panel.placements[0]])
  })

  it('makes active placement feedback visible with thicker stroke and bold label', () => {
    const wrapper = mount(CuttingPanelSvg, {
      props: {
        result: {
          ...result,
          parts_snapshot: [makePart({ name: 'Shelf' })],
        } as unknown as CuttingResult,
        panel,
        activePlacementId: 'placement-1',
      },
    })

    expect(wrapper.get('.placement rect').attributes('stroke-width')).toBe('3')
    expect(wrapper.get('.placement text').attributes('font-weight')).toBe('700')
  })
})

const BAND: CuttingEdgeBand = { material_id: 'edge-1', source: 'shop' }

function makePart(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'A',
    name: null,
    material_id: 'mat-1',
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

function mountWithBanding(part: CuttingPart, placement: Partial<CuttingPlacement> = {}) {
  const fullPlacement: CuttingPlacement = {
    id: 'placement-1',
    part_ref: 'A',
    part_quantity_index: 1,
    x_mm: 0,
    y_mm: 0,
    length_mm: 300,
    width_mm: 200,
    rotated: false,
    ...placement,
  }
  const bandedPanel: CuttingPanel = { ...panel, placements: [fullPlacement] }
  const bandedResult = {
    ...result,
    panels: [bandedPanel],
    parts_snapshot: [part],
  } as unknown as CuttingResult
  return mount(CuttingPanelSvg, {
    props: { result: bandedResult, panel: bandedPanel, activePlacementId: null },
  })
}

function lineOrientations(wrapper: ReturnType<typeof mountWithBanding>) {
  return wrapper.findAll('.placement line[data-band="tape"]').map((line) => ({
    horizontal: line.attributes('y1') === line.attributes('y2'),
    x: Number(line.attributes('x1')),
    y: Number(line.attributes('y1')),
  }))
}

describe('CuttingPanelSvg edge banding', () => {
  it('draws no band lines for a part with no banding', () => {
    const wrapper = mountWithBanding(makePart())
    expect(wrapper.findAll('.placement line[data-band="tape"]')).toHaveLength(0)
  })

  it('draws one horizontal band line per banded long side (top/bottom), none on sides', () => {
    const wrapper = mountWithBanding(makePart({ edge_top: BAND, edge_bottom: BAND }))
    const lines = lineOrientations(wrapper)
    expect(lines).toHaveLength(2)
    expect(lines.every((line) => line.horizontal)).toBe(true)
    // the tape's own registry colour — EDGE_REGISTRY_COLOR_STYLES[0].bg
    expect(wrapper.find('.placement line[data-band="tape"]').attributes('stroke')).toBe('#49740e')
  })

  it('draws one vertical band line per banded short side (left/right)', () => {
    const wrapper = mountWithBanding(makePart({ edge_left: BAND }))
    const lines = lineOrientations(wrapper)
    expect(lines).toHaveLength(1)
    expect(lines[0].horizontal).toBe(false)
  })

  it('maps a rotated part 90° clockwise: edge_top lands on the right (vertical) side', () => {
    // length/width are stored already-swapped for a rotated placement; the band of
    // the part's top edge must render as a vertical line near the right edge.
    const wrapper = mountWithBanding(makePart({ edge_top: BAND }), { rotated: true })
    const lines = lineOrientations(wrapper)
    expect(lines).toHaveLength(1)
    expect(lines[0].horizontal).toBe(false)
    // right side → x sits past the placement midline (length 300 → x ≈ 296)
    expect(lines[0].x).toBeGreaterThan(150)
  })

  it('tolerates a result without parts_snapshot (no crash, no bands)', () => {
    const wrapper = mount(CuttingPanelSvg, {
      props: { result, panel, activePlacementId: null },
    })
    expect(wrapper.findAll('.placement line[data-band="tape"]')).toHaveLength(0)
  })

  it('labels placements with part names and renders usable offcuts', () => {
    const wrapper = mount(CuttingPanelSvg, {
      props: {
        result: {
          ...result,
          parts_snapshot: [makePart({ name: 'Shelf' })],
        } as unknown as CuttingResult,
        panel: {
          ...panel,
          offcuts: [{ x_mm: 320, y_mm: 0, length_mm: 400, width_mm: 120, usable: true }],
        },
        activePlacementId: null,
      },
    })

    expect(wrapper.text()).toContain('Shelf')
    // Dims moved out of the centre label to the edges (Bazis-style): the placed
    // length renders horizontally near the top edge, the placed width rotated
    // -90° near the left edge.
    expect(wrapper.text()).not.toContain('300×200')
    const texts = wrapper.findAll('.placement text').map((node) => node.text())
    expect(texts).toEqual(expect.arrayContaining(['300', '200', 'Shelf']))
    const widthDim = wrapper.findAll('.placement text').find((node) => node.text() === '200')
    expect(widthDim?.attributes('transform')).toContain('rotate(-90')
    const lengthDim = wrapper.findAll('.placement text').find((node) => node.text() === '300')
    expect(lengthDim?.attributes('transform')).toBeUndefined()
    expect(wrapper.text()).toContain('Qoldiq 400×120')
    expect(wrapper.text()).not.toContain('sizda qoladi')
    expect(wrapper.find('.offcut rect').attributes('stroke-dasharray')).toBe('12 8')
  })

  // Pre-reshape snapshots are frozen history: they carry `panel_length_mm` /
  // `panel_width_mm` and no `tur`. The fixtures above are that legacy vocabulary;
  // this one is its post-reshape twin, and both must drive the same geometry.
  it('reads panel size from a post-reshape snapshot', () => {
    const wrapper = mount(CuttingPanelSvg, {
      props: {
        result: {
          ...result,
          material_snapshots: {
            'mat-1': { tur: 'ldsp', nomi: 'Panel', uzunlik_mm: 1000, eni_mm: 700 },
          },
        } as unknown as CuttingResult,
        panel,
        activePlacementId: null,
      },
    })

    expect(wrapper.get('svg').attributes('viewBox')).toBe('0 0 1000 700')
  })

  it('rotates labels for tall narrow offcuts', () => {
    const wrapper = mount(CuttingPanelSvg, {
      props: {
        result: {
          ...result,
          material_snapshots: {
            'mat-1': {
              name: 'Panel',
              panel_length_mm: 2963,
              panel_width_mm: 1830,
            },
          },
        } as unknown as CuttingResult,
        panel: {
          ...panel,
          offcuts: [{ x_mm: 320, y_mm: 0, length_mm: 322, width_mm: 1820, usable: true }],
        },
        activePlacementId: null,
      },
    })

    expect(wrapper.get('.offcut text').attributes('transform')).toContain('rotate(-90')
  })
})

describe('CuttingPanelSvg grain marking', () => {
  // The fixture sheet is 1000×700, so normScale = 800/1000 = 0.8 → the tile is
  // 8/0.8 = 10 sheet-mm and the hairline is 1/0.8 = 1.25 mm wide. Both numbers
  // are asserted rather than recomputed: they are the whole point of expressing
  // the marking against the normalized 800-unit width.
  it('draws one hairline pattern for a grain-locked part', () => {
    const wrapper = mountWithBanding(makePart({ follow_grain: true }))

    const patterns = wrapper.findAll('pattern')
    expect(patterns).toHaveLength(1)
    expect(patterns[0].attributes('width')).toBe('10')
    expect(patterns[0].attributes('height')).toBe('10')

    const hairline = patterns[0].get('line')
    expect(hairline.attributes('stroke')).toBe('var(--color-ink)')
    expect(hairline.attributes('stroke-opacity')).toBe('0.17')
    expect(hairline.attributes('stroke-width')).toBe('1.25')
    // Centred in the tile, not on its edge: pattern content is clipped to the
    // tile, so a stroke sitting on 0 would render at half its width.
    expect(hairline.attributes('y1')).toBe('5')
    expect(hairline.attributes('y2')).toBe('5')
  })

  // Print parity: the SVG tiles from the sheet's TOP edge (svgY flips y) while
  // the PDF phases from its bottom. The tile offset is what makes both put a
  // hairline on the same sheet millimetres. 700mm sheet, 10mm tile → (700 - 5)
  // mod 10 = 5, so the absolute lines land on every 10th mm from the bottom.
  // The backend twin is test_grain_hatch_lines_nominal_geometry.
  it('phases the pattern so the PDF draws the same hairlines', () => {
    const wrapper = mountWithBanding(makePart({ follow_grain: true }))

    expect(wrapper.get('pattern').attributes('y')).toBe('5')
  })

  it('fills a grain-locked placement with the pattern over its state fill', () => {
    const wrapper = mountWithBanding(makePart({ follow_grain: true }))

    const rects = wrapper.findAll('.placement rect')
    expect(rects).toHaveLength(2)
    // The base rect keeps the accent fill — it is what marks the selection.
    expect(rects[0].attributes('fill')).toBe('var(--color-accent-soft)')
    expect(rects[1].attributes('fill')).toMatch(/^url\(#mp-grain-\d+\)$/)
  })

  it('leaves a part the optimizer may turn flat', () => {
    const wrapper = mountWithBanding(makePart({ follow_grain: false }))

    expect(wrapper.findAll('.placement rect')).toHaveLength(1)
  })

  // A placement whose part is missing from the snapshot: we do not know its
  // grain, so claiming it is locked would be a lie on the one mark a cutter
  // acts on. It draws flat and nothing throws.
  it('draws an orphan placement flat', () => {
    const orphanResult = {
      ...result,
      parts_snapshot: [makePart({ part_ref: 'other' })],
    } as unknown as CuttingResult
    const wrapper = mount(CuttingPanelSvg, {
      props: { result: orphanResult, panel, activePlacementId: null },
    })

    expect(wrapper.findAll('.placement rect')).toHaveLength(1)
  })

  // The texture runs along the sheet's long side; the viewBox maps that side to
  // x. On a portrait sheet the same rule turns the hairlines vertical — the one
  // case a hardcoded "horizontal" would silently draw across the board.
  it('runs the hairline along the sheet’s long side on a portrait sheet', () => {
    const portraitResult = {
      ...result,
      material_snapshots: {
        'mat-1': { name: 'Panel', panel_length_mm: 900, panel_width_mm: 2000 },
      },
      parts_snapshot: [makePart({ follow_grain: true })],
    } as unknown as CuttingResult
    const wrapper = mount(CuttingPanelSvg, {
      props: { result: portraitResult, panel, activePlacementId: null },
    })

    const hairline = wrapper.get('pattern line')
    expect(hairline.attributes('x1')).toBe(hairline.attributes('x2'))
    expect(hairline.attributes('y1')).not.toBe(hairline.attributes('y2'))
  })

  // The pattern's own line lives in <defs>, outside `.placement` — which is
  // what keeps every band-tick count in the suite above counting tape only.
  it('keeps the hairline out of the band-tick selector', () => {
    const wrapper = mountWithBanding(makePart({ follow_grain: true }))

    expect(wrapper.findAll('.placement line[data-band="tape"]')).toHaveLength(0)
  })
})
