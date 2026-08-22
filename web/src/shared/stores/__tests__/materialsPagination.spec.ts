import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { api } from '@/shared/api/client'
import { CATALOG_PICKER_LIMIT, MATERIALS_PAGE_LIMIT } from '@/shared/app/constants'
import { useAdminStore } from '@/shared/stores/admin'
import { useWorkshopStore } from '@/shared/stores/workshop'

vi.mock('@/shared/app/authInit', () => ({
  authInit: () => ({ accessToken: 'access-token' }),
}))

// Mirror the orders-store spec: stub the HTTP layer, and make withQuery return the
// path with a readable query string so tests can assert the limit/offset sent.
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
    captureApiError: vi.fn((_error: unknown, fallback: string) => ({
      code: fallback,
      traceId: null,
    })),
    withQuery: (path: string, params: Record<string, unknown>) => {
      const search = new URLSearchParams()
      for (const [key, value] of Object.entries(params)) {
        if (value === null || value === undefined || value === '') continue
        if (Array.isArray(value)) value.forEach((item) => search.append(key, String(item)))
        else search.set(key, String(value))
      }
      const query = search.toString()
      return query ? `${path}?${query}` : path
    },
  }
})

// Length is all these tests inspect (append/replace + has-more), so id-only rows
// stand in for the real Decor / BranchMaterial shapes. Row shape is invisible
// here by design — the value of this file is the QUERY assertions.
function page(size: number, prefix: string): { id: string }[] {
  return Array.from({ length: size }, (_, index) => ({ id: `${prefix}-${index}` }))
}

function lastGetUrl(): string {
  const calls = vi.mocked(api.get).mock.calls
  return calls[calls.length - 1][0]
}

describe('admin store — dekors pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
  })

  it('sends limit/offset and flags has-more on a full first page', async () => {
    vi.mocked(api.get).mockResolvedValueOnce(page(MATERIALS_PAGE_LIMIT, 'm'))
    const store = useAdminStore()

    await store.loadDecors()

    expect(store.decors).toHaveLength(MATERIALS_PAGE_LIMIT)
    expect(store.decorsHasMore).toBe(true)
    expect(lastGetUrl()).toContain(`limit=${MATERIALS_PAGE_LIMIT}`)
    expect(lastGetUrl()).toContain('offset=0')
  })

  it('appends the next page and clears has-more when it is short', async () => {
    vi.mocked(api.get).mockResolvedValueOnce(page(MATERIALS_PAGE_LIMIT, 'm'))
    const store = useAdminStore()
    await store.loadDecors()

    vi.mocked(api.get).mockResolvedValueOnce(page(10, 'm2'))
    await store.loadDecors({ offset: store.decors.length })

    expect(store.decors).toHaveLength(MATERIALS_PAGE_LIMIT + 10)
    expect(store.decorsHasMore).toBe(false)
    expect(lastGetUrl()).toContain(`offset=${MATERIALS_PAGE_LIMIT}`)
  })

  it('replaces (does not append) on a filter reload at offset 0', async () => {
    vi.mocked(api.get).mockResolvedValueOnce(page(MATERIALS_PAGE_LIMIT, 'm'))
    const store = useAdminStore()
    await store.loadDecors()

    vi.mocked(api.get).mockResolvedValueOnce(page(3, 'search'))
    await store.loadDecors({ search: 'oak', type: 'ldsp', manufacturerIds: ['mfr-1', 'mfr-2'] })

    expect(store.decors).toHaveLength(3)
    expect(store.decorsHasMore).toBe(false)
    const url = lastGetUrl()
    expect(url).toContain('/platform/catalog/decors')
    expect(url).toContain('search=oak')
    expect(url).toContain('type=ldsp')
    expect(url).toContain('manufacturer_ids=mfr-1')
    expect(url).toContain('manufacturer_ids=mfr-2')
  })
})

describe('workshop store — branch materials pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
  })

  it('appends higher offsets and infers has-more from a full page', async () => {
    vi.mocked(api.get).mockResolvedValueOnce(page(MATERIALS_PAGE_LIMIT, 'bm'))
    const store = useWorkshopStore()
    await store.loadBranchMaterials('branch-1')
    expect(store.branchMaterials).toHaveLength(MATERIALS_PAGE_LIMIT)
    expect(store.branchMaterialsHasMore).toBe(true)

    vi.mocked(api.get).mockResolvedValueOnce(page(5, 'bm2'))
    await store.loadBranchMaterials('branch-1', { offset: store.branchMaterials.length })
    expect(store.branchMaterials).toHaveLength(MATERIALS_PAGE_LIMIT + 5)
    expect(store.branchMaterialsHasMore).toBe(false)
  })

  it('caps the add-material picker instead of loading the whole catalog', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      items: page(CATALOG_PICKER_LIMIT, 'opt'),
      total: 512,
    })
    const store = useWorkshopStore()

    await store.loadCatalogOptions('branch-1', { search: 'egger' })

    expect(store.catalogOptions).toHaveLength(CATALOG_PICKER_LIMIT)
    // The total counts the whole filtered set, not the capped page — that is what
    // the picker's "Filtrdagi hammasi (N)" master checkbox promises to select.
    expect(store.catalogOptionsTotal).toBe(512)
    expect(lastGetUrl()).toContain(`limit=${CATALOG_PICKER_LIMIT}`)
    expect(lastGetUrl()).toContain('search=egger')
  })

  // The `thickness_mm=0.8` facet this used to assert is GONE, not renamed: a
  // format is a branch fact now, so `BranchCatalogFiltersResponse` enumerates
  // manufacturers only and the picker has no thickness axis to filter on.
  it('passes the picker filters through to the catalog options query', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ items: [], total: 0 })
    const store = useWorkshopStore()

    await store.fetchCatalogOptions('branch-1', {
      manufacturer_id: 'mfr-9',
      type: 'kromka',
      limit: 100,
      offset: 100,
    })

    const url = lastGetUrl()
    expect(url).toContain('/workshop/branches/branch-1/catalog/decors')
    expect(url).toContain('manufacturer_id=mfr-9')
    expect(url).toContain('type=kromka')
    expect(url).toContain('offset=100')
  })
})
