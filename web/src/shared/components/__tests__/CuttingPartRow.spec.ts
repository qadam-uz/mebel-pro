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
      edge_width_mm: null,
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

    expect(wrapper.find('[data-test="follow-grain"][type="checkbox"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Tekstura')
  })

  it('emits false when active desktop texture checkbox is unchecked', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ follow_grain: true }))

    await wrapper.get('[data-test="follow-grain"][type="checkbox"]').setValue(false)

    expect(wrapper.emitted('update:follow-grain')).toEqual([[false]])
  })

  it('emits true when inactive desktop texture checkbox is checked', async () => {
    seedPanel(true)
    const wrapper = mountRow(part({ follow_grain: false }))

    await wrapper.get('[data-test="follow-grain"][type="checkbox"]').setValue(true)

    expect(wrapper.emitted('update:follow-grain')).toEqual([[true]])
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
    expect(glyph.attributes('aria-label')).toBe('Krom tomonlari')
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
