import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import CuttingPartRow from '@/shared/components/CuttingPartRow.vue'
import { useCuttingStore, type CuttingPart } from '@/shared/stores/cutting'
import type { EdgeRegistryEntry } from '@/shared/app/cuttingEditorDerived'

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'part-1',
    name: null,
    material_id: 'panel-1',
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

function seedPanel(tolali: boolean) {
  const cutting = useCuttingStore()
  cutting.panelOptions = [
    {
      id: 'panel-1',
      tur: 'ldsp',
      manufacturer_id: 'maker-1',
      manufacturer_name: 'Maker',
      kod: null,
      nomi: 'Oak',
      tolali,
      image_file_id: null,
      qalinlik_mm: '18',
      uzunlik_mm: 600,
      eni_mm: 400,
      kromka_eni_mm: null,
      price_tiyin: 0,
      price_unset: false,
      display_unit: 'sheet',
    },
  ]
}

function mountRow(rowPart: CuttingPart, edgeRegistry: EdgeRegistryEntry[] = []) {
  return mount(CuttingPartRow, {
    props: {
      part: rowPart,
      index: 0,
      hasError: false,
      sizeError: null,
      materialMissing: false,
      optimizeError: null,
      edgeRegistry,
    },
    global: {
      stubs: {
        Icon: true,
        SearchCombobox: {
          template: '<div data-test="panel-combobox" />',
        },
      },
    },
  })
}

describe('CuttingPartRow grain toggle', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // 0 is the stored "not entered" value; a blank row must read as blank, not as
  // three zeros the user has to clear first.
  it('renders the numeric cells empty when the part is still unfilled', () => {
    seedPanel(true)

    const wrapper = mountRow(part({ length_mm: 0, width_mm: 0, quantity: 0 }))

    expect(wrapper.get<HTMLInputElement>('[data-cell="length"]').element.value).toBe('')
    expect(wrapper.get<HTMLInputElement>('[data-cell="width"]').element.value).toBe('')
    expect(wrapper.get<HTMLInputElement>('[data-cell="quantity"]').element.value).toBe('')
  })

  it('shows real dimensions once they are entered', () => {
    seedPanel(true)

    const wrapper = mountRow(part({ length_mm: 300, width_mm: 200, quantity: 2 }))

    expect(wrapper.get<HTMLInputElement>('[data-cell="length"]').element.value).toBe('300')
    expect(wrapper.get<HTMLInputElement>('[data-cell="quantity"]').element.value).toBe('2')
  })

  it('stores 0 again when a numeric cell is cleared', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ length_mm: 300 }))

    await wrapper.get('[data-cell="length"]').setValue('')

    expect(wrapper.emitted('update:length')).toEqual([[0]])
  })

  it('keeps the rotation switch visible for non-grained material', () => {
    seedPanel(false)

    const wrapper = mountRow(part())

    expect(wrapper.find('[data-test="follow-grain"][role="switch"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Burilish')
  })

  // The switch names rotation, not grain: on = rotation allowed = follow_grain
  // false. Both directions are asserted so the inversion can't silently drop.
  it('emits false when the rotation switch is turned on', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ follow_grain: true }))

    await wrapper.get('[data-test="follow-grain"]').trigger('click')

    expect(wrapper.emitted('update:follow-grain')).toEqual([[false]])
  })

  it('emits true when the rotation switch is turned off', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ follow_grain: false }))

    await wrapper.get('[data-test="follow-grain"]').trigger('click')

    expect(wrapper.emitted('update:follow-grain')).toEqual([[true]])
  })

  it('reports switch state and glyph from follow_grain', () => {
    seedPanel(true)

    const locked = mountRow(part({ follow_grain: true }))
    const free = mountRow(part({ follow_grain: false }))

    expect(locked.get('[data-test="follow-grain"]').attributes('aria-checked')).toBe('false')
    expect(free.get('[data-test="follow-grain"]').attributes('aria-checked')).toBe('true')
    expect(locked.get('[data-test="follow-grain"] icon-stub').attributes('name')).toBe('grain')
    expect(free.get('[data-test="follow-grain"] icon-stub').attributes('name')).toBe('rotate')
  })

  it('renders one edge glyph and opens the shared edge dialog', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ edge_left: { material_id: 'edge-1', source: 'shop' } }), [
      {
        key: 'edge-1:shop',
        materialId: 'edge-1',
        source: 'shop',
        number: 1,
        colorStyle: { bg: '#D85A30', fg: '#ffffff', soft: '#fde2d6' },
      },
    ])

    const glyph = wrapper.get('[data-cell="edge"]')
    expect(wrapper.findAll('[data-cell="edge"]')).toHaveLength(1)
    expect(glyph.attributes('aria-label')).toBe('Kromka tomonlari')
    expect(glyph.attributes('style')).toContain('border-left: 3px solid')

    await glyph.trigger('click')

    expect(wrapper.emitted('open-edge-picker')).toHaveLength(1)
    expect(wrapper.emitted('open-edge-picker')?.[0]).toHaveLength(1)
  })

  it('shows the edge glyph with dashed borders when no edge is selected', () => {
    seedPanel(true)
    const wrapper = mountRow(part())

    expect(wrapper.get('[data-cell="edge"]').attributes('style')).toContain('1px dashed')
  })

  it('opens the material picker from the actions menu', async () => {
    seedPanel(true)
    const wrapper = mountRow(part())

    await wrapper.get('[title="Amallar"]').trigger('click')
    const moveButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes("ko'chirish"))
    expect(moveButton).toBeDefined()
    await moveButton!.trigger('click')

    expect(wrapper.emitted('open-material-picker')).toHaveLength(1)
  })
})
