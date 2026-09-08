import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import BranchDecorCreateForm from '@/shared/components/BranchDecorCreateForm.vue'
import { useWorkshopStore } from '@/shared/stores/workshop'

vi.mock('@/shared/app/authInit', () => ({
  authInit: () => ({ accessToken: 'access-token' }),
}))

vi.mock('@/shared/api/client', () => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      readonly body: unknown,
    ) {
      super(`API ${status}`)
      this.name = 'ApiError'
    }
  }
  return {
    ApiError,
    api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn(), blob: vi.fn() },
    apiErrorCode: (error: unknown) =>
      error instanceof ApiError && typeof error.body === 'object' && error.body !== null
        ? ((error.body as { code?: string }).code ?? null)
        : null,
    apiTraceId: () => null,
    withQuery: (path: string) => path,
  }
})

function mountForm(props: Record<string, unknown> = {}) {
  return mount(BranchDecorCreateForm, {
    props: { branchId: 'branch-1', ...props },
    global: { stubs: { teleport: true } },
  })
}

type Form = ReturnType<typeof mountForm>

/** The manufacturers the form's combobox sees, seeded straight into the store. */
function seedManufacturers() {
  useWorkshopStore().branchManufacturers = [
    { id: 'm-egger', name: 'Egger', own: false },
    { id: 'm-mine', name: 'Oq mebel', own: true },
  ]
}

/** Pick the first real manufacturer through the combobox's listbox. */
async function pickEgger(wrapper: Form) {
  await wrapper.find('input[role="combobox"]').trigger('focus')
  await flushPromises()
  const option = wrapper.findAll('[role="option"]').find((row) => row.text().includes('Egger'))
  await option!.trigger('click')
  await flushPromises()
}

/** Chip rows: thickness first, then size (or tape width). */
function chips(wrapper: Form, label: string) {
  const block = wrapper.findAll('.grid.gap-1').find((node) => node.text().startsWith(label))
  return block!.findAll('button.mp-chip')
}

async function fillName(wrapper: Form, value: string) {
  await wrapper.find('#branch-decor-name').setValue(value)
}

/** «+ Qo'shish» — by its word, since the image field owns outline buttons too. */
async function clickAdd(wrapper: Form) {
  const button = wrapper.findAll('button').find((node) => node.text() === "+ Qo'shish")
  await button!.trigger('click')
}

async function addStandardFormat(wrapper: Form) {
  await chips(wrapper, 'Qalinlik')[2].trigger('click') // 18
  await chips(wrapper, "O'lcham")[0].trigger('click') // 2750×1830
  await clickAdd(wrapper)
}

