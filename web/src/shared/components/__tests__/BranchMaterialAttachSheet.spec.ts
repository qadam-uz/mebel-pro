import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import BranchDecorCreateForm from '@/shared/components/BranchDecorCreateForm.vue'
import BranchMaterialAttachSheet from '@/shared/components/BranchMaterialAttachSheet.vue'
import type { Decor, DecorFormat, DecorType } from '@/shared/stores/admin'
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
    apiErrorCode: () => null,
    apiTraceId: () => null,
    withQuery: (path: string, params: Record<string, unknown>) => {
      const search = new URLSearchParams()
      for (const [key, value] of Object.entries(params)) {
        if (value === null || value === undefined || value === '') continue
        search.set(key, String(value))
      }
      const query = search.toString()
      return query ? `${path}?${query}` : path
    },
  }
})

function decor(id: string, overrides: Partial<Decor> = {}): Decor {
  return {
    id,
    manufacturer_id: 'maker-1',
    manufacturer_name: 'Egger',
    code: `H${id}`,
    name: 'Dub Sonoma',
    has_grain: false,
    image_file_id: null,
    status: 'active',
    label: `Dekor ${id}`,
    branch_usage_count: 0,
    format_count: 2,
    own: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

/** One platform format of `decorId`. Formats are platform-owned now. */
function format(id: string, decorId: string, overrides: Partial<DecorFormat> = {}): DecorFormat {
  const type = (overrides.type ?? 'ldsp') as DecorType
  return {
    id,
    decor_id: decorId,
    type,
    thickness_mm: '18',
    length_mm: 2800,
    width_mm: 2070,
    tape_width_mm: null,
    finished_sides: 2,
    status: 'active',
    label: `LDSP Egger H${decorId} · 2800×2070×18 mm`,
    own: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

/**
 * `GET .../catalog/decors` is step 1's page; `.../decors/{id}/formats` is step
 * 2's list; `.../catalog/filters` the facets.
 */
function respondWith(
  items: { decor: Decor; carried_format_count: number; available_format_count: number }[],
  formatsByDecor: Record<string, { decor_format: DecorFormat; carried: boolean }[]> = {},
) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.includes('/catalog/filters')) return { manufacturers: [] }
    const formatsMatch = /\/catalog\/decors\/([^/]+)\/formats/.exec(path)
    if (formatsMatch) return formatsByDecor[formatsMatch[1]] ?? []
    if (path.includes('/catalog/decors')) return { items, total: items.length }
    return []
  })
}

function mountSheet() {
  return mount(BranchMaterialAttachSheet, {
    props: { open: true, branchId: 'branch-1' },
    global: { stubs: { teleport: true } },
  })
}

type Sheet = ReturnType<typeof mountSheet>

/** Step 1's rows are doors — one `<button>` filling each row. */
function doors(wrapper: Sheet) {
  return wrapper.findAll('li button')
}

async function openDecor(wrapper: Sheet, index = 0) {
  await doors(wrapper)[index].trigger('click')
  await flushPromises()
}

/** Every o'lcham checkbox of step two, in render order. */
function formatBoxes(wrapper: Sheet) {
  return wrapper.findAll('tbody input[type="checkbox"]')
}

/** A button anywhere in the sheet, found by the word on it. */
function byText(wrapper: Sheet, text: string) {
  return wrapper.findAll('button').find((node) => node.text() === text)
}

/** Compose 16 mm · 2750×1830 in «+ Boshqa o'lcham» and press «+ Qo'shish». */
async function composeFormat(wrapper: Sheet) {
  await byText(wrapper, "+ Boshqa o'lcham")!.trigger('click')
  const chips = wrapper.findAll('button.mp-chip').filter((chip) => chip.attributes('aria-pressed'))
  await chips.find((chip) => chip.text() === '16')!.trigger('click')
  await chips.find((chip) => chip.text() === '2750×1830')!.trigger('click')
  await byText(wrapper, "+ Qo'shish")!.trigger('click')
  await flushPromises()
}

