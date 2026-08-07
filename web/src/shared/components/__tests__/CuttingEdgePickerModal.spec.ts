import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import CuttingEdgePickerModal from '@/shared/components/CuttingEdgePickerModal.vue'
import type { EdgeRegistryEntry } from '@/shared/app/cuttingEditorDerived'
import {
  useCuttingStore,
  type ClientCatalogMaterialOption,
  type CuttingPart,
} from '@/shared/stores/cutting'

const panel: ClientCatalogMaterialOption = {
  id: 'panel-1',
  kind: 'panel',
  manufacturer_id: 'maker-1',
  manufacturer_name: 'Maker',
  type: 'dsp',
  name: 'Panel',
  thickness_mm: '18',
  color: 'Oak',
  decor_code: 'H1234',
  panel_length_mm: 600,
  panel_width_mm: 400,
  grain_direction: false,
  edge_width_mm: null,
  image_file_id: null,
  branch_carried: true,
  price_tiyin: null,
  display_unit: 'sheet',
}

const edge: ClientCatalogMaterialOption = {
  id: 'edge-1',
  kind: 'edge',
  manufacturer_id: 'maker-1',
  manufacturer_name: 'Maker',
  type: null,
  name: 'Black tape',
  thickness_mm: '1',
  color: 'Black',
  decor_code: null,
  panel_length_mm: null,
  panel_width_mm: null,
  grain_direction: null,
  edge_width_mm: 19,
  image_file_id: null,
  branch_carried: true,
  price_tiyin: null,
  display_unit: 'm',
}

const decorEdge: ClientCatalogMaterialOption = {
  ...edge,
  id: 'edge-decor',
  name: 'Decor tape',
  thickness_mm: '2',
  color: 'Oak',
  decor_code: 'H1234',
  edge_width_mm: 22,
}

const colorEdge: ClientCatalogMaterialOption = {
  ...edge,
  id: 'edge-color',
  name: 'Color tape',
  thickness_mm: '0.4',
  color: 'Oak',
  decor_code: 'Other',
}

const narrowEdge: ClientCatalogMaterialOption = {
  ...edge,
  id: 'edge-narrow',
  name: 'Narrow tape',
  edge_width_mm: 16,
}

const part: CuttingPart = {
  part_ref: 'part-1',
  name: null,
  material_id: panel.id,
  material_source: 'shop',
  follow_grain: false,
  thickened: false,
  length_mm: 300,
  width_mm: 200,
  quantity: 1,
  edge_top: null,
  edge_bottom: null,
  edge_left: null,
  edge_right: null,
}

function mountPicker(edgeRegistry: EdgeRegistryEntry[] = [], groupEdgeIds: string[] = []) {
  return mount(CuttingEdgePickerModal, {
    props: {
      part: null,
      initialSide: null,
      partNumber: 1,
      preferredEdgeId: null,
      preferredBranchId: 'branch-1',
      preferredBranchName: 'Yunusobod',
      edgeRegistry,
      edgeAssignmentEntries: [],
      groupEdgeIds,
      otherGroupEdgeIds: [],
    },
  })
}

async function openPicker(edgeRegistry: EdgeRegistryEntry[] = [], groupEdgeIds: string[] = []) {
  const wrapper = mountPicker(edgeRegistry, groupEdgeIds)
  await wrapper.setProps({ part })
  return wrapper
}

