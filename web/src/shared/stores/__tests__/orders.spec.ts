import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import { ORDERS_PAGE_LIMIT } from '@/shared/app/constants'
import { useOrdersStore, type OrderDetail, type OrderSummary } from '@/shared/stores/orders'

vi.mock('@/shared/api/client', () => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      readonly body: unknown,
    ) {
      super(`API ${status}`)
    }
  }
  return {
    ApiError,
    apiTraceId: (error: unknown) =>
      error instanceof ApiError && typeof error.body === 'object' && error.body
        ? ((error.body as { trace_id?: unknown }).trace_id ?? null)
        : null,
    apiErrorCode: (error: unknown) => {
      if (error instanceof ApiError && typeof error.body === 'object' && error.body) {
        const code = (error.body as { code?: unknown }).code
        return typeof code === 'string' ? code : null
      }
      return null
    },
    captureApiError: (error: unknown, fallback: string) => {
      const traceId =
        error instanceof ApiError && typeof error.body === 'object' && error.body
          ? ((error.body as { trace_id?: unknown }).trace_id ?? null)
          : null
      if (error instanceof ApiError) {
        if (error.status === 403) return { code: 'permission_denied', traceId }
        const code = (error.body as { code?: unknown })?.code
        return { code: typeof code === 'string' ? code : fallback, traceId }
      }
      return { code: fallback, traceId }
    },
    api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
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

const orderAt = (version: number) => ({ id: 'o1', version }) as unknown as OrderDetail

describe('orders store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
  })

  it('refetches the order on a 409 version conflict so a retry uses the fresh version', async () => {
    const store = useOrdersStore()
    // the cancel POST conflicts: the cached version (3) is stale
    vi.mocked(api.post).mockRejectedValueOnce(
      new ApiError(409, { code: 'order_version_conflict', current_version: 5 }),
    )
    // the conflict triggers a refetch which returns the server's current version
    vi.mocked(api.get).mockResolvedValueOnce(orderAt(5))

    await expect(store.cancelClientOrder('o1', 3, 'changed my mind')).rejects.toBeInstanceOf(
      ApiError,
    )

    expect(api.get).toHaveBeenCalledWith('/client/orders/o1', expect.anything())
    expect(store.currentOrder?.version).toBe(5)
    expect(store.error).toBe('order_version_conflict')
  })

  it('does not refetch on a non-conflict error', async () => {
    const store = useOrdersStore()
    vi.mocked(api.post).mockRejectedValueOnce(new ApiError(403, { code: 'permission_denied' }))

    await expect(store.cancelClientOrder('o1', 3, 'reason')).rejects.toBeInstanceOf(ApiError)

    expect(api.get).not.toHaveBeenCalled()
    expect(store.error).toBe('permission_denied')
  })

  it('paginates orders: offset 0 replaces, offset>0 appends, hasMore from a full page (CB-38)', async () => {
    const store = useOrdersStore()
    const fullPage = Array.from(
      { length: ORDERS_PAGE_LIMIT },
      (_, i) => ({ id: `o${i}` }) as OrderSummary,
    )
    vi.mocked(api.get).mockResolvedValueOnce(fullPage)
    await store.loadClientOrders({})
    expect(store.clientOrders).toHaveLength(ORDERS_PAGE_LIMIT)
    expect(store.ordersHasMore).toBe(true)

    // a short next page appends and clears hasMore
    vi.mocked(api.get).mockResolvedValueOnce([{ id: 'tail' } as OrderSummary])
    await store.loadClientOrders({ offset: ORDERS_PAGE_LIMIT })
    expect(store.clientOrders).toHaveLength(ORDERS_PAGE_LIMIT + 1)
    expect(store.clientOrders.at(-1)?.id).toBe('tail')
    expect(store.ordersHasMore).toBe(false)

    // offset 0 again replaces (not append)
    vi.mocked(api.get).mockResolvedValueOnce([{ id: 'only' } as OrderSummary])
    await store.loadClientOrders({})
    expect(store.clientOrders).toHaveLength(1)
  })

  it('maps each branch to its own quote or error from the batch endpoint (CB-12/20)', async () => {
    const store = useOrdersStore()
    // One batch request: A quotes, B is closed, C can't fulfil — each branch keeps
    // its OWN backend code (CB-19 needs the real code, not a shared/blanked one).
    vi.mocked(api.post).mockResolvedValueOnce({
      quotes: { A: { branch_id: 'A', branch_name: 'Branch A' } },
      errors: { B: 'permission_denied', C: 'materials_unavailable' },
    } as never)

    const { quotes, errors, firstErrorTraceId } = await store.quoteBranches('draft-1', [
      'A',
      'B',
      'C',
    ])

    expect(api.post).toHaveBeenCalledWith(
      '/client/orders/quote/batch',
      { draft_id: 'draft-1', branch_ids: ['A', 'B', 'C'] },
      expect.anything(),
    )
    expect(quotes.A).toMatchObject({ branch_id: 'A' })
    expect(quotes.B).toBeUndefined()
    expect(errors.B).toBe('permission_denied')
    expect(errors.C).toBe('materials_unavailable')
    expect(firstErrorTraceId).toBeNull()
  })

  it('marks every branch failed with the trace when the whole batch request fails (CB-12)', async () => {
    const store = useOrdersStore()
    vi.mocked(api.post).mockRejectedValueOnce(new ApiError(500, { trace_id: 'tr-batch' }))

    const { quotes, errors, firstErrorTraceId } = await store.quoteBranches('draft-1', ['A', 'B'])

    expect(Object.keys(quotes)).toHaveLength(0)
    expect(errors.A).toBeNull()
    expect(errors.B).toBeNull()
    expect(firstErrorTraceId).toBe('tr-batch')
  })
})
