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

function mountRow(rowPart: CuttingPart, edgeRegistry: EdgeRegistryEntry[] = []) {
  return mount(CuttingPartRow, {
    props: {
      part: rowPart,
      index: 0,
      hasError: false,
      sizeError: null,
      materialMissing: false,
      optimizeError: null,
      notCarried: [],
      preferredBranchName: 'Yunusobod',
      edgeRegistry,
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

  it('keeps the texture checkbox visible for non-grained material', () => {
    seedPanel(false)

    const wrapper = mountRow(part())

    expect(wrapper.find('[data-test="follow-grain-desktop"][type="checkbox"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="follow-grain-desktop"]').text()).toBe('')
  })

  it('emits false when active desktop texture checkbox is unchecked', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ follow_grain: true }))

    await wrapper.get('[data-test="follow-grain-desktop"][type="checkbox"]').setValue(false)

    expect(wrapper.emitted('update:follow-grain')).toEqual([[false]])
  })

  it('emits true when inactive desktop texture checkbox is checked', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ follow_grain: false }))

    await wrapper.get('[data-test="follow-grain-desktop"][type="checkbox"]').setValue(true)

    expect(wrapper.emitted('update:follow-grain')).toEqual([[true]])
  })

  it('renders edge cells and opens the shared edge dialog from any cell', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ edge_left: { material_id: 'edge-1', source: 'shop' } }), [
      {
        key: 'edge-1:shop',
        materialId: 'edge-1',
        source: 'shop',
        number: 1,
        colorClass: 'bg-info-soft text-info',
      },
    ])

    expect(wrapper.findAll('[data-cell="edge"]')).toHaveLength(4)

    await wrapper.findAll('[data-cell="edge"]')[2].trigger('click')

    expect(wrapper.emitted('open-edge-picker')).toHaveLength(1)
    expect(wrapper.emitted('open-edge-picker')?.[0]?.[1]).toBe('edge_left')
  })

  it('opens the shared material picker from the material action', async () => {
    seedPanel(true)
    const wrapper = mountRow(part())

    await wrapper.get('[title="Materialni almashtirish"]').trigger('click')

    expect(wrapper.emitted('open-material-picker')).toHaveLength(1)
  })
})
