import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CuttingPartsByMaterial from '@/shared/components/CuttingPartsByMaterial.vue'
import type { CuttingPart, CuttingResult } from '@/shared/stores/cutting'

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'p1',
    name: null,
    material_id: 'panel-a',
    material_source: 'shop',
    follow_grain: true,
    thickened: false,
    length_mm: 700,
    width_mm: 396,
    quantity: 1,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
    ...overrides,
  }
}

function result(parts: CuttingPart[]): CuttingResult {
  return {
    id: 'r1',
    draft_id: null,
    parts_snapshot: parts,
    material_snapshots: {
      'panel-a': { name: 'LDSP A', kind: 'panel' },
      'panel-b': { name: 'LDSP B', kind: 'panel' },
      'edge-1': {
        name: 'Kromka Egger H1137 · Kulrang eman · 2×19 mm',
        kind: 'edge',
        manufacturer_name: 'Egger',
        decor_code: 'H1137',
        color: 'Kulrang eman',
        thickness_mm: '2',
        edge_width_mm: 19,
      },
      'edge-legacy': { kind: 'edge', manufacturer_name: 'Egger', decor_code: 'H1137' },
      // Post-reshape vocabulary: no `name`, no `kind`, and the renamed keys.
      // The fixtures above are frozen history and stay as the legacy lock.
      'panel-new': {
        tur: 'ldsp',
        manufacturer_name: 'Egger',
        kod: 'A1',
        nomi: 'Oq',
        qalinlik_mm: '18',
        uzunlik_mm: 2800,
        eni_mm: 2070,
      },
      'edge-new': {
        tur: 'kromka',
        manufacturer_name: 'Egger',
        kod: 'H1137',
        nomi: 'Kulrang eman',
        qalinlik_mm: '2',
        kromka_eni_mm: 19,
      },
    },
    panels: [],
    panels_used_by_material: {},
    own_panel_counts: {},
    edge_consumed_shop_by_material: {},
    edge_consumed_own_by_material: {},
    edge_length_by_material: {},
    waste_percentage: '0',
    total_cut_length_mm: 0,
    total_edge_length_mm: 0,
    kerf_mm: 4,
    edge_trim_mm: 10,
  } as unknown as CuttingResult
}

function mountList(parts: CuttingPart[]) {
  return mount(CuttingPartsByMaterial, {
    props: { result: result(parts) },
    global: { stubs: { Icon: true } },
  })
}

describe('CuttingPartsByMaterial', () => {
  it('groups rows by panel material', () => {
    const wrapper = mountList([
      part({ part_ref: 'p1', material_id: 'panel-a' }),
      part({ part_ref: 'p2', material_id: 'panel-b' }),
      part({ part_ref: 'p3', material_id: 'panel-a' }),
    ])

    const groups = wrapper.findAll('section')
    expect(groups).toHaveLength(2)
    expect(groups[0].text()).toContain('LDSP A')
    expect(groups[1].text()).toContain('LDSP B')
  })

  // The glyph is colour-only; the label is what a screen reader and a hover get.
  it('names the banded sides on every row', () => {
    const wrapper = mountList([
      part({
        part_ref: 'p1',
        edge_top: { material_id: 'edge-1', source: 'shop' },
        edge_left: { material_id: 'edge-1', source: 'shop' },
      }),
      part({ part_ref: 'p2' }),
    ])

    const labels = wrapper.findAll('[aria-label]').map((node) => node.attributes('aria-label'))
    expect(labels).toContain('Kromka: Yuqori · Chap')
    expect(labels).toContain('Kromkasiz')
  })

  // Each group shows only the tapes its own rows use — a tape used solely by
  // another material must not appear under this one.
  it('scopes the tape registry to the group that uses it', () => {
    const wrapper = mountList([
      part({
        part_ref: 'p1',
        material_id: 'panel-a',
        edge_top: { material_id: 'edge-1', source: 'shop' },
      }),
      part({ part_ref: 'p2', material_id: 'panel-b' }),
    ])

    const groups = wrapper.findAll('section')
    expect(groups[0].text()).toContain('Kromka Egger H1137')
    expect(groups[1].text()).not.toContain('Kromka Egger H1137')
  })

  // Accent marks the constraint: a part that may NOT rotate is what the cutter
  // has to honour, so it carries the colour and a free part stays grey.
  it('accents the locked rotation glyph and greys the free one', () => {
    const wrapper = mountList([
      part({ part_ref: 'p1', follow_grain: true }),
      part({ part_ref: 'p2', follow_grain: false }),
    ])

    const glyphs = wrapper.findAll('span.grid > icon-stub')
    expect(glyphs[0].attributes('name')).toBe('grain')
    expect(glyphs[0].classes()).toContain('text-accent')
    expect(glyphs[1].attributes('name')).toBe('rotate')
    expect(glyphs[1].classes()).toContain('text-ink-muted')
  })

  // `name` was the catalog's stored label column. It survives only inside
  // pre-reshape snapshots, which are frozen history — printing it verbatim is
  // what keeps an old order rendering the string it always did.
  it('names a tape by its generated catalog name', () => {
    const wrapper = mountList([part({ edge_top: { material_id: 'edge-1', source: 'shop' } })])

    expect(wrapper.text()).toContain('Kromka Egger H1137 · Kulrang eman · 2×19 mm')
  })

  it('falls back to the assembled label when a snapshot carries no name', () => {
    const wrapper = mountList([part({ edge_top: { material_id: 'edge-legacy', source: 'shop' } })])

    expect(wrapper.text()).toContain('Egger H1137')
  })

  // The same tape written after the reshape has no `name` at all: its label is
  // composed from the renamed keys, byte-identical to the backend's edge_label().
  it('composes panel and tape labels from a post-reshape snapshot', () => {
    const wrapper = mountList([
      part({
        material_id: 'panel-new',
        edge_top: { material_id: 'edge-new', source: 'shop' },
      }),
    ])

    expect(wrapper.text()).toContain('LDSP Egger A1 · Oq · 2800×2070×18 mm')
    expect(wrapper.text()).toContain('Egger H1137 · Kulrang eman · 2×19 mm')
  })

  it('renders nothing but the empty note when the result has no parts', () => {
    const wrapper = mountList([])

    expect(wrapper.findAll('section')).toHaveLength(0)
    expect(wrapper.text()).toContain("Detal yo'q")
  })

  // Read-only by contract: this is a placed order's list, so no control in it
  // may offer an edit (the editor's own registry badges are buttons).
  it('exposes no interactive controls', () => {
    const wrapper = mountList([part({ edge_top: { material_id: 'edge-1', source: 'shop' } })])

    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.findAll('input')).toHaveLength(0)
  })
})
