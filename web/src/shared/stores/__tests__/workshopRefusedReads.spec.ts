import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { ApiError, api } from '@/shared/api/client'
import { useOrdersStore } from '@/shared/stores/orders'
import { useWorkshopStore, type BranchMaterial, type StockItem } from '@/shared/stores/workshop'

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
    api: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      patch: vi.fn(),
      del: vi.fn(),
      blob: vi.fn(),
    },
    apiErrorCode: () => null,
    apiTraceId: () => null,
    captureApiError: (_error: unknown, fallback: string) => ({ code: fallback, traceId: null }),
    isPermissionDenied: (error: unknown) => error instanceof ApiError && error.status === 403,
    withQuery: (path: string) => path,
  }
})

function stockRow(id: string): StockItem {
  return {
    id,
    branch_id: 'branch-1',
    branch_material_id: `bm-${id}`,
    // Deliberately not cast: `StockItem.material` is a BranchMaterial now, and a
    // real minimal object is what makes the fixture fail if the shape drifts.
    material: {
      id: `bm-${id}`,
      branch_id: 'branch-1',
      dekor_id: `dekor-${id}`,
      dekor: {} as BranchMaterial['dekor'],
      qalinlik_mm: '18',
      uzunlik_mm: 2800,
      eni_mm: 2070,
      kromka_eni_mm: null,
      price_tiyin: 0,
      price_unset: true,
      min_stock: 2,
      status: 'active',
      label: `LDSP Egger ${id}`,
      created_at: '2026-07-26T09:00:00Z',
      updated_at: '2026-07-26T09:00:00Z',
    },
    tur: 'ldsp',
    stock_unit: 'sheet',
    display_unit: 'sheet',
    on_hand: 4,
    min_stock: 2,
    is_low_stock: false,
    updated_at: '2026-07-26T09:00:00Z',
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

// QAD-172: a grant revoked mid-session used to leave the rows it unlocked on
// screen with an error line stacked on top. The rows go when the server refuses
// them; a transport failure is a different thing and keeps the last good data.
describe('reads the server refuses', () => {
  it('drops the stock rows a refused reload was meant to replace', async () => {
    const workshop = useWorkshopStore()
    vi.mocked(api.get).mockResolvedValueOnce([stockRow('stock-1')])
    await workshop.loadStock('branch-1')
    expect(workshop.stockItems).toHaveLength(1)

    vi.mocked(api.get).mockRejectedValueOnce(new ApiError(403, { code: 'forbidden' }))
    await expect(workshop.loadStock('branch-1')).rejects.toMatchObject({ status: 403 })

    expect(workshop.stockItems).toEqual([])
  })

  it('keeps the stock rows when the reload merely fails to reach the server', async () => {
    const workshop = useWorkshopStore()
    vi.mocked(api.get).mockResolvedValueOnce([stockRow('stock-1')])
    await workshop.loadStock('branch-1')

    vi.mocked(api.get).mockRejectedValueOnce(new ApiError(500, { code: 'internal_error' }))
    await expect(workshop.loadStock('branch-1')).rejects.toMatchObject({ status: 500 })

    expect(workshop.stockItems).toHaveLength(1)
  })

  it('drops the low-stock, transaction and supplier lists on a refusal', async () => {
    const workshop = useWorkshopStore()
    vi.mocked(api.get).mockResolvedValueOnce([stockRow('stock-1')])
    await workshop.loadLowStock(['branch-1'])
    vi.mocked(api.get).mockResolvedValueOnce([{ id: 'tx-1' }])
    await workshop.loadStockTransactions('branch-1')
    vi.mocked(api.get).mockResolvedValueOnce([{ id: 'supplier-1' }])
    await workshop.loadSuppliers('branch-1')
    expect(workshop.stockTransactions).toHaveLength(1)

    vi.mocked(api.get).mockRejectedValue(new ApiError(403, { code: 'forbidden' }))
    await expect(workshop.loadLowStock(['branch-1'])).rejects.toBeInstanceOf(ApiError)
    await expect(workshop.loadStockTransactions('branch-1')).rejects.toBeInstanceOf(ApiError)
    await expect(workshop.loadSuppliers('branch-1')).rejects.toBeInstanceOf(ApiError)

    expect(workshop.lowStockItems).toEqual([])
    expect(workshop.stockTransactions).toEqual([])
    expect(workshop.stockTransactionsHasMore).toBe(false)
    expect(workshop.suppliers).toEqual([])
  })

  it('drops the order board rows on a refusal but keeps them on a server fault', async () => {
    const orders = useOrdersStore()
    vi.mocked(api.get).mockResolvedValueOnce([{ id: 'order-1', status: 'new' }])
    await orders.loadWorkshopOrders()
    expect(orders.workshopOrders).toHaveLength(1)

    vi.mocked(api.get).mockRejectedValueOnce(new ApiError(500, { code: 'internal_error' }))
    await orders.loadWorkshopOrders()
    expect(orders.workshopOrders).toHaveLength(1)

    vi.mocked(api.get).mockRejectedValueOnce(new ApiError(403, { code: 'forbidden' }))
    await orders.loadWorkshopOrders()
    expect(orders.workshopOrders).toEqual([])
  })
})
