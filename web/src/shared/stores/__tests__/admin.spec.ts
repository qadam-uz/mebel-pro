import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import { useAdminStore } from '@/shared/stores/admin'

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
