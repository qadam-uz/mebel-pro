import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { api, withQuery } from '@/shared/api/client'
import { openBlobInNewTab } from '@/shared/app/downloadBlob'
import {
  partFitError,
  useCuttingStore,
  type ClientCatalogMaterialOption,
  type CuttingDraft,
  type CuttingResult,
} from '@/shared/stores/cutting'

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
    captureApiError: vi.fn((_error: unknown, fallback: string) => ({
      code: fallback,
      traceId: null,
    })),
    // Path-only, so the scope suite can assert prefixes cleanly. It is a spy so
    // the params object stays inspectable — see the catalog-query test below.
    withQuery: vi.fn((path: string) => path),
  }
})

function draft(id = 'draft-1'): CuttingDraft {
  return {
    id,
    client_id: 'client-1',
    name: null,
    preferred_branch_id: null,
    kerf_mm: 4,
    edge_trim_mm: 5,
    parts_snapshot: [],
    own_panel_counts: {},
    own_edge_material_ids: [],
    chosen_result_id: null,
    revision_of_order_id: null,
    created_at: '2026-07-08T00:00:00Z',
    updated_at: '2026-07-08T00:00:00Z',
    results: [],
  }
}

const WALK_IN = { id: 'client-9', name: 'Ali Valiyev', phone: '+998901112233' }

const basePanel: Pick<ClientCatalogMaterialOption, 'uzunlik_mm' | 'eni_mm' | 'tolali'> = {
  uzunlik_mm: 600,
  eni_mm: 400,
  tolali: true,
}

// Drives every store action that talks to the API and returns the request
// paths per HTTP verb — the scope tests assert the '/client' vs '/workshop'
// prefix over the full surface so a new hard-coded path can't sneak in.
async function exerciseEveryPath(store: ReturnType<typeof useCuttingStore>) {
  vi.mocked(api.get).mockResolvedValue([])
  vi.mocked(api.post).mockResolvedValue(draft())
  vi.mocked(api.patch).mockResolvedValue(draft())
  vi.mocked(api.del).mockResolvedValue(undefined)

  await store.loadDrafts()
  await store.createDraft({ branchId: 'branch-1' })
  await store.loadDraft('draft-1')
  await store.updateDraft('draft-1', { parts_snapshot: [] })
  await store.deleteDraft('draft-1')
  await store.optimizeDraft('draft-1')
  await store.chooseResult('draft-1', 'result-1')
  await store.loadMaterials({ tape: false, branchId: 'branch-1', force: true })
  await store.openClientPdf('result-1')

  return {
    get: vi.mocked(api.get).mock.calls.map((call) => call[0]),
    post: vi.mocked(api.post).mock.calls.map((call) => call[0]),
    patch: vi.mocked(api.patch).mock.calls.map((call) => call[0]),
    del: vi.mocked(api.del).mock.calls.map((call) => call[0]),
    blob: vi.mocked(openBlobInNewTab).mock.calls.map((call) => call[0]),
  }
}

