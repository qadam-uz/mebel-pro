import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CuttingImportWizard from '@/shared/components/CuttingImportWizard.vue'
import { parseCuttingImport } from '@/shared/stores/cuttingImport'

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
          template: '<div data-test="combobox">{{ label }}</div>',
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
    parseMock.mockReset()
  })

  it('rejects non-csv files before calling the parser', async () => {
    const wrapper = mountWizard()

    await chooseFile(wrapper, new File(['x'], 'parts.xlsx'))

    expect(parseMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('faqat CSV')
  })

  it('shows uploaded file name and panel thickness hint on material mapping', async () => {
    parseMock
      .mockResolvedValueOnce({
        status: 'needs_mapping',
        grid: [['Длина', 'Ширина', 'Толщина']],
        guessed_mapping: { length_mm: 0, width_mm: 1, thickness_mm: 2 },
        guessed_skip_rows: 1,
      })
      .mockResolvedValueOnce({
        status: 'parsed',
        total_parts: 1,
        total_pieces: 1,
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
})