describe('BranchDecorCreateForm — the workshop enters what the library lacks', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('carries step one’s query into Nomi', () => {
    const wrapper = mountForm({ initialName: 'kastamonu oq' })
    expect((wrapper.find('#branch-decor-name').element as HTMLInputElement).value).toBe(
      'kastamonu oq',
    )
  })

  it('swaps the o‘lcham chip sets when the type changes', async () => {
    const wrapper = mountForm()
    expect(chips(wrapper, 'Qalinlik').map((chip) => chip.text())).toEqual(['10', '16', '18', '25'])
    expect(chips(wrapper, "O'lcham").map((chip) => chip.text())).toEqual([
      '2750×1830',
      '2800×2070',
      '2440×1830',
    ])

    // Kromka is a different axis entirely: tape widths, not sheet sizes.
    const kromka = wrapper.findAll('[role="radio"]').find((chip) => chip.text() === 'Kromka')
    await kromka!.trigger('click')
    expect(chips(wrapper, 'Qalinlik').map((chip) => chip.text())).toEqual(['0.4', '0.8', '1', '2'])
    expect(chips(wrapper, 'Kromka eni').map((chip) => chip.text())).toEqual([
      '19 mm',
      '22 mm',
      '35 mm',
      '42 mm',
    ])
  })

  it('refuses a submit with no o‘lcham, and names the field', async () => {
    seedManufacturers()
    const wrapper = mountForm()
    await pickEgger(wrapper)
    await fillName(wrapper, 'Oq yog’och')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain("Kamida bitta o'lcham qo'shing")
    expect(api.post).not.toHaveBeenCalled()
  })

  it('refuses the same o‘lcham twice in one list', async () => {
    const wrapper = mountForm()
    await addStandardFormat(wrapper)
    await addStandardFormat(wrapper)
    expect(wrapper.text()).toContain("Bu o'lcham allaqachon ro'yxatda")
    expect(wrapper.findAll('li')).toHaveLength(1)
  })

  it('posts the composed decor, one entry per o‘lcham, sides on the boards', async () => {
    seedManufacturers()
    vi.mocked(api.post).mockResolvedValue({ decor: { id: 'd-new' }, formats: [] })
    vi.mocked(api.get).mockResolvedValue([])
    const wrapper = mountForm()
    await pickEgger(wrapper)
    await fillName(wrapper, 'Oq daraxt')
    await wrapper.find('input[placeholder="H1145"]').setValue('H1145')
    await addStandardFormat(wrapper)
    // «1 tomonlama» is the exception a buyer has to see; two-sided is silent.
    await wrapper.findAll('input[type="checkbox"]').at(-1)!.setValue(true)
    await chips(wrapper, 'Qalinlik')[1].trigger('click') // 16
    await chips(wrapper, "O'lcham")[0].trigger('click')
    await clickAdd(wrapper)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const [path, body] = vi.mocked(api.post).mock.calls[0]
    expect(path).toBe('/workshop/branches/branch-1/catalog/decors')
    expect(body).toEqual({
      manufacturer_id: 'm-egger',
      name: 'Oq daraxt',
      code: 'H1145',
      has_grain: false,
      image_file_id: null,
      formats: [
        {
          type: 'ldsp',
          thickness_mm: '18',
          length_mm: 2750,
          width_mm: 1830,
          tape_width_mm: null,
          finished_sides: 2,
        },
        {
          type: 'ldsp',
          thickness_mm: '16',
          length_mm: 2750,
          width_mm: 1830,
          tape_width_mm: null,
          finished_sides: 1,
        },
      ],
    })
  })

  it('sends a kromka as thickness × tape width, with no finished sides', async () => {
    seedManufacturers()
    vi.mocked(api.post).mockResolvedValue({ decor: { id: 'd-new' }, formats: [] })
    vi.mocked(api.get).mockResolvedValue([])
    const wrapper = mountForm()
    await pickEgger(wrapper)
    await fillName(wrapper, 'Oq kromka')
    const kromka = wrapper.findAll('[role="radio"]').find((chip) => chip.text() === 'Kromka')
    await kromka!.trigger('click')
    await chips(wrapper, 'Qalinlik')[1].trigger('click') // 0.8
    await chips(wrapper, 'Kromka eni')[1].trigger('click') // 22
    await clickAdd(wrapper)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const [, body] = vi.mocked(api.post).mock.calls[0]
    expect((body as { formats: unknown[] }).formats).toEqual([
      {
        type: 'kromka',
        thickness_mm: '0.8',
        length_mm: null,
        width_mm: null,
        tape_width_mm: 22,
        finished_sides: null,
      },
    ])
  })

  it('mints a manufacturer inline when the typed name matches none', async () => {
    seedManufacturers()
    vi.mocked(api.post).mockResolvedValue({ decor: { id: 'd-new' }, formats: [] })
    vi.mocked(api.get).mockResolvedValue([])
    const wrapper = mountForm()
    const combobox = wrapper.find('input[role="combobox"]')
    await combobox.setValue('Kastamonu')
    await flushPromises()
    const create = wrapper
      .findAll('[role="option"]')
      .find((row) => row.text().includes('Kastamonu'))
    expect(create!.text()).toContain("ni qo'shish")
    await create!.trigger('click')
    await flushPromises()

    await fillName(wrapper, 'Oq')
    await addStandardFormat(wrapper)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const [, body] = vi.mocked(api.post).mock.calls[0]
    // A name, never an id — the server reuses a folded match and otherwise
    // creates the workshop's own row.
    expect(body).toMatchObject({ manufacturer_name: 'Kastamonu' })
    expect(body).not.toHaveProperty('manufacturer_id')
  })

  it('anchors a 409 decor_exists on the identity fields and names the clash', async () => {
    seedManufacturers()
    const { ApiError } = await import('@/shared/api/client')
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, { code: 'decor_exists', details: { decor_label: 'Egger H1145 Oq' } }),
    )
    const wrapper = mountForm()
    await pickEgger(wrapper)
    await fillName(wrapper, 'Oq')
    await addStandardFormat(wrapper)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const message = wrapper.find('#branch-decor-name-error')
    expect(message.text()).toBe('Bunday dekor bor: Egger H1145 Oq')
    expect(wrapper.find('#branch-decor-name').attributes('aria-invalid')).toBe('true')
    expect(wrapper.find('#branch-decor-name').attributes('aria-describedby')).toBe(
      'branch-decor-name-error',
    )
    expect(wrapper.emitted('created')).toBeUndefined()
  })

  it('drops the o‘lchamlar block in edit mode — a format is immutable', () => {
    const wrapper = mountForm({
      decor: {
        id: 'd-1',
        manufacturer_id: 'm-mine',
        manufacturer_name: 'Oq mebel',
        code: 'A1',
        name: 'Oq',
        has_grain: true,
        image_file_id: null,
        status: 'active',
        label: 'Oq mebel A1 Oq',
        branch_usage_count: 0,
        format_count: 1,
        own: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    })
    expect(wrapper.text()).not.toContain('Qalinlik')
    expect((wrapper.find('#branch-decor-name').element as HTMLInputElement).value).toBe('Oq')
  })
})
