import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import { useWorkshopSearchStore } from '@/shared/stores/workshopSearch'

vi.mock('@/shared/app/authInit', () => ({
  authInit: () => ({ accessToken: 'token' }),
}))

vi.mock('@/shared/api/client', () => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      readonly body: unknown,
    ) {
      super(`API ${status}`)
    }
  }

  const apiTraceId = (error: unknown) =>
    error instanceof ApiError && typeof error.body === 'object' && error.body
      ? ((error.body as { trace_id?: unknown }).trace_id ?? null)
      : null

  return {
    ApiError,
    apiTraceId,
    api: { get: vi.fn() },
    withQuery: (path: string, params: Record<string, unknown>) => {
      const search = new URLSearchParams()
      for (const [key, value] of Object.entries(params)) {
        if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
      }
      const query = search.toString()
      return query ? `${path}?${query}` : path
    },
  }
})

describe('workshop search store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
  })

  it('searches enabled workshop sources scoped to the selected branch', async () => {
    const store = useWorkshopSearchStore()
    const order = { id: 'order-1', order_number: 'ORD-1' }
    const matchingUser = { id: 'user-1', full_name: 'Ali Valiyev', login: 'ali', phone: '+99890' }
    const otherUser = { id: 'user-2', full_name: 'Madina', login: 'madina', phone: '+99891' }
    const material = { id: 'bm-1', material: { name: 'Ali panel' } }
    const stock = { id: 'stock-1', material: { name: 'Ali panel' } }

    vi.mocked(api.get).mockImplementation(async (path) => {
      if (String(path).startsWith('/workshop/orders')) return [order] as never
      if (path === '/workshop/users') return [matchingUser, otherUser] as never
      if (String(path).startsWith('/workshop/branches/branch-1/materials')) {
        return [material] as never
      }
      if (String(path).startsWith('/workshop/branches/branch-1/stock')) return [stock] as never
      throw new Error(`unexpected path ${String(path)}`)
    })

    await store.search({
      query: 'ali',
      branchId: 'branch-1',
      includeOrders: true,
      includeUsers: true,
      includeCatalog: true,
      includeInventory: true,
    })

    const paths = vi.mocked(api.get).mock.calls.map((call) => String(call[0]))
    expect(paths).toContain(
      '/workshop/orders?branch_id=branch-1&status=all&search=ali&limit=5&offset=0',
    )
    expect(paths).toContain('/workshop/users')
    expect(paths).toContain('/workshop/branches/branch-1/materials?search=ali&status=active')
    expect(paths).toContain('/workshop/branches/branch-1/stock?search=ali')
    expect(store.results.orders).toEqual([order])
    expect(store.results.users).toEqual([matchingUser])
    expect(store.results.materials).toEqual([material])
    expect(store.results.stock).toEqual([stock])
    expect(store.error).toBeNull()
  })

  it('does not call branch-scoped sources without a branch', async () => {
    const store = useWorkshopSearchStore()
    vi.mocked(api.get).mockResolvedValue([])

    await store.search({
      query: 'panel',
      branchId: null,
      includeOrders: false,
      includeCatalog: true,
      includeInventory: true,
    })

    expect(api.get).not.toHaveBeenCalled()
    expect(store.results).toEqual({ orders: [], users: [], materials: [], stock: [] })
  })

  it('keeps successful results when one source fails', async () => {
    const store = useWorkshopSearchStore()
    const user = { id: 'user-1', full_name: 'Ali Valiyev', login: 'ali', phone: '+99890' }

    vi.mocked(api.get).mockImplementation(async (path) => {
      if (String(path).startsWith('/workshop/orders')) {
        throw new ApiError(500, { trace_id: 'tr-search' })
      }
      if (path === '/workshop/users') return [user] as never
      return []
    })

    await store.search({ query: 'ali', includeOrders: true, includeUsers: true })

    expect(store.results.users).toEqual([user])
    expect(store.results.orders).toEqual([])
    expect(store.error).toBe('workshop_search_failed')
    expect(store.traceId).toBe('tr-search')
  })
})
