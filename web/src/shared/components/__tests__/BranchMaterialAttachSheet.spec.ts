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
    respondWith([{ decor: decor('d-1'), carried_format_count: 1, available_format_count: 1 }], {
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
    await formatBoxes(wrapper)[0].trigger('change')
    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('attached')?.[0]).toEqual([{ created: 0, skipped: 1 }])
  })
})
