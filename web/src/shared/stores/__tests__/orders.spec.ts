import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { ApiError, api } from '@/shared/api/client'
import { useOrdersStore, type OrderQuote } from '@/shared/stores/orders'

vi.mock('@/shared/app/authInit', () => ({
  authInit: () => ({ accessToken: 'access-token' }),
}))

vi.mock('@/shared/app/downloadBlob', () => ({
  openBlobInNewTab: vi.fn(),
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

  function bodyObject(error: unknown) {
    return error instanceof ApiError && typeof error.body === 'object' && error.body !== null
      ? (error.body as Record<string, unknown>)
      : null
  }

  return {
    ApiError,
    api: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      patch: vi.fn(),
      del: vi.fn(),
      blob: vi.fn(),
    },
    apiErrorCode: (error: unknown) => {
      const body = bodyObject(error)
      return typeof body?.code === 'string' ? body.code : null
    },
    apiTraceId: (error: unknown) => {
      const body = bodyObject(error)
      return typeof body?.trace_id === 'string' ? body.trace_id : null
    },
    captureApiError: vi.fn((_error: unknown, fallback: string) => ({
      code: fallback,
      traceId: null,
    })),
    isPermissionDenied: (error: unknown) => error instanceof ApiError && error.status === 403,
    withQuery: (path: string) => path,
  }
})

function quote(branchId: string): OrderQuote {
  return {
    draft_id: 'draft-1',
    branch_id: branchId,
    branch_name: `Branch ${branchId}`,
    branch_address: 'Tashkent',
    branch_phone: '+998901234567',
    subtotal_cutting_tiyin: 1,
    subtotal_materials_tiyin: 2,
    subtotal_edge_banding_tiyin: 3,
    total_tiyin: 6,
    panels_used: 1,
    cutting_rate_tiyin: 1,
    material_lines: [],
    edge_lines: [],
  }
}

describe('orders store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
  })

  it('quotes more than 50 branches in backend-sized batches', async () => {
    const branchIds = Array.from({ length: 51 }, (_, index) => `branch-${index}`)
    vi.mocked(api.post).mockImplementation(async (_path, payload) => {
      const ids = (payload as { branch_ids: string[] }).branch_ids
      return {
        quotes: { [ids[0]]: quote(ids[0]) },
        errors: Object.fromEntries(
          ids.slice(1).map((branchId) => [branchId, 'missing_cutting_rate']),
        ),
      }
    })

    const result = await useOrdersStore().quoteBranches('draft-1', branchIds)

    expect(api.post).toHaveBeenCalledTimes(2)
    expect(vi.mocked(api.post).mock.calls[0][1]).toMatchObject({
      branch_ids: branchIds.slice(0, 50),
    })
    expect(vi.mocked(api.post).mock.calls[1][1]).toMatchObject({
      branch_ids: ['branch-50'],
    })
    expect(result.requestFailed).toBe(false)
    expect(result.quotes['branch-0']).toMatchObject({ branch_id: 'branch-0' })
    expect(result.quotes['branch-50']).toMatchObject({ branch_id: 'branch-50' })
    expect(result.errors['branch-1']).toBe('missing_cutting_rate')
  })

  it('keeps all-branch quote errors as per-branch failures', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(
      new ApiError(409, {
        code: 'order_quote_unavailable',
        trace_id: 'trace-409',
        quotes: {},
        errors: { 'branch-1': 'missing_cutting_rate' },
      }),
    )

    const result = await useOrdersStore().quoteBranches('draft-1', ['branch-1'])

    expect(result).toMatchObject({
      quotes: {},
      errors: { 'branch-1': 'missing_cutting_rate' },
      firstErrorTraceId: 'trace-409',
      requestFailed: false,
    })
  })

  it('captures a single-branch quote error for checkout copy', async () => {
    vi.mocked(api.get).mockRejectedValueOnce(
      new ApiError(400, { code: 'missing_cutting_rate', trace_id: 'trace-rate' }),
    )
    const store = useOrdersStore()

    await expect(store.quoteForDraft('draft-1', 'branch-1')).rejects.toBeInstanceOf(ApiError)

    expect(store.error).toBe('order_quote_failed')
  })

  it('quotes a workshop branch against the workshop mirror endpoint', async () => {
    vi.mocked(api.get).mockResolvedValueOnce(quote('branch-1'))

    const result = await useOrdersStore().quoteWorkshopBranch('draft-1', 'branch-1')

    expect(api.get).toHaveBeenCalledWith('/workshop/orders/quote', expect.anything())
    expect(result).toMatchObject({ branch_id: 'branch-1' })
  })

  it('creates a workshop walk-in order and joins the workshop list', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ id: 'order-1', status: 'confirmed' })
    const store = useOrdersStore()

    const order = await store.createWorkshopOrder({
      draft_id: 'draft-1',
      branch_id: 'branch-1',
      contact_name: 'Ali Valiyev',
      contact_phone: '+998901234567',
      note_client: 'walk-in',
    })

    expect(api.post).toHaveBeenCalledWith(
      '/workshop/orders',
      {
        draft_id: 'draft-1',
        branch_id: 'branch-1',
        contact_name: 'Ali Valiyev',
        contact_phone: '+998901234567',
        note_client: 'walk-in',
      },
      expect.anything(),
    )
    expect(order).toMatchObject({ id: 'order-1', status: 'confirmed' })
    expect(store.currentOrder).toMatchObject({ id: 'order-1' })
    expect(store.workshopOrders).toHaveLength(1)
    expect(store.workshopOrders[0]).toMatchObject({ id: 'order-1' })
  })

  // QAD-156: the sidebar badge is ambient decoration. A failing count must leave
  // no error state and no stale number behind — the badge simply stops rendering.
  it('keeps the new-order count silent when it fails to load', async () => {
    const store = useOrdersStore()
    vi.mocked(api.get).mockResolvedValueOnce({ count: 4 })
    await store.loadNewOrderCount('branch-1')
    expect(store.newOrderCount).toBe(4)

    vi.mocked(api.get).mockRejectedValueOnce(new ApiError(500, { code: 'boom' }))
    await store.refreshNewOrderCount()

    expect(store.newOrderCount).toBe(0)
    expect(store.error).toBeNull()
    expect(store.actionError).toBeNull()
  })
})
