import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import { useCuttingStore, type ClientCatalogMaterialOption } from '@/shared/stores/cutting'

vi.mock('@/shared/api/client', () => ({
  api: { get: vi.fn() },
  apiTraceId: () => null,
  captureApiError: (_error: unknown, fallback: string) => ({ code: fallback, traceId: null }),
  withQuery: (path: string, query: Record<string, unknown>) =>
    `${path}?${Object.entries(query)
      .filter(([, value]) => value != null)
      .map(([key, value]) => `${key}=${String(value)}`)
      .join('&')}`,
}))

const list = (id: string) => [{ id }] as unknown as ClientCatalogMaterialOption[]

describe('cutting store loadMaterials cache (CB-40)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
  })

  it('reuses a recent (kind, branch) result instead of refetching an identical payload', async () => {
    const store = useCuttingStore()
    vi.mocked(api.get).mockResolvedValue(list('m1'))

    await store.loadMaterials({ kind: 'panel', branchId: 'b1' })
    await store.loadMaterials({ kind: 'panel', branchId: 'b1' })

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(store.panelOptions).toEqual([{ id: 'm1' }])
  })

  it('refetches when the branch changes, when the kind differs, and on force', async () => {
    const store = useCuttingStore()
    vi.mocked(api.get).mockResolvedValue(list('m1'))

    await store.loadMaterials({ kind: 'panel', branchId: 'b1' })
    await store.loadMaterials({ kind: 'panel', branchId: 'b2' }) // different branch
    await store.loadMaterials({ kind: 'edge', branchId: 'b1' }) // different kind
    await store.loadMaterials({ kind: 'panel', branchId: 'b2', force: true }) // force

    expect(api.get).toHaveBeenCalledTimes(4)
  })
})