describe('cutting store scope', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
    vi.mocked(api.patch).mockReset()
    vi.mocked(api.del).mockReset()
    vi.mocked(openBlobInNewTab).mockReset()
  })

  it('routes every action through /client/* by default', async () => {
    const paths = await exerciseEveryPath(useCuttingStore())

    expect(paths.get).toEqual([
      '/client/cutting-drafts',
      '/client/cutting-drafts/draft-1',
      '/client/catalog/materials',
    ])
    expect(paths.post).toEqual([
      '/client/cutting-drafts',
      '/client/cutting-drafts/draft-1/optimize',
      '/client/cutting-drafts/draft-1/chosen-result',
    ])
    expect(paths.patch).toEqual(['/client/cutting-drafts/draft-1'])
    expect(paths.del).toEqual(['/client/cutting-drafts/draft-1'])
    expect(paths.blob).toEqual(['/client/cutting-results/result-1/pdf'])
    // Client scope never sends a create body, even if a branch id is passed.
    expect(vi.mocked(api.post).mock.calls[0][1]).toBeUndefined()
  })

  it('commits MAP layout imports through the client endpoint', async () => {
    const store = useCuttingStore()
    vi.mocked(api.post).mockResolvedValue(draft('draft-map'))

    const result = await store.commitMapImport({
      preferred_branch_id: 'branch-1',
      parts: [],
      panel_picks: { m1: 'panel-1' },
      map_layout: { sheets: [], part_rows: [], description: '', customer_name: '', order_type: '' },
    })

    expect(result.id).toBe('draft-map')
    expect(vi.mocked(api.post).mock.calls[0][0]).toBe('/client/cutting/import/map/commit')
  })

  it('commits MAP layout imports for the walk-in client through the workshop endpoint', async () => {
    const store = useCuttingStore()
    store.configureScope('workshop')
    store.setWalkInClient(WALK_IN)
    vi.mocked(api.post).mockResolvedValue(draft('draft-map'))

    await store.commitMapImport({
      preferred_branch_id: 'branch-1',
      parts: [],
      panel_picks: { m1: 'panel-1' },
      map_layout: { sheets: [], part_rows: [], description: '', customer_name: '', order_type: '' },
    })

    expect(api.post).toHaveBeenCalledWith(
      '/workshop/cutting/import/map/commit',
      expect.objectContaining({ client_id: 'client-9', branch_id: 'branch-1' }),
      expect.anything(),
    )
  })

  it('routes every action through /workshop/* after configureScope', async () => {
    const store = useCuttingStore()
    store.configureScope('workshop')
    store.setWalkInClient(WALK_IN)
    const paths = await exerciseEveryPath(store)

    expect(paths.get).toEqual([
      '/workshop/cutting-drafts',
      '/workshop/cutting-drafts/draft-1',
      '/workshop/catalog/materials',
    ])
    expect(paths.post).toEqual([
      '/workshop/cutting-drafts',
      '/workshop/cutting-drafts/draft-1/optimize',
      '/workshop/cutting-drafts/draft-1/chosen-result',
    ])
    expect(paths.patch).toEqual(['/workshop/cutting-drafts/draft-1'])
    expect(paths.del).toEqual(['/workshop/cutting-drafts/draft-1'])
    expect(paths.blob).toEqual(['/workshop/cutting-results/result-1/pdf'])
  })

  it('creates a client draft with no payload', async () => {
    vi.mocked(api.post).mockResolvedValue(draft())

    await useCuttingStore().createDraft()

    expect(api.post).toHaveBeenCalledWith('/client/cutting-drafts', undefined, expect.anything())
  })

  it('creates a workshop draft on behalf of the walk-in client at the fixed branch', async () => {
    vi.mocked(api.post).mockResolvedValue(draft())
    const store = useCuttingStore()
    store.configureScope('workshop')
    store.setWalkInClient(WALK_IN)

    await store.createDraft({ branchId: 'branch-1' })

    expect(api.post).toHaveBeenCalledWith(
      '/workshop/cutting-drafts',
      { client_id: 'client-9', branch_id: 'branch-1' },
      expect.anything(),
    )
  })

  it('rejects workshop draft creation without a resolved walk-in client', async () => {
    const store = useCuttingStore()
    store.configureScope('workshop')

    await expect(store.createDraft({ branchId: 'branch-1' })).rejects.toThrow(/walk-in client/)

    expect(api.post).not.toHaveBeenCalled()
    expect(store.saving).toBe(false)
  })

  it('rejects workshop draft creation without a branch', async () => {
    const store = useCuttingStore()
    store.configureScope('workshop')
    store.setWalkInClient(WALK_IN)

    await expect(store.createDraft()).rejects.toThrow(/branch/)

    expect(api.post).not.toHaveBeenCalled()
    expect(store.saving).toBe(false)
  })

  it('keeps candidate results returned by a geometry-neutral parts PATCH', async () => {
    const result = {
      id: 'result-imported',
      source: 'imported_map',
      status: 'candidate',
      parts_snapshot: [],
      own_panel_counts: {},
      own_edge_material_ids: [],
      panels: [],
    } as unknown as CuttingResult
    const updated = draft('draft-1')
    updated.chosen_result_id = result.id
    updated.results = [result]
    vi.mocked(api.patch).mockResolvedValue(updated)

    const stored = await useCuttingStore().updateDraft('draft-1', { parts_snapshot: [] })

    expect(stored.results).toEqual([result])
    expect(useCuttingStore().currentDraft?.results).toEqual([result])
    expect(useCuttingStore().currentDraft?.chosen_result_id).toBe(result.id)
  })

  it('loads branch options from the client surface in client scope', async () => {
    vi.mocked(api.get).mockResolvedValue([])

    await useCuttingStore().loadBranchOptions()

    expect(api.get).toHaveBeenCalledWith('/client/branch-options', expect.anything())
  })

  it('makes loadBranchOptions a no-op in workshop scope (no /workshop mirror exists)', async () => {
    const store = useCuttingStore()
    store.configureScope('workshop')

    await store.loadBranchOptions()
    await store.loadBranchOptions('search-term')
    await store.loadBranchOptions(undefined, { force: true })

    expect(api.get).not.toHaveBeenCalled()
  })

  it('reset clears the walk-in client but keeps the bootstrap scope', () => {
    const store = useCuttingStore()
    store.configureScope('workshop')
    store.setWalkInClient(WALK_IN)

    store.reset()

    expect(store.walkInClient).toBeNull()
    expect(store.scope).toBe('workshop')
  })
})