describe('CuttingEdgePickerModal arming', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const cutting = useCuttingStore()
    cutting.panelOptions = [panel]
    cutting.edgeOptions = [edge]
  })

  it('keeps side actions unarmed and opens the catalog for an empty drawing', async () => {
    const wrapper = await openPicker()
    const pattern = (label: string) =>
      wrapper.findAll('button').find((button) => button.text().includes(label))

    expect(wrapper.find('[aria-label="Kromka qidirish"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Hammasi')
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Orqaga'))!
      .trigger('click')

    expect(wrapper.text()).toContain('Avval kromka tanlang — keyin tomonlarni bosing.')
    expect(wrapper.get('button[aria-label^="Yuqori tomon"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[aria-label^="Chap tomon"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[aria-label^="O\'ng tomon"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[aria-label^="Pastki tomon"]').attributes('disabled')).toBeDefined()
    expect(pattern('4 tomon')?.attributes('disabled')).toBeDefined()
    expect(pattern('Kromkasiz')?.attributes('disabled')).toBeUndefined()
  })

  it('enables side actions after the user arms a draft tape', async () => {
    const wrapper = await openPicker(
      [
        {
          key: 'edge-1:shop',
          materialId: edge.id,
          source: 'shop',
          number: 1,
          colorStyle: { bg: '#0f766e', fg: '#ffffff', soft: '#d8f3ea' },
        },
      ],
      [edge.id],
    )

    const tape = wrapper.findAll('button').find((button) => button.text().includes(edge.name))
    const allSides = wrapper.findAll('button').find((button) => button.text().includes('4 tomon'))
    expect(tape).toBeDefined()
    expect(allSides).toBeDefined()
    await tape!.trigger('click')

    expect(wrapper.get('button[aria-label^="Yuqori tomon"]').attributes('disabled')).toBeUndefined()
    expect(allSides!.attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[aria-label="Kromka tomoni shablonlari"]').findAll('button')).toHaveLength(
      2,
    )
    expect(wrapper.text()).not.toContain('1mm')
    expect(wrapper.get('[data-test="edge-part-name"]').text()).toBe('D1')
  })

  it('orders drawing tapes by their registry number', async () => {
    const cutting = useCuttingStore()
    cutting.edgeOptions = [edge, decorEdge]
    const wrapper = await openPicker(
      [
        {
          key: 'edge-1:shop',
          materialId: edge.id,
          source: 'shop',
          number: 2,
          colorStyle: { bg: '#D85A30', fg: '#ffffff', soft: '#fde2d6' },
        },
        {
          key: 'edge-decor:shop',
          materialId: decorEdge.id,
          source: 'shop',
          number: 1,
          colorStyle: { bg: '#0f766e', fg: '#ffffff', soft: '#d8f3ea' },
        },
      ],
      [edge.id, decorEdge.id],
    )
    await wrapper.setProps({
      edgeAssignmentEntries: [
        ['edge-1:shop', 2],
        ['edge-decor:shop', 1],
      ],
    })

    const tapeNames = wrapper
      .get('[aria-label="Kromkalar"]')
      .findAll('button')
      .map((button) => button.text())
      .filter((text) => text.includes('tape'))

    expect(tapeNames).toEqual([
      expect.stringContaining(decorEdge.name),
      expect.stringContaining(edge.name),
    ])
  })

  it('applies the currently selected tape to all four sides', async () => {
    const cutting = useCuttingStore()
    cutting.edgeOptions = [edge, decorEdge]
    const wrapper = await openPicker(
      [
        {
          key: 'edge-1:shop',
          materialId: edge.id,
          source: 'shop',
          number: 1,
          colorStyle: { bg: '#0f766e', fg: '#ffffff', soft: '#d8f3ea' },
        },
        {
          key: 'edge-decor:shop',
          materialId: decorEdge.id,
          source: 'shop',
          number: 2,
          colorStyle: { bg: '#D85A30', fg: '#ffffff', soft: '#fde2d6' },
        },
      ],
      [edge.id, decorEdge.id],
    )

    await wrapper
      .findAll('button')
      .find((button) => button.text().includes(decorEdge.name))!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('4 tomon'))!
      .trigger('click')

    expect(wrapper.emitted('edges-change')?.[0]?.[0]).toMatchObject({
      edges: {
        edge_top: { material_id: decorEdge.id },
        edge_bottom: { material_id: decorEdge.id },
        edge_left: { material_id: decorEdge.id },
        edge_right: { material_id: decorEdge.id },
      },
    })

    // Edges are written live, so the footer's `Tayyor` only closes — the sides
    // above are already applied by the time it is pressed (QAD-153).
    const done = wrapper.findAll('button').find((button) => button.text() === 'Tayyor')!
    expect(done.exists()).toBe(true)
    await done.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('filters the catalog, excludes draft tapes, and returns a new tape armed', async () => {
    const cutting = useCuttingStore()
    cutting.edgeOptions = [edge, decorEdge, colorEdge, narrowEdge]
    const wrapper = await openPicker(
      [
        {
          key: 'edge-1:shop',
          materialId: edge.id,
          source: 'shop',
          number: 1,
          colorStyle: { bg: '#0f766e', fg: '#ffffff', soft: '#d8f3ea' },
        },
      ],
      [edge.id],
    )

    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Yana kromka'))!
      .trigger('click')

    expect(wrapper.text()).toContain("Shu listga mos · Panel bo'yicha")
    expect(wrapper.text()).toContain('dekor mos')
    expect(wrapper.text()).toContain('rang mos')
    expect(wrapper.text()).toContain('Boshqa kromkalar')
    expect(wrapper.text()).toContain('list qalinligidan (18 mm) tor')
    expect(wrapper.text()).not.toContain(edge.name)

    const thicknessFilter = wrapper.get('[aria-label="Qalinlik filtri"]')
    await thicknessFilter
      .findAll('button')
      .find((button) => button.text() === '2 mm')!
      .trigger('click')
    expect(wrapper.text()).toContain(decorEdge.name)
    expect(wrapper.text()).not.toContain(colorEdge.name)

    await thicknessFilter
      .findAll('button')
      .find((button) => button.text() === 'Hammasi')!
      .trigger('click')
    await wrapper.get('[aria-label="Kromka qidirish"]').setValue(edge.name)
    expect(wrapper.text()).toContain("Bu kromka allaqachon chizmada — 1-ro'yxatdan tanlang.")

    await wrapper.get('[aria-label="Kromka qidirish"]').setValue('')
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes(decorEdge.name))!
      .trigger('click')

    expect(wrapper.text()).toContain('Chizmadagi kromkalar')
    expect(wrapper.text()).toContain(decorEdge.name)
    expect(wrapper.text()).toContain('Yangi')
    expect(wrapper.get('button[aria-label^="Yuqori tomon"]').attributes('aria-pressed')).toBe(
      'false',
    )
  })
})
