import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import CuttingImportWizard from '@/shared/components/CuttingImportWizard.vue'
import { parseCuttingImport } from '@/shared/stores/cuttingImport'
import { useCuttingStore } from '@/shared/stores/cutting'

vi.mock('@/shared/stores/cuttingImport', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/stores/cuttingImport')>()
  return {
    ...actual,
    parseCuttingImport: vi.fn(),
  }
})

const parseMock = vi.mocked(parseCuttingImport)

function mountWizard() {
  return mount(CuttingImportWizard, {
    props: {
      open: true,
      panelChoices: [{ value: 'panel-1', label: 'Panel 1' }],
      allPanelChoices: [{ value: 'panel-1', label: 'Panel 1' }],
      edgeChoices: [],
      allEdgeChoices: [],
      hasExistingParts: false,
      currentPieces: 0,
      preferredBranchName: null,
    },
    global: {
      stubs: {
        AppModal: {
          props: ['open', 'title', 'maxWidth'],
          template: '<section v-if="open"><slot /></section>',
        },
        Icon: true,
        SearchCombobox: {
          props: ['modelValue', 'label', 'options', 'placeholder'],
          template:
            '<button type="button" data-test="combobox" @click="$emit(\'update:modelValue\', options[0]?.value ?? null)">{{ label }}</button>',
        },
      },
    },
  })
}

async function chooseFile(wrapper: ReturnType<typeof mountWizard>, file: File) {
  const input = wrapper.get('input[type="file"]').element as HTMLInputElement
  Object.defineProperty(input, 'files', {
    value: [file],
    configurable: true,
  })
  await wrapper.get('input[type="file"]').trigger('change')
  await flushPromises()
}

function continueButton(wrapper: ReturnType<typeof mountWizard>) {
  return wrapper.findAll('button').find((button) => button.text().includes('Davom etish'))
}

describe('CuttingImportWizard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    parseMock.mockReset()
  })

  it('rejects non-csv/xml/map files before calling the parser', async () => {
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['x'], 'parts.xlsx'))

    expect(parseMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('faqat CSV, XML yoki MAP')
  })

  it('shows uploaded file name and panel thickness hint on material mapping', async () => {
    parseMock
      .mockResolvedValueOnce({
        status: 'needs_mapping',
        source_format: 'csv',
        grid: [['Длина', 'Ширина', 'Толщина']],
        guessed_mapping: { length_mm: 0, width_mm: 1, thickness_mm: 2 },
        guessed_skip_rows: 1,
      })
      .mockResolvedValueOnce({
        status: 'parsed',
        source_format: 'csv',
        total_parts: 1,
        total_pieces: 1,
        ignored_object_count: 0,
        panel_materials: [
          { key: 'm1', label: 'ЛДСП EGGER H1334', part_count: 1, thickness_hint: '18' },
        ],
        edge_materials: [],
        skipped_rows: [],
        warnings: [],
        parts: [
          {
            row: 2,
            length_mm: 720,
            width_mm: 450,
            quantity: 1,
            material_key: 'm1',
            follow_grain: true,
            edges: { top: null, bottom: null, left: null, right: null },
          },
        ],
      })
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['csv'], 'kitchen-material.csv', { type: 'text/csv' }))
    await continueButton(wrapper)?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Fayl: kitchen-material.csv')
    expect(wrapper.text()).toContain('18 mm')
  })

  it('skips column mapping for Bazis XML imports and shows XML report notes', async () => {
    parseMock.mockResolvedValueOnce({
      status: 'parsed',
      source_format: 'bazis_xml',
      total_parts: 1,
      total_pieces: 1,
      ignored_object_count: 1,
      panel_materials: [
        { key: 'm1', label: 'ЛДСП EGGER H1334', part_count: 1, thickness_hint: '18' },
      ],
      edge_materials: [],
      skipped_rows: [],
      warnings: [{ code: 'non_rectangular', rows: [1] }],
      parts: [
        {
          row: 1,
          length_mm: 720,
          width_mm: 450,
          quantity: 1,
          material_key: 'm1',
          follow_grain: true,
          edges: { top: null, bottom: null, left: null, right: null },
        },
      ],
    })
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['xml'], 'kitchen.xml', { type: 'application/xml' }))

    expect(wrapper.text()).toContain('Materiallar')
    expect(wrapper.text()).not.toContain('Qaysi ustun nimani bildiradi?')
    expect(wrapper.text()).not.toContain('Ustunlar')

    await wrapper.get('[data-test="combobox"]').trigger('click')
    await continueButton(wrapper)?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain("panel bo'lmagan obyekt")
    expect(wrapper.text()).toContain("To'g'ri to'rtburchak bo'lmagan panel import qilindi")
  })

  it('commits a MAP layout through the workshop store path', async () => {
    const cutting = useCuttingStore()
    cutting.configureScope('workshop')
    cutting.setWalkInClient({ id: 'walk-in-1', name: 'Ali', phone: '+998901112233' })
    const commit = vi.spyOn(cutting, 'commitMapImport').mockResolvedValue({ id: 'draft-map' } as never)
    parseMock.mockResolvedValueOnce({
      status: 'parsed',
      source_format: 'map_2dplace',
      total_parts: 1,
      total_pieces: 1,
      ignored_object_count: 0,
      panel_materials: [{ key: 'm1', label: '2750×1830 mm', part_count: 1, thickness_hint: null }],
      edge_materials: [],
      skipped_rows: [],
      warnings: [],
      parts: [
        {
          row: 1,
          length_mm: 720,
          width_mm: 450,
          quantity: 1,
          material_key: 'm1',
          follow_grain: false,
          edges: { top: null, bottom: null, left: null, right: null },
        },
      ],
      material_groups: [
        { key: 'm1', label: '2750×1830 mm', width_mm: 2750, height_mm: 1830, sheet_count: 1, hint: null },
      ],
      map_layout: {
        description: '',
        customer_name: '',
        order_type: '',
        sheets: [],
        part_rows: [
          {
            row: 1,
            part_ref: 'map-1',
            material_key: 'm1',
            length_mm: 720,
            width_mm: 450,
            quantity: 1,
            follow_grain: false,
            edges: { top: false, bottom: false, left: false, right: false },
            name: 'Shelf',
          },
        ],
      },
    })
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['map'], 'kitchen.map'))
    await wrapper.get('[data-test="combobox"]').trigger('click')
    await continueButton(wrapper)?.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text().includes('Import qilish'))?.trigger('click')
    await flushPromises()

    expect(parseMock).toHaveBeenCalledWith(expect.any(File), undefined, 'workshop')
    expect(commit).toHaveBeenCalledOnce()
  })
})
