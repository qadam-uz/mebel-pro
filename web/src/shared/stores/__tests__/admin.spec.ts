import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import {
  useAdminStore,
  type ActionLog,
  type ErrorRecord,
  type ErrorRecordStatus,
  type JobRun,
  type JobRunStatus,
  type Material,
  type MaterialWriteRequest,
  type StatusChangeLog,
  type WorkshopListItem,
} from '@/shared/stores/admin'

function makeRun(id: string, status: JobRunStatus): JobRun {
  return {
    id,
    job_definition_id: 'd1',
    job_name: 'cleanup-expired-sessions',
    status,
    started_at: '2026-06-19T10:00:00Z',
    finished_at: null,
    brief_log: null,
    error_code: null,
    error_message: null,
    trace_id: null,
  }
}

function makeListWorkshop(): WorkshopListItem {
  return {
    id: 'w1',
    code: 'c1',
    name: 'WS',
    phone: '+998900000000',
    address: null,
    status: 'active',
    owner_user_id: 'u1',
    created_at: '2026-06-19T10:00:00Z',
    owner_login: 'owner-1',
    branch_count: 3,
  }
}

function makeMaterial(id: string, branchUsageCount: number, name = 'Panel'): Material {
  return {
    id,
    kind: 'panel',
    manufacturer_id: 'mf1',
    manufacturer_name: 'Maker',
    type: 'dsp',
    name,
    thickness_mm: '18',
    color: 'White',
    decor_code: null,
    panel_length_mm: 2800,
    panel_width_mm: 2070,
    grain_direction: true,
    image_file_id: null,
    status: 'active',
    branch_usage_count: branchUsageCount,
    created_at: '2026-06-19T10:00:00Z',
    updated_at: '2026-06-19T10:00:00Z',
  }
}

function makeError(id: string, status: ErrorRecordStatus): ErrorRecord {
  return {
    id,
    code: 'x.error',
    module: 'tests',
    status,
    count_24h: 1,
    count_7d: 1,
    last_occurred_at: '2026-06-19T10:00:00Z',
    preview_message: 'boom',
    resolved_by_user_id: status === 'resolved' ? 'u1' : null,
    resolved_at: status === 'resolved' ? '2026-06-19T10:00:00Z' : null,
    created_at: '2026-06-19T10:00:00Z',
    updated_at: '2026-06-19T10:00:00Z',
  }
}

function makeAction(id: string): ActionLog {
  return {
    id,
    actor_type: 'platform_user',
    actor_user_id: 'u1',
    actor_client_id: null,
    workshop_id: 'w1',
    branch_id: null,
    action: 'platform.workshop.block',
    entity_type: 'workshop',
    entity_id: 'entity-1',
    summary: 'Blocked',
    details: null,
    trace_id: 'trace-1',
    created_at: '2026-06-19T10:00:00Z',
  }
}

function makeStatus(id: string): StatusChangeLog {
  return {
    id,
    entity_type: 'workshop',
    entity_id: 'entity-1',
    workshop_id: 'w1',
    branch_id: null,
    from_status: 'active',
    to_status: 'blocked',
    actor_type: 'platform_user',
    actor_user_id: 'u1',
    actor_client_id: null,
    reason: 'reason',
    action_log_id: null,
    changed_at: '2026-06-19T10:00:00Z',
  }
}

// AB-01 / AB-53 regression: every admin loader must run its error through
// captureApiError so a 403 surfaces as `permission_denied` (rendered as the
// dedicated access-revoked state) rather than being masked as a generic outage.
describe('admin store loaders surface permission_denied on 403', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it('maps a 403 on loadPlatformUsers to permission_denied', async () => {
    vi.spyOn(api, 'get').mockRejectedValueOnce(new ApiError(403, { code: 'forbidden' }))
    const store = useAdminStore()
    await store.loadPlatformUsers()
    expect(store.opsError).toBe('permission_denied')
  })

  it('maps a 403 on loadWorkshops to permission_denied', async () => {
    vi.spyOn(api, 'get').mockRejectedValueOnce(new ApiError(403, {}))
    const store = useAdminStore()
    await store.loadWorkshops()
    expect(store.error).toBe('permission_denied')
  })

  it('keeps the generic fallback code on a non-403 failure', async () => {
    vi.spyOn(api, 'get').mockRejectedValueOnce(new ApiError(500, {}))
    const store = useAdminStore()
    await store.loadJobs()
    expect(store.opsError).toBe('jobs_load_failed')
  })
})

describe('admin store catalog loader state', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it('keeps manufacturer and material errors independent', async () => {
    const store = useAdminStore()
    vi.spyOn(api, 'get').mockRejectedValueOnce(new ApiError(403, { code: 'forbidden' }))
    await store.loadManufacturers()
    expect(store.manufacturersError).toBe('permission_denied')
    expect(store.materialsError).toBeNull()

    vi.spyOn(api, 'get').mockResolvedValueOnce([])
    await store.loadMaterials()
    expect(store.manufacturersError).toBe('permission_denied')
    expect(store.materialsError).toBeNull()
  })
})