describe('partFitError', () => {
  it.each([
    [true, true, 'impossible_grain'],
    [true, false, null],
    [false, true, 'impossible_grain'],
    [false, false, null],
  ] as const)(
    'uses follow_grain as the rotation lock for tolali=%s and follow_grain=%s',
    (materialGrain, followGrain, expected) => {
      const panel = { ...basePanel, tolali: materialGrain }

      expect(partFitError(360, 500, panel, followGrain, 10)).toBe(expected)
    },
  )

  // Two branches with different edge trims (kerf/trim are per-branch settings,
  // not a shared constant — cutting.md) must reach different verdicts for the
  // identical part on the identical panel.
  it('gives different verdicts for the same part at different branch trims', () => {
    expect(partFitError(500, 300, basePanel, false, 5)).toBeNull()
    expect(partFitError(500, 300, basePanel, false, 90)).toBe('part_too_large')
  })
})

// The scope suite mocks withQuery down to the path, which makes the query string
// invisible to it. `branch_id` is REQUIRED on both catalog endpoints now, so the
// "a branch is chosen before materials" invariant needs its own lock.
describe('loadMaterials query', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset().mockResolvedValue([])
    vi.mocked(withQuery).mockClear()
  })

  it('always sends branch_id, and sends tape=false rather than dropping it', async () => {
    await useCuttingStore().loadMaterials({ tape: false, branchId: 'branch-7', force: true })

    const call = vi.mocked(withQuery).mock.calls.at(-1)
    expect(call?.[0]).toBe('/client/catalog/materials')
    expect(call?.[1]).toMatchObject({ tape: false, branch_id: 'branch-7' })
    // Both replaced by `tape`/structural branch scoping — never send them again.
    expect(call?.[1]).not.toHaveProperty('kind')
    expect(call?.[1]).not.toHaveProperty('carried_only')
  })

  it('asks for tapes with tape=true', async () => {
    await useCuttingStore().loadMaterials({ tape: true, branchId: 'branch-7', force: true })

    expect(vi.mocked(withQuery).mock.calls.at(-1)?.[1]).toMatchObject({
      tape: true,
      branch_id: 'branch-7',
    })
  })

  it('caches per (tape, branch) so a branch flip refetches', async () => {
    const store = useCuttingStore()
    await store.loadMaterials({ tape: false, branchId: 'branch-7' })
    await store.loadMaterials({ tape: false, branchId: 'branch-7' })
    expect(vi.mocked(api.get)).toHaveBeenCalledTimes(1)

    await store.loadMaterials({ tape: false, branchId: 'branch-8' })
    expect(vi.mocked(api.get)).toHaveBeenCalledTimes(2)
  })
})
