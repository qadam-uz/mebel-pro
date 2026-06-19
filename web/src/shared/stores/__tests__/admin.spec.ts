import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import { useAdminStore, type JobRun, type JobRunStatus } from '@/shared/stores/admin'

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
