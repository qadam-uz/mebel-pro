import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import { useFinanceStore } from '@/shared/stores/finance'

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
    api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
    withQuery: (path: string) => path,
  }
})

describe('finance store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
    vi.mocked(api.patch).mockReset()
  })

  it('captures backend action code and trace for failed ledger mutations', async () => {
    const store = useFinanceStore()
    vi.mocked(api.post).mockRejectedValueOnce(
      new ApiError(500, { code: 'ledger_date_in_future', trace_id: 'tr-fin-1' }),
    )

    await expect(store.createExpense({ amount_tiyin: 10_000 })).rejects.toBeInstanceOf(ApiError)

    expect(store.actionError).toBe('ledger_date_in_future')
    expect(store.actionTraceId).toBe('tr-fin-1')
    expect(store.error).toBeNull()
  })

  it('captures loader error and trace while clearing loading', async () => {
    const store = useFinanceStore()
    vi.mocked(api.get).mockRejectedValueOnce(
      new ApiError(500, { code: 'boom', trace_id: 'tr-fin-load' }),
    )

    await store.loadSummary({ date_from: '2026-06-01', date_to: '2026-06-19' })

    expect(store.error).toBe('finance_summary_failed')
    expect(store.traceId).toBe('tr-fin-load')
    expect(store.loading).toBe(false)
  })

  it('prepends newly recorded expenses', async () => {
    const store = useFinanceStore()
    store.expenses = [{ id: 'old-expense', amount_tiyin: 10_000 } as never]
    vi.mocked(api.post).mockResolvedValueOnce({ id: 'new-expense', amount_tiyin: 20_000 })

    await store.createExpense({ amount_tiyin: 20_000 })

    expect(store.expenses.map((row) => row.id)).toEqual(['new-expense', 'old-expense'])
  })

  it('replaces voided rows in place without reordering', async () => {
    const store = useFinanceStore()
    store.expenses = [
      { id: 'exp-1', status: 'recorded' },
      { id: 'exp-2', status: 'recorded' },
    ] as never
    vi.mocked(api.post).mockResolvedValueOnce({ id: 'exp-1', status: 'voided' })

    await store.voidExpense('exp-1', 'duplicate')

    expect(store.expenses).toEqual([
      expect.objectContaining({ id: 'exp-1', status: 'voided' }),
      expect.objectContaining({ id: 'exp-2', status: 'recorded' }),
    ])
  })
})
