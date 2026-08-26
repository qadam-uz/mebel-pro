import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
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

function decor(id: string): Decor {
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
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
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

async function tickDecor(wrapper: Sheet, index = 0) {
  await wrapper.findAll('li input[type="checkbox"]')[index].trigger('change')
}

async function continueToFormats(wrapper: Sheet) {
  await wrapper.find('button.mp-button-primary').trigger('click')
  await flushPromises()
}

/** Every format checkbox in step two, in render order. */
function formatBoxes(wrapper: Sheet) {
  return wrapper.findAll('label input[type="checkbox"]')
}

describe('BranchMaterialAttachSheet — step two picks platform formats', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('lists the decor’s active formats, with carried ones disabled', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 1, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        {
          decor_format: format('f-2', 'd-1', { thickness_mm: '16', label: 'LDSP 16 mm' }),
          carried: true,
        },
      ],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await tickDecor(wrapper)
    await continueToFormats(wrapper)

    const boxes = formatBoxes(wrapper)
    expect(boxes).toHaveLength(2)
    expect(boxes[0].attributes('disabled')).toBeUndefined()
    // Carried rows stay in the list rather than vanishing: hiding them leaves
    // the branch wondering whether the size exists at all.
    expect(boxes[1].attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('LDSP 16 mm')
  })

  it('offers no way to invent a format, and says who can add one', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }], {
      'd-1': [{ decor_format: format('f-1', 'd-1'), carried: false }],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await tickDecor(wrapper)
    await continueToFormats(wrapper)

    // The old "Nostandart · faqat sizda" group and its "+ qo'shish" are gone:
    // a format is the manufacturer's fact, entered once by the platform.
    expect(wrapper.text()).not.toContain('Nostandart')
    expect(wrapper.text()).not.toContain("+ qo'shish")
    // ...and the wait that replaces them is made visible.
    expect(wrapper.text()).toContain('Platformaga xabar bering')
  })

  it('posts one item per ticked format, keyed by decor_format_id', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        { decor_format: format('f-2', 'd-1', { thickness_mm: '16' }), carried: false },
      ],
    })
    vi.mocked(api.post).mockResolvedValue({ created: [], skipped: [] })
    const wrapper = mountSheet()
    await flushPromises()
    await tickDecor(wrapper)
    await continueToFormats(wrapper)

    await formatBoxes(wrapper)[0].trigger('change')
    await formatBoxes(wrapper)[1].trigger('change')
    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    const [path, body] = vi.mocked(api.post).mock.calls[0]
    expect(path).toBe('/workshop/branches/branch-1/materials')
    expect(body).toEqual({
      items: [
        // Price left blank means "not priced yet" — 0 tiyin, not a rejection.
        { decor_format_id: 'f-1', price_tiyin: 0, min_stock: 0 },
        { decor_format_id: 'f-2', price_tiyin: 0, min_stock: 0 },
      ],
    })
  })

  it('never submits a carried format even if it is somehow still in the list', async () => {
    // The picker's page said there was something to add; by the time the formats
    // load a concurrent attach has taken it. The decor was tickable, the format
    // is not.
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }], {
      'd-1': [{ decor_format: format('f-1', 'd-1'), carried: true }],
    })
    vi.mocked(api.post).mockResolvedValue({ created: [], skipped: [] })
    const wrapper = mountSheet()
    await flushPromises()
    await tickDecor(wrapper)
    await continueToFormats(wrapper)

    await formatBoxes(wrapper)[0].trigger('change')
    expect(wrapper.find('button.mp-button-primary').attributes('disabled')).toBeDefined()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('reports created and skipped counts to its parent', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 1 }], {
      'd-1': [{ decor_format: format('f-1', 'd-1'), carried: false }],
    })
    const store = useWorkshopStore()
    vi.spyOn(store, 'attachBranchMaterials').mockResolvedValue({
      created: [],
      // A format a concurrent attach already registered — a race, not user
      // error, so the sheet surfaces it as a notice.
      skipped: ['f-9'],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await tickDecor(wrapper)
    await continueToFormats(wrapper)
    // One decor, one addable format: it arrives ticked, so submit is one click.
    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('attached')?.[0]).toEqual([{ created: 0, skipped: 1 }])
  })

  it('pre-ticks the only addable format for a single decor, and never for a batch', async () => {
    respondWith(
      [
        { decor: decor('d-1'), carried_format_count: 1, available_format_count: 2 },
        { decor: decor('d-2'), carried_format_count: 0, available_format_count: 1 },
      ],
      {
        'd-1': [
          { decor_format: format('f-1', 'd-1'), carried: false },
          { decor_format: format('f-2', 'd-1', { thickness_mm: '16' }), carried: true },
        ],
        'd-2': [{ decor_format: format('f-3', 'd-2'), carried: false }],
      },
    )
    const wrapper = mountSheet()
    await flushPromises()
    await tickDecor(wrapper, 0)
    await continueToFormats(wrapper)

    // The carried row is not "a choice", so the one addable row is the whole
    // decision and comes ticked; the submit button already counts it.
    expect((formatBoxes(wrapper)[0].element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.find('button.mp-button-primary').text()).toContain('1 ta')

    // Back to step 1, add a second decor: a batch is confirmed row by row — a
    // wrong attach can only be deactivated, never deleted — so nothing is
    // guessed, even though each decor still has exactly one addable row.
    await wrapper.findAll('button.mp-button-outline').at(-1)!.trigger('click')
    await tickDecor(wrapper, 1)
    await continueToFormats(wrapper)
    const checked = formatBoxes(wrapper).filter((box) => (box.element as HTMLInputElement).checked)
    expect(checked).toHaveLength(0)
  })

  it('quick-pick chips tick one o‘lcham across the whole selection, or everything', async () => {
    const board = (id: string, decorId: string) => ({
      decor_format: format(id, decorId, { label: `Board ${id}` }),
      carried: false,
    })
    const tape = (id: string, decorId: string) => ({
      decor_format: format(id, decorId, {
        type: 'kromka',
        thickness_mm: '0.8',
        length_mm: null,
        width_mm: null,
        tape_width_mm: 22,
        finished_sides: null,
        label: `Tape ${id}`,
      }),
      carried: false,
    })
    respondWith(
      [
        { decor: decor('d-1'), carried_format_count: 0, available_format_count: 2 },
        { decor: decor('d-2'), carried_format_count: 0, available_format_count: 2 },
        { decor: decor('d-3'), carried_format_count: 0, available_format_count: 1 },
      ],
      {
        'd-1': [board('f-1', 'd-1'), tape('f-2', 'd-1')],
        'd-2': [board('f-3', 'd-2'), tape('f-4', 'd-2')],
        'd-3': [board('f-5', 'd-3')],
      },
    )
    vi.mocked(api.post).mockResolvedValue({ created: [], skipped: [] })
    const wrapper = mountSheet()
    await flushPromises()
    await tickDecor(wrapper, 0)
    await tickDecor(wrapper, 1)
    await tickDecor(wrapper, 2)
    await continueToFormats(wrapper)

    const chips = () => wrapper.findAll('button[aria-pressed]')
    // Most shared first: the board is in three decors, the tape in two, then «Hammasi».
    // Two finished faces is the default and says nothing, so it is not printed;
    // a one-sided format would carry its note here.
    expect(chips().map((chip) => chip.text())).toEqual([
      'LDSP · 2800×2070×18 mm (3)',
      'Kromka · 0.8×22 mm (2)',
      'Hammasi (5)',
    ])

    // One press ticks the board under every decor and nothing else…
    await chips()[0].trigger('click')
    expect(chips()[0].attributes('aria-pressed')).toBe('true')
    expect(wrapper.find('button.mp-button-primary').text()).toContain('3 ta')
    // …a second press unticks exactly those three…
    await chips()[0].trigger('click')
    expect(wrapper.find('button.mp-button-primary').attributes('disabled')).toBeDefined()
    // …and «Hammasi» takes the lot.
    await chips()[2].trigger('click')
    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()
    const [, body] = vi.mocked(api.post).mock.calls[0]
    expect((body as { items: unknown[] }).items).toHaveLength(5)
  })

  it('step one says how many o‘lchamlar are in against how many exist', async () => {
    respondWith([
      { decor: decor('d-1'), carried_format_count: 1, available_format_count: 3 },
      { decor: decor('d-2'), carried_format_count: 2, available_format_count: 2 },
      { decor: decor('d-3'), carried_format_count: 0, available_format_count: 4 },
    ])
    const wrapper = mountSheet()
    await flushPromises()
    const chips = wrapper.findAll('li .mp-chip').map((chip) => chip.text())
    // A partly carried decor is an invitation, a fully carried one is an answer,
    // and an untouched one still says how many sizes are behind it.
    expect(chips).toEqual(["1/3 o'lcham bor", 'Hammasi bor', "4 o'lcham"])
  })

  it('prints the finished-faces note only when a format is one-sided', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 0, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        { decor_format: format('f-2', 'd-1', { finished_sides: 1 }), carried: false },
      ],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await wrapper.find('li button[aria-expanded]').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('li li').map((row) => row.text())).toEqual([
      'LDSP · 2800×2070×18 mm',
      'LDSP · 2800×2070×18 mm · 1 tomonlama',
    ])
  })

  it('gives a decor with nothing left to add no checkbox at all', async () => {
    respondWith([
      { decor: decor('d-1'), carried_format_count: 2, available_format_count: 2 },
      { decor: decor('d-2'), carried_format_count: 1, available_format_count: 2 },
    ])
    const wrapper = mountSheet()
    await flushPromises()

    // Ticking a fully carried decor led to a step two of disabled rows and a
    // submit that refused — so the checkbox is gone, while the row (and its
    // o'lcham list) stays as the proof that it IS carried.
    const rows = wrapper.findAll('li')
    expect(rows[0].find('input[type="checkbox"]').exists()).toBe(false)
    expect(rows[1].find('input[type="checkbox"]').exists()).toBe(true)
    expect(rows[0].find('button[aria-expanded]').exists()).toBe(true)

    // «Filtrdagi hammasi» collects only what can still be added.
    await wrapper.find('input[type="checkbox"]').trigger('change')
    await flushPromises()
    expect(wrapper.text()).toContain('1 ta tanlandi')
  })

  it('offers no bulk select when the whole filter is already carried', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 2, available_format_count: 2 }])
    const wrapper = mountSheet()
    await flushPromises()

    const master = wrapper.find('input[type="checkbox"]')
    expect(master.attributes('disabled')).toBeDefined()
    expect((master.element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.text()).toContain('allaqachon qo‘shilgan'.replace('‘', "'"))
  })

  it('opens a decor’s o‘lchamlar in step one without ticking the decor', async () => {
    respondWith([{ decor: decor('d-1'), carried_format_count: 1, available_format_count: 2 }], {
      'd-1': [
        { decor_format: format('f-1', 'd-1'), carried: false },
        { decor_format: format('f-2', 'd-1', { thickness_mm: '16' }), carried: true },
      ],
    })
    const wrapper = mountSheet()
    await flushPromises()

    // Nothing is fetched until the row is opened — a hundred decors' formats is
    // a payload nobody reads.
    expect(vi.mocked(api.get).mock.calls.some(([path]) => path.includes('/formats'))).toBe(false)

    await wrapper.find('li button[aria-expanded]').trigger('click')
    await flushPromises()

    // The o'lchamlar are named — identity-free, since the decor is the heading
    // right above them — and the carried one is marked rather than hidden.
    const preview = wrapper.findAll('li li').map((row) => row.text())
    expect(preview).toEqual(['LDSP · 2800×2070×18 mm', 'LDSP · 2800×2070×16 mmAllaqachon bor'])
    // Reading the sizes is not choosing the decor: the checkbox is untouched.
    expect((wrapper.find('li input[type="checkbox"]').element as HTMLInputElement).checked).toBe(
      false,
    )

    // …and what step 1 fetched, step 2 does not fetch again.
    const before = vi.mocked(api.get).mock.calls.length
    await tickDecor(wrapper)
    await continueToFormats(wrapper)
    expect(vi.mocked(api.get).mock.calls).toHaveLength(before)
    expect(formatBoxes(wrapper)).toHaveLength(2)
  })
})