describe('BranchMaterialAttachSheet — one decor at a time', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('opens step two for the row that was clicked, and for no other decor', async () => {
    respondWith(
      [
        { decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 },
        {
          decor: decor('d-2', { label: 'Dekor 2' }),
          carried_format_count: 0,
          available_format_count: 1,
        },
      ],
      {
        'd-1': [{ decor_format: format('f-1', 'd-1'), carried: false }],
        'd-2': [{ decor_format: format('f-2', 'd-2'), carried: false }],
      },
    )
    const wrapper = mountSheet()
    await flushPromises()
    // Nothing is fetched until a door is opened — a hundred decors' formats is a
    // payload nobody reads.
    expect(vi.mocked(api.get).mock.calls.some(([path]) => path.includes('/formats'))).toBe(false)

    await openDecor(wrapper, 1)

    const fetched = vi
      .mocked(api.get)
      .mock.calls.map(([path]) => path)
      .filter((path) => path.includes('/formats'))
    expect(fetched).toEqual(['/workshop/branches/branch-1/catalog/decors/d-2/formats'])
    expect(wrapper.text()).toContain('Dekor 2')
    expect(formatBoxes(wrapper)).toHaveLength(1)
  })

  it('lists the decor’s o‘lchamlar with the carried ones disabled', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 1, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        { decor_format: format('f-2', 'd-1', { thickness_mm: '16' }), carried: true },
      ],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)

    const boxes = formatBoxes(wrapper)
    expect(boxes).toHaveLength(2)
    // Thinnest first: the 16 mm row sorts above the 18 mm one.
    expect(boxes[0].attributes('disabled')).toBeDefined()
    expect(boxes[1].attributes('disabled')).toBeUndefined()
    // Carried rows stay in the table rather than vanishing: hiding them leaves
    // the branch wondering whether the size exists at all.
    expect(wrapper.text()).toContain('Allaqachon bor')
    expect(wrapper.text()).toContain('LDSP · 2800×2070×16 mm')
  })

  it('says how many o‘lchamlar are in against how many exist, as text on the door', async () => {
    respondWith([
      { decor: decor('d-1'), carried_format_count: 1, available_format_count: 3 },
      { decor: decor('d-2'), carried_format_count: 2, available_format_count: 2 },
      { decor: decor('d-3'), carried_format_count: 0, available_format_count: 4 },
    ])
    const wrapper = mountSheet()
    await flushPromises()

    const rows = doors(wrapper).map((door) => door.text())
    expect(rows[0]).toContain("1/3 o'lcham bor")
    // A fully carried decor is still a door — step 2 shows every row carried,
    // plus the composer.
    expect(rows[1]).toContain('Hammasi bor')
    expect(rows[2]).toContain("4 o'lcham")
    expect(wrapper.find('li input[type="checkbox"]').exists()).toBe(false)
  })

  it('posts one item per ticked o‘lcham, with the price that was typed', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        { decor_format: format('f-2', 'd-1', { thickness_mm: '16' }), carried: false },
      ],
    })
    vi.mocked(api.post).mockResolvedValue({ created: [], skipped: [] })
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)

    await formatBoxes(wrapper)[0].trigger('change')
    await formatBoxes(wrapper)[1].trigger('change')
    // The price input opens disabled and is enabled by its own tick.
    const prices = wrapper.findAll('tbody input.mp-input')
    await prices[0].setValue('410000')
    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    const [path, body] = vi.mocked(api.post).mock.calls[0]
    expect(path).toBe('/workshop/branches/branch-1/materials')
    expect(body).toEqual({
      items: [
        { decor_format_id: 'f-2', price_tiyin: 41000000 },
        // Price left blank means "not priced yet" — 0 tiyin, not a rejection.
        { decor_format_id: 'f-1', price_tiyin: 0 },
      ],
    })
  })

  it('counts the ticked rows on the button and refuses to submit at zero', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        { decor_format: format('f-2', 'd-1', { thickness_mm: '16' }), carried: false },
      ],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)

    const submit = () => wrapper.find('button.mp-button-primary')
    expect(submit().attributes('disabled')).toBeDefined()
    await formatBoxes(wrapper)[0].trigger('change')
    expect(submit().text()).toBe("Qo'shish (1)")
    await formatBoxes(wrapper)[1].trigger('change')
    expect(submit().text()).toBe("Qo'shish (2)")
    expect(api.post).not.toHaveBeenCalled()
  })

  it('hands the decor and the counts to its parent, which closes the sheet', async () => {
    respondWith(
      [
        {
          decor: decor('d-1', { label: 'Egger H1145' }),
          carried_format_count: 0,
          available_format_count: 1,
        },
      ],
      {
        'd-1': [{ decor_format: format('f-1', 'd-1'), carried: false }],
      },
    )
    const store = useWorkshopStore()
    vi.spyOn(store, 'attachBranchMaterials').mockResolvedValue({
      created: [],
      // A format a concurrent attach already registered — a race, not user
      // error, so the sheet surfaces it as a notice.
      skipped: ['f-9'],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)

    // One addable o'lcham: it arrives ticked, so submit is one click.
    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('attached')?.[0]).toEqual([
      { created: 0, skipped: 1, decorLabel: 'Egger H1145' },
    ])
  })

  it('goes back to a decor list that kept its search and its page', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }], {
      'd-1': [{ decor_format: format('f-1', 'd-1'), carried: false }],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)
    const before = vi.mocked(api.get).mock.calls.length

    await byText(wrapper, 'Orqaga')!.trigger('click')
    await flushPromises()

    expect(doors(wrapper)).toHaveLength(1)
    // Neither the list nor the formats are re-read: the list is the same list.
    expect(vi.mocked(api.get).mock.calls).toHaveLength(before)
    await openDecor(wrapper)
    expect(vi.mocked(api.get).mock.calls).toHaveLength(before)
  })
})

