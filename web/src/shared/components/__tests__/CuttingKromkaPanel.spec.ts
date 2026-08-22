import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import CuttingKromkaPanel from '@/shared/components/CuttingKromkaPanel.vue'
import type { ClientCatalogMaterialOption, CuttingPart } from '@/shared/stores/cutting'

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'part-1',
    name: 'Yon panel',
    material_id: 'panel-1',
    material_source: 'shop',
    follow_grain: true,
    thickened: false,
    length_mm: 800,
    width_mm: 600,
    quantity: 2,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
    ...overrides,
  }
}

function material(
  overrides: Partial<ClientCatalogMaterialOption> = {},
): ClientCatalogMaterialOption {
  return {
    id: 'tape-1',
    type: 'kromka',
    manufacturer_id: 'maker-1',
    manufacturer_name: 'Maker',
    code: 'K1',
    name: 'Kromka Oq',
    has_grain: false,
    image_file_id: null,
    thickness_mm: '2',
    length_mm: null,
    width_mm: null,
    tape_width_mm: 19,
    price_tiyin: 100000,
    price_unset: false,
    display_unit: 'm',
    ...overrides,
  }
}

const PANEL = material({ id: 'panel-1', type: 'ldsp', name: 'Oq daraxt', thickness_mm: '18' })
const TAPE_A = material({ id: 'tape-a', name: 'Kromka A' })
const TAPE_B = material({ id: 'tape-b', name: 'Kromka B' })

function mountPanel(props: Partial<InstanceType<typeof CuttingKromkaPanel>['$props']> = {}) {
  return mount(CuttingKromkaPanel, {
    props: {
      part: part(),
      partNumber: 1,
      panelMaterial: PANEL,
      edgeOptions: [TAPE_A, TAPE_B],
      edgeRegistry: [],
      flashSide: null,
      ...props,
    },
  })
}

/** The side buttons carry their label as text; the two pattern controls are
 *  glyphs, so they are found by their accessible name. */
function sideButton(wrapper: ReturnType<typeof mountPanel>, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)!
}
function patternButton(wrapper: ReturnType<typeof mountPanel>, name: string) {
  return wrapper.findAll('button').find((button) => button.attributes('aria-label') === name)!
}

type Payload = {
  edges: Record<string, unknown>
  rememberedMaterialId: string | null
}

describe('CuttingKromkaPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  // Number, name and size: the panel has no diagram, so without the size nothing
  // on this surface says which detal's edges are being set.
  it('names the detal by number, name and size', () => {
    expect(mountPanel().text()).toContain('D1 · Yon panel · 800×600')
    expect(mountPanel({ part: part({ name: null }) }).text()).toContain('D1 · 800×600')
  })

  // The write is a full four-side replace, not a delta: `applyEdgesToRefs` on the
  // editor side assumes the complete record.
  it('emits the whole four-side record when one side is toggled', async () => {
    const wrapper = mountPanel()
    await sideButton(wrapper, 'Yuqori').trigger('click')
    const payload = wrapper.emitted('edges-change')?.[0]?.[0] as Payload
    expect(Object.keys(payload.edges).sort()).toEqual([
      'edge_bottom',
      'edge_left',
      'edge_right',
      'edge_top',
    ])
    expect(payload.edges.edge_top).toEqual({ material_id: 'tape-a', source: 'shop' })
    expect(payload.edges.edge_bottom).toBeNull()
    expect(payload.rememberedMaterialId).toBe('tape-a')
  })

  it('bands all four sides, then clears them, from the two pattern glyphs', async () => {
    const wrapper = mountPanel()
    await patternButton(wrapper, '4 tomon').trigger('click')
    const all = wrapper.emitted('edges-change')?.[0]?.[0] as Payload
    expect(Object.values(all.edges).every((band) => band !== null)).toBe(true)

    await patternButton(wrapper, 'Kromkasiz').trigger('click')
    const none = wrapper.emitted('edges-change')?.[1]?.[0] as Payload
    expect(Object.values(none.edges).every((band) => band === null)).toBe(true)
  })

  it('marks the pattern glyph that matches the current side set', () => {
    const bare = mountPanel()
    expect(patternButton(bare, 'Kromkasiz').attributes('aria-pressed')).toBe('true')
    expect(patternButton(bare, '4 tomon').attributes('aria-pressed')).toBe('false')

    const banded = mountPanel({
      part: part({
        edge_top: { material_id: 'tape-a', source: 'shop' },
        edge_bottom: { material_id: 'tape-a', source: 'shop' },
        edge_left: { material_id: 'tape-a', source: 'shop' },
        edge_right: { material_id: 'tape-a', source: 'shop' },
      }),
    })
    expect(patternButton(banded, '4 tomon').attributes('aria-pressed')).toBe('true')
  })

  // The bug this panel exists to avoid: the modal's watcher only fires on
  // open/close, so walking D1 → D2 would carry D1's armed tape onto D2.
  it('re-arms from the new detal when the subject changes', async () => {
    const wrapper = mountPanel({
      part: part({ part_ref: 'a', edge_top: { material_id: 'tape-b', source: 'shop' } }),
    })
    await wrapper.setProps({ part: part({ part_ref: 'b' }) })
    await sideButton(wrapper, 'Yuqori').trigger('click')
    const payload = wrapper.emitted('edges-change')?.at(-1)?.[0] as Payload
    expect(payload.rememberedMaterialId).toBe('tape-a')
  })

  it('keeps an existing band untouched when a different side is toggled', async () => {
    const wrapper = mountPanel({
      part: part({ edge_left: { material_id: 'tape-b', source: 'shop' } }),
    })
    await sideButton(wrapper, 'Yuqori').trigger('click')
    const payload = wrapper.emitted('edges-change')?.[0]?.[0] as Payload
    expect(payload.edges.edge_left).toEqual({ material_id: 'tape-b', source: 'shop' })
  })
})