describe('admin store audit loading', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it('passes server filters and appends offset pages', async () => {
    const get = vi
      .spyOn(api, 'get')
      .mockResolvedValueOnce([makeAction('a1')])
      .mockResolvedValueOnce([makeStatus('s1')])
      .mockResolvedValueOnce([makeAction('a2')])
      .mockResolvedValueOnce([makeStatus('s2')])
    const store = useAdminStore()

    const first = await store.loadAudit({
      actions: { workshop_id: 'w1', action_prefix: 'platform', limit: 50, offset: 0 },
      status: { workshop_id: 'w1', to_status: 'blocked', limit: 50, offset: 0 },
    })
    const next = await store.loadAudit({
      actions: { workshop_id: 'w1', action_prefix: 'platform', limit: 50, offset: 1 },
      status: { workshop_id: 'w1', to_status: 'blocked', limit: 50, offset: 1 },
      appendActions: true,
      appendStatus: true,
    })

    expect(first).toEqual({ actionsCount: 1, statusCount: 1 })
    expect(next).toEqual({ actionsCount: 1, statusCount: 1 })
    expect(get).toHaveBeenNthCalledWith(
      1,
      '/platform/audit/actions?workshop_id=w1&action_prefix=platform&limit=50&offset=0',
      { accessToken: null },
    )
    expect(get).toHaveBeenNthCalledWith(
      2,
      '/platform/audit/status-changes?workshop_id=w1&to_status=blocked&limit=50&offset=0',
      { accessToken: null },
    )
    expect(store.auditActions.map((row) => row.id)).toEqual(['a1', 'a2'])
    expect(store.auditStatusChanges.map((row) => row.id)).toEqual(['s1', 's2'])
  })
})

// AB-15 / AB-31: runJob's optimistic merge — prepend + cap-5, and do NOT
// overwrite a real terminal result with a `skipped` (already-running) outcome.
describe('admin store runJob optimistic merge', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it('prepends the run capped at 5 and keeps a prior failed result on a skip', async () => {
    const store = useAdminStore()
    store.jobs = [
      {
        definition: {
          id: 'd1',
          name: 'cleanup-expired-sessions',
          schedule: 'hourly',
          enabled: true,
          running: false,
          last_run_at: '2026-06-19T09:00:00Z',
          last_result: 'failed',
          updated_at: '2026-06-19T09:00:00Z',
        },
        recent_runs: ['r5', 'r4', 'r3', 'r2', 'r1'].map((id) => makeRun(id, 'ok')),
      },
    ]
    vi.spyOn(api, 'post').mockResolvedValueOnce(makeRun('r6', 'skipped'))
    const run = await store.runJob('cleanup-expired-sessions')
    expect(run.status).toBe('skipped')
    const row = store.jobs[0]!
    expect(row.recent_runs).toHaveLength(5)
    expect(row.recent_runs[0]!.id).toBe('r6')
    // skipped must NOT overwrite the prior real `failed` result
    expect(row.definition.last_result).toBe('failed')
  })

  it('mirrors a terminal ok result onto the definition', async () => {
    const store = useAdminStore()
    store.jobs = [
      {
        definition: {
          id: 'd1',
          name: 'cleanup-expired-sessions',
          schedule: 'hourly',
          enabled: true,
          running: false,
          last_run_at: null,
          last_result: 'failed',
          updated_at: '2026-06-19T09:00:00Z',
        },
        recent_runs: [],
      },
    ]
    vi.spyOn(api, 'post').mockResolvedValueOnce(makeRun('r1', 'ok'))
    await store.runJob('cleanup-expired-sessions')
    expect(store.jobs[0]!.definition.last_result).toBe('ok')
  })

  it('is a no-op for an unknown job name', async () => {
    const store = useAdminStore()
    store.jobs = []
    vi.spyOn(api, 'post').mockResolvedValueOnce(makeRun('r1', 'ok'))
    const run = await store.runJob('does-not-exist')
    expect(run.status).toBe('ok')
    expect(store.jobs).toHaveLength(0)
  })
})

// AB-37 / AB-22: block/unblock and material edits return the lean single-object
// shape (no owner_login/branch_count/branch_usage_count); the patch helpers must
// merge so those list-only fields survive a status/profile change.
describe('admin store list-only fields survive single-object patches', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it('blockWorkshop keeps owner_login + branch_count (AB-37)', async () => {
    const store = useAdminStore()
    store.workshops = [makeListWorkshop()]
    // the block response is the lean WorkshopSummary — owner_login/branch_count
    // keys are absent, not undefined, so the merge preserves the list row's.
    vi.spyOn(api, 'post').mockResolvedValueOnce({
      id: 'w1',
      code: 'c1',
      name: 'WS',
      phone: '+998900000000',
      address: null,
      status: 'blocked',
      owner_user_id: 'u1',
      created_at: '2026-06-19T10:00:00Z',
    })
    await store.blockWorkshop('w1', 'Unpaid invoice')
    const row = store.workshops[0]!
    expect(row.status).toBe('blocked')
    expect(row.owner_login).toBe('owner-1')
    expect(row.branch_count).toBe(3)
  })

  it('updateMaterial keeps branch_usage_count (AB-22)', async () => {
    const store = useAdminStore()
    store.materials = [makeMaterial('m1', 4)]
    // single-material response returns 0 for the uncomputed count
    vi.spyOn(api, 'patch').mockResolvedValueOnce(makeMaterial('m1', 0, 'Renamed'))
    await store.updateMaterial('m1', {} as MaterialWriteRequest)
    const row = store.materials[0]!
    expect(row.name).toBe('Renamed')
    expect(row.branch_usage_count).toBe(4)
  })
})

// AB-25: reopenError flips a resolved record back to open in both the list and
// the open detail.
describe('admin store reopenError', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it('flips the record to open in the list and detail', async () => {
    const store = useAdminStore()
    store.errors = [makeError('e1', 'resolved')]
    store.errorDetail = { record: makeError('e1', 'resolved'), occurrences: [] }
    vi.spyOn(api, 'post').mockResolvedValueOnce(makeError('e1', 'open'))
    await store.reopenError('e1')
    expect(store.errors[0]!.status).toBe('open')
    expect(store.errorDetail!.record.status).toBe('open')
    expect(store.errorDetail!.record.resolved_at).toBeNull()
  })
})