describe('BranchMaterialAttachSheet — «+ Boshqa o‘lcham», merged in silence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('ticks a row whose shape is already on screen, without asking the server', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        {
          decor_format: format('f-2', 'd-1', {
            thickness_mm: '16',
            length_mm: 2750,
            width_mm: 1830,
          }),
          carried: false,
        },
      ],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)
    await composeFormat(wrapper)

    // The shape the operator typed is a row this decor already has: it is
    // ticked, nothing is created, and nothing is said about it.
    expect(api.post).not.toHaveBeenCalled()
    expect((formatBoxes(wrapper)[0].element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.text()).not.toContain('Sizda bor')
    expect(wrapper.find('button.mp-button-primary').text()).toBe("Qo'shish (1)")
  })

  it('creates a genuinely new o‘lcham and arrives with it ticked', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }], {
      'd-1': [{ decor_format: format('f-1', 'd-1'), carried: false }],
    })
    vi.mocked(api.post).mockResolvedValue(
      format('f-new', 'd-1', { thickness_mm: '16', length_mm: 2750, width_mm: 1830 }),
    )
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)
    await composeFormat(wrapper)

    const [path, body] = vi.mocked(api.post).mock.calls[0]
    expect(path).toBe('/workshop/branches/branch-1/catalog/decors/d-1/formats')
    expect(body).toEqual({
      type: 'ldsp',
      thickness_mm: '16',
      length_mm: 2750,
      width_mm: 1830,
      tape_width_mm: null,
      finished_sides: 2,
    })
    const boxes = formatBoxes(wrapper)
    expect(boxes).toHaveLength(2)
    expect((boxes[0].element as HTMLInputElement).checked).toBe(true)
    // The composer closed on success; nothing was announced.
    expect(byText(wrapper, "+ Qo'shish")).toBeUndefined()
  })

  it('absorbs a 409 twin silently — no toast, no text, just the ticked row', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        {
          decor_format: format('f-2', 'd-1', {
            // A shape the client-side match cannot see as the same one: the
            // server normalises `16.0`, the composer sends `16`.
            thickness_mm: '16.0',
            length_mm: 2750,
            width_mm: 1830,
          }),
          carried: false,
        },
      ],
    })
    const { ApiError } = await import('@/shared/api/client')
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, { code: 'decor_format_exists', details: { decor_format_id: 'f-2' } }),
    )
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)
    await composeFormat(wrapper)

    const boxes = formatBoxes(wrapper)
    expect(boxes).toHaveLength(2)
    expect((boxes[0].element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.text()).not.toContain("O'lcham qo'shilmadi")
    expect(wrapper.text()).not.toContain('Sizda bor')
  })

  it('appends a twin the sheet never listed, after re-reading the decor', async () => {
    const twin = format('f-2', 'd-1', {
      thickness_mm: '16',
      length_mm: 2750,
      width_mm: 1830,
    })
    let listed: { decor_format: DecorFormat; carried: boolean }[] = [
      { decor_format: format('f-1', 'd-1'), carried: false },
    ]
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path.includes('/catalog/filters')) return { manufacturers: [] }
      if (path.includes('/formats')) return listed
      if (path.includes('/catalog/decors')) {
        return {
          items: [{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }],
          total: 1,
        }
      }
      return []
    })
    const { ApiError } = await import('@/shared/api/client')
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, { code: 'decor_format_exists', details: { decor_format_id: 'f-2' } }),
    )
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)
    // The row the server names appears only on a second read — it was not
    // attachable when the sheet listed them.
    listed = [...listed, { decor_format: twin, carried: false }]
    await composeFormat(wrapper)

    const boxes = formatBoxes(wrapper)
    expect(boxes).toHaveLength(2)
    expect((boxes[0].element as HTMLInputElement).checked).toBe(true)
  })

  it('says «Sizda bor» on a row the branch already carries, and posts nothing', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 1, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        {
          decor_format: format('f-2', 'd-1', {
            thickness_mm: '16',
            length_mm: 2750,
            width_mm: 1830,
          }),
          carried: true,
        },
      ],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)
    await composeFormat(wrapper)

    // Nothing to add — the one outcome the operator cannot see for themselves,
    // so it is the one outcome that says anything.
    expect(api.post).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Sizda bor')
    expect(wrapper.text()).not.toContain('Allaqachon bor')
    // …and the composer keeps what was typed, so a near miss is one press away.
    expect(byText(wrapper, "+ Qo'shish")).toBeDefined()
  })

  it('adds a kromka to a board decor — the type belongs to the format', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }], {
      'd-1': [{ decor_format: format('f-1', 'd-1'), carried: false }],
    })
    vi.mocked(api.post).mockResolvedValue(
      format('f-new', 'd-1', {
        type: 'kromka',
        thickness_mm: '0.8',
        length_mm: null,
        width_mm: null,
        tape_width_mm: 22,
        finished_sides: null,
      }),
    )
    const wrapper = mountSheet()
    await flushPromises()
    await openDecor(wrapper)
    await byText(wrapper, "+ Boshqa o'lcham")!.trigger('click')

    // The composer opens on the decor's substrate but is not held to it: one
    // decor carries the board AND the tape that edges it.
    const kromka = wrapper.findAll('[role="radio"]').find((chip) => chip.text() === 'Kromka')
    await kromka!.trigger('click')
    const chips = wrapper
      .findAll('button.mp-chip')
      .filter((chip) => chip.attributes('aria-pressed'))
    await chips.find((chip) => chip.text() === '0.8')!.trigger('click')
    await chips.find((chip) => chip.text() === '22 mm')!.trigger('click')
    await byText(wrapper, "+ Qo'shish")!.trigger('click')
    await flushPromises()

    const [, body] = vi.mocked(api.post).mock.calls[0]
    expect(body).toEqual({
      type: 'kromka',
      thickness_mm: '0.8',
      length_mm: null,
      width_mm: null,
      tape_width_mm: 22,
      finished_sides: null,
    })
    // Kromka sorts last, under the boards.
    expect(wrapper.findAll('tbody tr').at(-1)!.text()).toContain('Kromka · 0.8×22 mm')
  })
})

