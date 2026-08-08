import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { api } from '@/shared/api/client'
import { useAdminStore } from '@/shared/stores/admin'

vi.mock('@/shared/app/authInit', () => ({
  authInit: () => ({ accessToken: 'access-token' }),
}))

vi.mock('@/shared/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn(), blob: vi.fn() },
  apiErrorCode: () => null,
  apiTraceId: () => null,
  captureApiError: vi.fn((_error: unknown, fallback: string) => ({
    code: fallback,
    traceId: null,
  })),
  withQuery: (path: string) => path,
}))

const apiGet = vi.mocked(api.get)
const apiPost = vi.mocked(api.post)

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

/**
 * A list read carries a server snapshot from the moment it started. When a
 * mutation lands while that read is in flight, the snapshot is already stale —
 * assigning it on arrival rolls the screen back with no error and nothing to
 * retry.
 *
 * Reproduced against the running app before this guard existed: provisioning a
 * workshop while the page's own initial load was still outstanding made the new
 * row appear and then disappear. It also surfaced as a flaky E2E
 * (`access-and-provisioning.spec.ts` "admin provisions and blocks a workshop"),
 * which is the same race seen from the outside.
 */
describe('admin store — a stale list read never overwrites a newer mutation', () => {
  it('keeps a provisioned workshop when the in-flight list read lands after it', async () => {
    const pending = deferred<unknown>()
    apiGet.mockReturnValueOnce(pending.promise as never)
    apiPost.mockResolvedValueOnce({
      workshop: { id: 'w-new', name: 'Fresh Workshop', status: 'active' },
      owner: { login: 'owner-new' },
      temp_password: 'Temp12345',
    } as never)

    const admin = useAdminStore()
    const reading = admin.loadWorkshops()

    await admin.provision({
      workshop: { name: 'Fresh Workshop' },
      branch: { name: 'B', address: 'Tashkent', phone: '+998901234567' },
      owner: { login: 'owner-new' },
    } as never)
    expect(admin.workshops.map((row) => row.id)).toEqual(['w-new'])

    // The read started BEFORE the workshop existed, so its payload cannot contain it.
    pending.resolve([{ id: 'w-old', name: 'Existing', status: 'active' }])
    await reading

    expect(admin.workshops.map((row) => row.id)).toEqual(['w-new'])
    expect(admin.loading).toBe(false)
  })

  it('keeps a block when the in-flight list read lands after it', async () => {
    const pending = deferred<unknown>()
    apiGet.mockReturnValueOnce(pending.promise as never)
    apiPost.mockResolvedValueOnce({ id: 'w-1', name: 'One', status: 'blocked' } as never)

    const admin = useAdminStore()
    admin.workshops = [{ id: 'w-1', name: 'One', status: 'active' }] as never
    const reading = admin.loadWorkshops()

    await admin.blockWorkshop('w-1', 'E2E block')
    expect(admin.workshops[0]?.status).toBe('blocked')

    pending.resolve([{ id: 'w-1', name: 'One', status: 'active' }])
    await reading

    expect(admin.workshops[0]?.status).toBe('blocked')
  })

  it('still applies a read that nothing superseded', async () => {
    apiGet.mockResolvedValueOnce([{ id: 'w-1', name: 'One', status: 'active' }] as never)

    const admin = useAdminStore()
    await admin.loadWorkshops()

    expect(admin.workshops.map((row) => row.id)).toEqual(['w-1'])
    expect(admin.loading).toBe(false)
  })

  it('does not paint an error from a read a mutation superseded', async () => {
    const pending = deferred<unknown>()
    apiGet.mockReturnValueOnce(pending.promise as never)
    apiPost.mockResolvedValueOnce({
      workshop: { id: 'w-new', name: 'Fresh', status: 'active' },
      owner: { login: 'owner-new' },
      temp_password: 'Temp12345',
    } as never)

    const admin = useAdminStore()
    const reading = admin.loadWorkshops()
    await admin.provision({
      workshop: { name: 'Fresh' },
      branch: { name: 'B', address: 'Tashkent', phone: '+998901234567' },
      owner: { login: 'owner-new' },
    } as never)

    pending.reject(new Error('network went away'))
    await reading

    expect(admin.error).toBeNull()
    expect(admin.workshops.map((row) => row.id)).toEqual(['w-new'])
  })
})
