import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import CuttingPartRow from '@/shared/components/CuttingPartRow.vue'
import { useCuttingStore, type CuttingPart } from '@/shared/stores/cutting'

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'part-1',
    material_id: 'panel-1',
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

function seedPanel(grain_direction: boolean) {
  const cutting = useCuttingStore()
  cutting.panelOptions = [
    {
      id: 'panel-1',
      kind: 'panel',
      manufacturer_id: 'maker-1',
      manufacturer_name: 'Maker',
      type: 'dsp',
      name: 'Oak',
      thickness_mm: '18',
      color: 'Oak',
      decor_code: null,
      panel_length_mm: 600,
      panel_width_mm: 400,
      grain_direction,
      image_file_id: null,
      branch_carried: true,
      price_tiyin: null,
      display_unit: 'sheet',
    },
  ]
}

function mountRow(rowPart: CuttingPart) {
  return mount(CuttingPartRow, {
    props: {
      part: rowPart,
      index: 0,
      panelChoices: [],
      hasError: false,
      sizeError: null,
      materialMissing: false,
      optimizeError: null,
      notCarried: [],
      preferredBranchName: 'Yunusobod',
      selected: false,
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

  it('renders the follow-grain toggle even for non-grained material', async () => {
    seedPanel(false)

    const wrapper = mountRow(part())

    const toggle = wrapper.get('[data-test="follow-grain-desktop"][aria-pressed="true"]')
    expect(toggle.text()).toContain('Tekstura')

    await toggle.trigger('click')

    expect(wrapper.emitted('update:follow-grain')).toEqual([[false]])
  })

  it('emits false when active desktop follow-grain toggle is clicked', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ follow_grain: true }))

    await wrapper.get('[data-test="follow-grain-desktop"][aria-pressed="true"]').trigger('click')

    expect(wrapper.emitted('update:follow-grain')).toEqual([[false]])
  })

  it('emits true when inactive desktop follow-grain toggle is clicked', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ follow_grain: false }))

    await wrapper.get('[data-test="follow-grain-desktop"][aria-pressed="false"]').trigger('click')

    expect(wrapper.emitted('update:follow-grain')).toEqual([[true]])
  })
})