describe('BranchMaterialAttachSheet — the door to «Yangi dekor»', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('opens the create form from the footer, carrying the typed query', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }])
    const wrapper = mountSheet()
    await flushPromises()

    await byText(wrapper, '+ Yangi dekor')!.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(BranchDecorCreateForm).exists()).toBe(true)
    expect(wrapper.text()).toContain('Yangi dekor')
  })

  it('shows ONE create control: the empty state’s, not the footer’s as well', async () => {
    respondWith([])
    const wrapper = mountSheet()
    await flushPromises()

    // The typed query is what the operator looked for and did not find, so it
    // becomes the new decor's name rather than being thrown away with the step.
    await wrapper.find('input.mp-input').setValue('kastamonu oq')
    await flushPromises()
    expect(
      wrapper.findAll('button').filter((node) => node.text() === '+ Yangi dekor'),
    ).toHaveLength(1)

    await byText(wrapper, '+ Yangi dekor')!.trigger('click')
    await flushPromises()
    const name = wrapper.find('#branch-decor-name').element as HTMLInputElement
    expect(name.value).toBe('kastamonu oq')
  })

  it('drives the form from the modal’s fixed footer, not from inside it', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }])
    const wrapper = mountSheet()
    await flushPromises()
    await byText(wrapper, '+ Yangi dekor')!.trigger('click')
    await flushPromises()

    // One «Yaratish va davom etish», and it is the footer's — the form's own
    // action row is off, so the buttons cannot scroll away with the fields.
    const submits = wrapper
      .findAll('button')
      .filter((node) => node.text() === 'Yaratish va davom etish')
    expect(submits).toHaveLength(1)
    expect(
      wrapper.findComponent(BranchDecorCreateForm).find('button[type="submit"]').exists(),
    ).toBe(false)

    // It still submits the form: an empty one comes back with its errors.
    await submits[0].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Dekor nomini kiriting.')
  })

  it('lands a created decor on step 2 with every o‘lcham ticked', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }])
    const wrapper = mountSheet()
    await flushPromises()
    await byText(wrapper, '+ Yangi dekor')!.trigger('click')
    await flushPromises()

    const created = decor('d-new', { own: true, label: 'Kastamonu Oq' })
    wrapper.findComponent(BranchDecorCreateForm).vm.$emit('created', {
      decor: created,
      formats: [format('f-a', 'd-new'), format('f-b', 'd-new', { thickness_mm: '16' })],
    })
    await flushPromises()

    // Nothing left to choose — the operator just typed the o'lchamlar — so the
    // step opens with a price to put against each of them.
    const boxes = formatBoxes(wrapper)
    expect(boxes).toHaveLength(2)
    expect(boxes.every((box) => (box.element as HTMLInputElement).checked)).toBe(true)
    expect(wrapper.text()).toContain('Sizniki')
    expect(wrapper.find('button.mp-button-primary').text()).toBe("Qo'shish (2)")
  })
})
