import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import CuttingImportWizard from '@/shared/components/CuttingImportWizard.vue'
import { parseCuttingImport, type ImportParsedResponse } from '@/shared/stores/cuttingImport'
import { useCuttingStore } from '@/shared/stores/cutting'

vi.mock('@/shared/stores/cuttingImport', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/stores/cuttingImport')>()
  return {
    ...actual,
    parseCuttingImport: vi.fn(),
  }
})

const parseMock = vi.mocked(parseCuttingImport)

function mountWizard(props: Record<string, unknown> = {}) {
  return mount(CuttingImportWizard, {
    props: {
      open: true,
      panelChoices: [{ value: 'panel-1', label: 'Panel 1' }],
      edgeChoices: [],
      hasExistingParts: false,
      currentPieces: 0,
      currentParts: 0,
      preferredBranchName: null,
      ...props,
    },
    global: {
      stubs: {
        AppModal: {
          props: ['open', 'title', 'maxWidth'],
          template: '<section v-if="open"><slot /></section>',
        },
        Icon: true,
        SearchCombobox: {
          props: ['modelValue', 'label', 'options', 'placeholder', 'hint'],
          template:
            '<button type="button" data-test="combobox" @click="$emit(\'update:modelValue\', options[0]?.value ?? null)">{{ label }}</button>',
        },
        SegmentedControl: {
          props: ['modelValue', 'label', 'options'],
          template:
            '<div data-test="mode"><button v-for="o in options" :key="o.value" type="button" :data-mode="o.value" @click="$emit(\'update:modelValue\', o.value)">{{ o.label }}</button></div>',
        },
      },
    },
  })
}

async function chooseFile(wrapper: ReturnType<typeof mountWizard>, file: File) {
  const input = wrapper.get('input[type="file"]').element as HTMLInputElement
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  await wrapper.get('input[type="file"]').trigger('change')
  await flushPromises()
}

function button(wrapper: ReturnType<typeof mountWizard>, text: string) {
  return wrapper.findAll('button').find((item) => item.text().includes(text))
}

function parsedCsv(overrides: Partial<ImportParsedResponse> = {}): ImportParsedResponse {
  return {
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
    ...overrides,
  } as ImportParsedResponse
}

