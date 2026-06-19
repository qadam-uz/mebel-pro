import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import { INVENTORY_TX_PAGE_LIMIT } from '@/shared/app/constants'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

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
  const apiErrorCode = (error: unknown) => {
    if (error instanceof ApiError && typeof error.body === 'object' && error.body) {
      const code = (error.body as { code?: unknown }).code
      return typeof code === 'string' ? code : null
    }
    return null
  }

  return {
    ApiError,
    apiTraceId,
    apiErrorCode,
    captureApiError: (error: unknown, fallback: string) => ({
      code:
        error instanceof ApiError && error.status === 403
          ? 'permission_denied'
          : (apiErrorCode(error) ?? fallback),
      traceId: apiTraceId(error),
    }),
    api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() },
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

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

describe('workshop store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
    vi.mocked(api.put).mockReset()
    vi.mocked(api.patch).mockReset()
    vi.mocked(api.del).mockReset()
  })

  it('captures backend action code and trace for failed user mutations', async () => {
    const store = useWorkshopStore()
    vi.mocked(api.post).mockRejectedValueOnce(new ApiError(403, { trace_id: 'tr-user-1' }))

    await expect(store.resetPassword('user-1')).rejects.toBeInstanceOf(ApiError)

    expect(store.actionError).toBe('permission_denied')
    expect(store.actionTraceId).toBe('tr-user-1')
    expect(store.error).toBeNull()
  })

  it('does not refetch branch context until forced', async () => {
    const store = useWorkshopStore()
    const branch = {
      id: 'branch-1',
      name: 'Main',
      address: 'Tashkent',
      phone: '+998901234567',
      status: 'active',
      closed_reason: null,
      permissions: [],
    }
    vi.mocked(api.get).mockResolvedValue({ branches: [branch] })

    await store.loadBranchContext()
    await store.loadBranchContext()
    await store.loadBranchContext({ force: true })

    expect(api.get).toHaveBeenCalledTimes(2)
    expect(store.branches).toEqual([branch])
  })

  it('paginates stock transactions with date filters', async () => {
    const store = useWorkshopStore()
    const fullPage = Array.from(
      { length: INVENTORY_TX_PAGE_LIMIT },
      (_, i) => ({ id: `tx-${i}` }) as never,
    )
    vi.mocked(api.get).mockResolvedValueOnce(fullPage)

    await store.loadStockTransactions('branch-1', {
      material_id: 'mat-1',
      date_from: '2026-06-01',
      date_to: '2026-06-19',
    })

    expect(vi.mocked(api.get).mock.calls[0][0]).toContain(
      '/workshop/branches/branch-1/stock-transactions?',
    )
    expect(vi.mocked(api.get).mock.calls[0][0]).toContain('material_id=mat-1')
    expect(vi.mocked(api.get).mock.calls[0][0]).toContain('date_from=2026-06-01')
    expect(vi.mocked(api.get).mock.calls[0][0]).toContain('date_to=2026-06-19')
    expect(vi.mocked(api.get).mock.calls[0][0]).toContain('limit=50')
    expect(vi.mocked(api.get).mock.calls[0][0]).toContain('offset=0')
    expect(store.stockTransactions).toHaveLength(INVENTORY_TX_PAGE_LIMIT)
    expect(store.stockTransactionsHasMore).toBe(true)

    vi.mocked(api.get).mockResolvedValueOnce([{ id: 'tail' } as never])
    await store.loadStockTransactions('branch-1', { offset: INVENTORY_TX_PAGE_LIMIT })

    expect(store.stockTransactions).toHaveLength(INVENTORY_TX_PAGE_LIMIT + 1)
    expect(store.stockTransactions.at(-1)?.id).toBe('tail')
    expect(store.stockTransactionsHasMore).toBe(false)

    vi.mocked(api.get).mockResolvedValueOnce([{ id: 'fresh' } as never])
    await store.loadStockTransactions('branch-1')

    expect(store.stockTransactions).toEqual([{ id: 'fresh' }])
  })

  it('captures catalog list failures without replacing rows with an empty state', async () => {
    const store = useWorkshopStore()
    store.branchMaterials = [{ id: 'existing' } as never]
    vi.mocked(api.get).mockRejectedValueOnce(
      new ApiError(500, { code: 'catalog_down', trace_id: 'tr-catalog' }),
    )

    await expect(store.loadBranchMaterials('branch-1')).rejects.toBeInstanceOf(ApiError)

    expect(store.branchMaterials).toEqual([{ id: 'existing' }])
    expect(store.catalogError).toBe('catalog_load_failed')
    expect(store.catalogTraceId).toBe('tr-catalog')
    expect(store.catalogLoading).toBe(false)
  })

  it('loads low-stock summaries across all requested branches without replacing stock items', async () => {
    const store = useWorkshopStore()
    store.stockItems = [{ id: 'current-stock' } as never]
    vi.mocked(api.get)
      .mockResolvedValueOnce([{ id: 'low-a' } as never])
      .mockResolvedValueOnce([{ id: 'low-b' } as never])

    await store.loadLowStock(['branch-a', 'branch-b', 'branch-a'])

    const paths = vi.mocked(api.get).mock.calls.map((call) => String(call[0]))
    expect(paths).toEqual([
      '/workshop/branches/branch-a/stock?low_stock=true',
      '/workshop/branches/branch-b/stock?low_stock=true',
    ])
    expect(store.lowStockItems).toEqual([{ id: 'low-a' }, { id: 'low-b' }])
    expect(store.stockItems).toEqual([{ id: 'current-stock' }])
  })

  it('ignores out-of-order user list responses', async () => {
    const store = useWorkshopStore()
    const first = deferred<Array<{ id: string }>>()
    vi.mocked(api.get)
      .mockReturnValueOnce(first.promise as never)
      .mockResolvedValueOnce([{ id: 'newer-user' }])

    const firstLoad = store.loadUsers()
    const secondLoad = store.loadUsers()
    await secondLoad
    expect(store.users).toEqual([{ id: 'newer-user' }])

    first.resolve([{ id: 'stale-user' }])
    await firstLoad
    expect(store.users).toEqual([{ id: 'newer-user' }])
    expect(store.loading).toBe(false)
  })

  it('loads owner user details without requesting owner sessions', async () => {
    const store = useWorkshopStore()
    const owner = {
      id: 'owner-1',
      workshop_id: 'workshop-1',
      login: 'owner',
      full_name: 'Workshop Owner',
      phone: '+998901234567',
      is_owner: true,
      home_branch_id: 'branch-1',
      status: 'active',
      password_reset_required: false,
      last_login_at: null,
      grants: [],
    }
    vi.mocked(api.get).mockResolvedValueOnce(owner)

    await store.loadUser('owner-1')

    expect(store.selectedUser).toEqual(owner)
    expect(store.sessions).toEqual([])
    expect(store.error).toBeNull()
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(api.get).toHaveBeenCalledWith('/workshop/users/owner-1', expect.anything())
  })

  it('lets loadUsers own loading after createUser while preserving the temp password', async () => {
    const store = useWorkshopStore()
    const staleLoad = deferred<Array<{ id: string }>>()
    vi.mocked(api.get)
      .mockReturnValueOnce(staleLoad.promise as never)
      .mockResolvedValueOnce([{ id: 'created-user' }])
    vi.mocked(api.post).mockResolvedValueOnce({
      user: { id: 'created-user' },
      temp_password: 'temp-123',
    })

    const staleLoadPromise = store.loadUsers()
    expect(store.loading).toBe(true)

    await store.createUser({ full_name: 'Created User' })

    expect(store.loading).toBe(false)
    expect(store.lastTempPassword).toBe('temp-123')
    expect(store.users).toEqual([{ id: 'created-user' }])

    staleLoad.resolve([{ id: 'stale-user' }])
    await staleLoadPromise
    expect(store.users).toEqual([{ id: 'created-user' }])
  })

  it('captures inventory load failures with trace ids', async () => {
    const store = useWorkshopStore()
    vi.mocked(api.get)
      .mockRejectedValueOnce(new ApiError(500, { trace_id: 'tr-inventory' }))
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])

    await store.loadInventory('branch-1')

    expect(store.inventoryError).toBe('inventory_load_failed')
    expect(store.inventoryTraceId).toBe('tr-inventory')
    expect(store.inventoryLoading).toBe(false)
  })

  it('loads branch pricing only for owners', async () => {
    const auth = useAuthStore()
    const store = useWorkshopStore()
    auth.me = { is_owner: true } as never
    vi.mocked(api.get).mockResolvedValueOnce({ id: 'branch-1' }).mockResolvedValueOnce({
      cutting_price_per_meter_tiyin: 100,
    })

    await store.loadBranch('branch-1')

    expect(vi.mocked(api.get).mock.calls.map((call) => String(call[0]))).toEqual([
      '/workshop/branches/branch-1',
      '/workshop/branches/branch-1/pricing',
    ])

    vi.mocked(api.get).mockReset()
    auth.me = { is_owner: false } as never
    vi.mocked(api.get).mockResolvedValueOnce({ id: 'branch-2' })

    await store.loadBranch('branch-2')

    expect(vi.mocked(api.get).mock.calls.map((call) => String(call[0]))).toEqual([
      '/workshop/branches/branch-2',
    ])
  })

  it('prepends stock-in transactions and reloads stock', async () => {
    const store = useWorkshopStore()
    store.stockTransactions = [{ id: 'existing-tx' } as never]
    vi.mocked(api.post).mockResolvedValueOnce({ id: 'new-tx' })
    vi.mocked(api.get).mockResolvedValueOnce([{ id: 'stock-row' }])

    await store.recordStockIn('branch-1', { quantity: 5 })

    expect(store.stockTransactions).toEqual([{ id: 'new-tx' }, { id: 'existing-tx' }])
    expect(store.stockItems).toEqual([{ id: 'stock-row' }])
    expect(vi.mocked(api.get).mock.calls[0][0]).toBe('/workshop/branches/branch-1/stock')
  })
})
