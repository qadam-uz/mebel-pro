import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import CuttingKromkaPanel from '@/shared/components/CuttingKromkaPanel.vue'
import { groupTapeDecors } from '@/shared/app/cuttingGroupTape'
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
    name: 'Oq daraxt',
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

// One tape decor in two thicknesses — the group tape the card is handed.
const DECOR = groupTapeDecors([
  material({ id: 'tape-04', thickness_mm: '0.4' }),
  material({ id: 'tape-2', thickness_mm: '2' }),
])[0]

function mountPanel(props: Partial<InstanceType<typeof CuttingKromkaPanel>['$props']> = {}) {
  return mount(CuttingKromkaPanel, {
    props: {
      part: part(),
      partNumber: 1,
      groupTapeDecor: DECOR,
      selectedThicknessMm: 2,
      ...props,
    },
  })
}

function buttonStartingWith(wrapper: ReturnType<typeof mountPanel>, prefix: string) {
  return wrapper.findAll('button').find((button) => button.text().startsWith(prefix))!
}

describe('CuttingKromkaPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  // Number, name and size: the card has no drawing of the part, so without the
  // size nothing on this surface says which detal's edges are being set.
  it('names the detal by number, name and size', () => {
    expect(mountPanel().text()).toContain('D1 · Yon panel · 800×600')
    expect(mountPanel({ part: part({ name: null }) }).text()).toContain('D1 · 800×600')
  })

  // §7.1 / §13 W2: the card opens by naming the group's tape and pointing at
  // where it changes — there is no per-part tape list left to search.
  it('names the group tape and opens the picker from that line', async () => {
    const wrapper = mountPanel()
    const line = buttonStartingWith(wrapper, 'Kromka:')
    expect(line.text()).toContain('Oq daraxt')
    expect(line.text()).toContain('0.4 / 2 mm')
    await line.trigger('click')
    expect(wrapper.emitted('open-group-tape')).toHaveLength(1)
  })

  it('bands one side with the armed thickness, and clears it on a second tap', async () => {
    const wrapper = mountPanel()
    await buttonStartingWith(wrapper, 'Yuqori').trigger('click')
    expect(wrapper.emitted('set-side')?.[0]).toEqual(['edge_top', 'tape-2'])

    const banded = mountPanel({
      part: part({ edge_top: { material_id: 'tape-2', source: 'shop' } }),
    })
    await buttonStartingWith(banded, 'Yuqori').trigger('click')
    expect(banded.emitted('set-side')?.[0]).toEqual(['edge_top', null])
  })

  it('asks for a tape instead of banding when the group has none', async () => {
    const wrapper = mountPanel({ groupTapeDecor: null, selectedThicknessMm: null })
    await buttonStartingWith(wrapper, 'Yuqori').trigger('click')
    expect(wrapper.emitted('need-tape')).toHaveLength(1)
    expect(wrapper.emitted('set-side')).toBeUndefined()
  })

  it('arms a thickness from the chips', async () => {
    const wrapper = mountPanel()
    await buttonStartingWith(wrapper, '0.4 mm').trigger('click')
    expect(wrapper.emitted('update:selectedThicknessMm')?.[0]).toEqual([0.4])
  })

  // The one workshop-only control on the card: the client never orders
  // thickening, and the client editor does not render it.
  it('carries thickening for the workshop only', async () => {
    expect(mountPanel().text()).not.toContain('Uta')

    const wrapper = mountPanel({ showThickening: true })
    const toggle = wrapper.get('[role="switch"]')
    expect(toggle.attributes('aria-checked')).toBe('false')
    await toggle.trigger('click')
    expect(wrapper.emitted('update:thickened')?.[0]).toEqual([true])
  })
})
