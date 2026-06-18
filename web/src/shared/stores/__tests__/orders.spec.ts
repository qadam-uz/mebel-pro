import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import { useOrdersStore, type OrderDetail } from '@/shared/stores/orders'

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
    apiTraceId: () => null,
    apiErrorCode: (error: unknown) => {
      if (error instanceof ApiError && typeof error.body === 'object' && error.body) {
        const code = (error.body as { code?: unknown }).code
        return typeof code === 'string' ? code : null
      }
      return null
    },
    api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
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
})
