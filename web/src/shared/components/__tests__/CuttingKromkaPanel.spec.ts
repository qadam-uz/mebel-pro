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
    tur: 'kromka',
    manufacturer_id: 'maker-1',
    manufacturer_name: 'Maker',
    kod: 'K1',
    nomi: 'Kromka Oq',
    tolali: false,
    image_file_id: null,
    qalinlik_mm: '2',
    uzunlik_mm: null,
    eni_mm: null,
    kromka_eni_mm: 19,
    price_tiyin: 100000,
    price_unset: false,
    display_unit: 'm',
    ...overrides,
  }
}

const PANEL = material({ id: 'panel-1', tur: 'ldsp', nomi: 'Oq daraxt', qalinlik_mm: '18' })
const TAPE_A = material({ id: 'tape-a', nomi: 'Kromka A' })
const TAPE_B = material({ id: 'tape-b', nomi: 'Kromka B' })

function mountPanel(props: Partial<InstanceType<typeof CuttingKromkaPanel>['$props']> = {}) {
  return mount(CuttingKromkaPanel, {
    props: {
      part: part(),
      partNumber: 1,
      panelMaterial: PANEL,
      edgeOptions: [TAPE_A, TAPE_B],
      edgeRegistry: [],
      groupSize: 3,
      flashSide: null,
      ...props,
    },
  })
}

describe('CuttingKromkaPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows the empty state and no close control when nothing is selected', () => {
    const wrapper = mountPanel({ part: null })
    expect(wrapper.text()).toContain('Detal tanlanmagan')
    expect(wrapper.text()).toContain('Jadvaldan detalni bosing')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('names the detal by number and name', () => {
    expect(mountPanel().text()).toContain('D1 · Yon panel')
    expect(mountPanel({ part: part({ name: null }) }).text()).toContain('D1')
  })

  // The write is a full four-side replace, not a delta: `applyEdgesToRefs` on the
  // editor side assumes the complete record.
  it('emits the whole four-side record when one side is toggled', async () => {
    const wrapper = mountPanel()
    await wrapper.findAll('button')[1].trigger('click') // Ustki
    const payload = wrapper.emitted('edges-change')?.[0]?.[0] as {
      edges: Record<string, unknown>
      rememberedMaterialId: string | null
    }
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

  it('bands all four sides, then clears them, from the two pattern chips', async () => {
    const wrapper = mountPanel()
    const chips = wrapper
      .findAll('button')
      .filter((b) => ['4 tomon', 'Kromkasiz'].includes(b.text()))
    await chips[0].trigger('click')
    const all = wrapper.emitted('edges-change')?.[0]?.[0] as { edges: Record<string, unknown> }
    expect(Object.values(all.edges).every((band) => band !== null)).toBe(true)

    await chips[1].trigger('click')
    const none = wrapper.emitted('edges-change')?.[1]?.[0] as { edges: Record<string, unknown> }
    expect(Object.values(none.edges).every((band) => band === null)).toBe(true)
  })

  // The bug this panel exists to avoid: the modal's watcher only fires on
  // open/close, so walking D1 → D2 would carry D1's armed tape onto D2.
  it('re-arms from the new detal when the subject changes', async () => {
    const wrapper = mountPanel({
      part: part({ part_ref: 'a', edge_top: { material_id: 'tape-b', source: 'shop' } }),
    })
    await wrapper.setProps({ part: part({ part_ref: 'b' }) })
    await wrapper.findAll('button')[1].trigger('click')
    const payload = wrapper.emitted('edges-change')?.at(-1)?.[0] as {
      rememberedMaterialId: string | null
    }
    expect(payload.rememberedMaterialId).toBe('tape-a')
  })

  it('keeps an existing band untouched when a different side is toggled', async () => {
    const wrapper = mountPanel({
      part: part({ edge_left: { material_id: 'tape-b', source: 'shop' } }),
    })
    await wrapper.findAll('button')[1].trigger('click') // Ustki
    const payload = wrapper.emitted('edges-change')?.[0]?.[0] as {
      edges: Record<string, unknown>
    }
    expect(payload.edges.edge_left).toEqual({ material_id: 'tape-b', source: 'shop' })
  })

  // (800 + 800) + (600 + 600) = 2800 mm per piece, × 2 pieces = 5.60 m.
  it('reports the sarf only once a side is banded', () => {
    expect(mountPanel().text()).toContain('Kromkasiz')
    const banded = mountPanel({
      part: part({
        edge_top: { material_id: 'tape-a', source: 'shop' },
        edge_bottom: { material_id: 'tape-a', source: 'shop' },
        edge_left: { material_id: 'tape-a', source: 'shop' },
        edge_right: { material_id: 'tape-a', source: 'shop' },
      }),
    })
    expect(banded.text()).toContain('Sarf 5.60 m')
  })
})