// A CSV arrives needing a mapping, but the backend guesses it — so the dialog
// parses straight through and the review screen opens with real materials.
function mockCsvRoundTrip(parsed: ImportParsedResponse = parsedCsv()) {
  parseMock
    .mockResolvedValueOnce({
      status: 'needs_mapping',
      source_format: 'csv',
      grid: [['Длина', 'Ширина', 'Толщина']],
      guessed_mapping: { length_mm: 0, width_mm: 1, thickness_mm: 2 },
      guessed_skip_rows: 1,
    })
    .mockResolvedValueOnce(parsed)
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

  it('names every accepted extension with the program that exports it', () => {
    // A first-time importer does not know `.map` is 2D-Place's word, so this
    // cannot hide behind a disclosure they have no reason to open.
    const wrapper = mountWizard()
    const text = wrapper.text()

    for (const extension of ['.csv', '.xml', '.map']) {
      expect(text).toContain(extension)
    }
    expect(text).toContain('БАЗИС-Мебельщик')
    expect(text).toContain('2D-Place')
    expect(text).toContain('«Спецификация в XML»')
    expect(text).toContain('Сохранить как → CSV')
  })

  it('never draws a step rail — the step count depended on a file not yet chosen', async () => {
    mockCsvRoundTrip()
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['csv'], 'kitchen.csv', { type: 'text/csv' }))

    expect(wrapper.text()).not.toContain('Xulosa')
    expect(wrapper.text()).not.toContain('Tekshirish')
    expect(button(wrapper, 'Orqaga')).toBeUndefined()
    expect(button(wrapper, 'Davom etish')).toBeUndefined()
  })

  it('parses through a confident guess and collapses columns to one summary line', async () => {
    mockCsvRoundTrip()
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['csv'], 'kitchen-material.csv', { type: 'text/csv' }))

    // Two calls: the detect, then the parse the guess earned without a click.
    expect(parseMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Ustunlar aniqlandi')
    expect(wrapper.text()).toContain('A→Uzunlik (mm)')
    expect(wrapper.text()).toContain('kitchen-material.csv')
    expect(wrapper.text()).toContain('18 mm')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('opens the columns block itself when the guess is short of what parsing needs', async () => {
    parseMock.mockResolvedValueOnce({
      status: 'needs_mapping',
      source_format: 'csv',
      grid: [['Длина', 'Прочее']],
      guessed_mapping: { length_mm: 0 },
      guessed_skip_rows: 0,
    })
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['csv'], 'kitchen.csv', { type: 'text/csv' }))

    expect(parseMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Uzunlik va kenglik ustunlarini tanlang')
    expect(wrapper.find('table').exists()).toBe(true)
    expect(button(wrapper, 'Import qilish')).toBeUndefined()
  })

  it('puts what the parser dropped ahead of the commit, not on a screen after it', async () => {
    mockCsvRoundTrip(
      parsedCsv({
        skipped_rows: [{ row: 4, reason: 'non_numeric_length', preview: 'Полка;;' }],
        warnings: [{ code: 'non_rectangular', rows: [7] }],
      }),
    )
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['csv'], 'kitchen.csv', { type: 'text/csv' }))

    // Visible while the commit is still ahead of the operator, and countable
    // without opening anything.
    expect(wrapper.text()).toContain("1 qator o'tkazib yuborildi")
    expect(wrapper.text()).toContain('1 ogohlantirish')
    expect(button(wrapper, 'Import qilish')).toBeDefined()

    await button(wrapper, "1 qator o'tkazib yuborildi")?.trigger('click')

    expect(wrapper.text()).toContain('4-qator:')
  })

  it('blocks the commit until every material group is picked', async () => {
    mockCsvRoundTrip()
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['csv'], 'kitchen.csv', { type: 'text/csv' }))

    expect(button(wrapper, 'Import qilish')?.attributes('disabled')).toBeDefined()

    await wrapper.get('[data-test="combobox"]').trigger('click')

    expect(button(wrapper, 'Import qilish')?.attributes('disabled')).toBeUndefined()
  })

  it('names what replacing costs instead of colouring a second button red', async () => {
    mockCsvRoundTrip(parsedCsv({ total_parts: 24, total_pieces: 86 }))
    const wrapper = mountWizard({ hasExistingParts: true, currentParts: 7, currentPieces: 20 })

    await chooseFile(wrapper, new File(['csv'], 'kitchen.csv', { type: 'text/csv' }))
    await wrapper.get('[data-test="combobox"]').trigger('click')

    expect(wrapper.text()).toContain("24 xil qo'shiladi — jami 31 xil")
    expect(
      wrapper.findAll('button').filter((item) => item.text() === 'Import qilish'),
    ).toHaveLength(1)

    await wrapper.get('[data-mode="replace"]').trigger('click')

    expect(wrapper.text()).toContain("Hozirgi 7 xil o'chadi")
  })

  it('refuses the commit when the import would breach the piece cap', async () => {
    mockCsvRoundTrip(parsedCsv({ total_parts: 40, total_pieces: 400 }))
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['csv'], 'kitchen.csv', { type: 'text/csv' }))
    await wrapper.get('[data-test="combobox"]').trigger('click')

    expect(wrapper.get('[data-testid="import-cap-warning"]').text()).toContain('400')
    expect(button(wrapper, 'Import qilish')?.attributes('disabled')).toBeDefined()
  })

  it('skips the columns block entirely for Bazis XML and files its notes as chips', async () => {
    parseMock.mockResolvedValueOnce(
      parsedCsv({
        source_format: 'bazis_xml',
        ignored_object_count: 1,
        warnings: [{ code: 'non_rectangular', rows: [1] }],
      }),
    )
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['xml'], 'kitchen.xml', { type: 'application/xml' }))

    expect(wrapper.text()).toContain('Materiallar')
    expect(wrapper.text()).not.toContain('Ustunlar aniqlandi')
    expect(wrapper.text()).toContain('1 obyekt import qilinmadi')

    await button(wrapper, '1 obyekt import qilinmadi')?.trigger('click')

    expect(wrapper.text()).toContain("list bo'lmagan obyekt")
  })

  it('commits a MAP layout through the workshop store path', async () => {
    const cutting = useCuttingStore()
    cutting.configureScope('workshop')
    cutting.setWalkInClient({ id: 'walk-in-1', name: 'Ali', phone: '+998901112233' })
    const commit = vi
      .spyOn(cutting, 'commitMapImport')
      .mockResolvedValue({ id: 'draft-map' } as never)
    parseMock.mockResolvedValueOnce(
      parsedCsv({
        source_format: 'map_2dplace',
        panel_materials: [
          { key: 'm1', label: '2750×1830 mm', part_count: 1, thickness_hint: null },
        ],
        material_groups: [
          {
            key: 'm1',
            label: '2750×1830 mm',
            width_mm: 2750,
            height_mm: 1830,
            sheet_count: 1,
            hint: null,
          },
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
      }),
    )
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['map'], 'kitchen.map'))
    await wrapper.get('[data-test="combobox"]').trigger('click')
    await button(wrapper, 'Import qilish')?.trigger('click')
    await flushPromises()

    expect(parseMock).toHaveBeenCalledWith(expect.any(File), undefined, 'workshop')
    expect(commit).toHaveBeenCalledOnce()
    // The uploaded file's name travels to the commit payload so the backend
    // can seed the new draft's name from it (extension stripped server-side).
    expect(commit).toHaveBeenCalledWith(expect.objectContaining({ source_filename: 'kitchen.map' }))
    expect(wrapper.emitted('committed')).toEqual([['draft-map']])
  })
})
