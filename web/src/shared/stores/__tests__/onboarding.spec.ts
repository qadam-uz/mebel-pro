import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { api } from '@/shared/api/client'
import { useAuthStore, type MeResponse } from '@/shared/stores/auth'
import { useOnboardingStore, type WorkshopOnboardingStatus } from '@/shared/stores/onboarding'

vi.mock('@/shared/app/authInit', () => ({
  authInit: () => ({ accessToken: 'access-token' }),
}))

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    del: vi.fn(),
  },
}))

const apiGet = vi.mocked(api.get)

function memoryStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() {
      return values.size
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  }
}

function me(overrides: Partial<MeResponse> = {}): MeResponse {
  return {
    principal_type: 'workshop_user',
    principal_id: 'owner-1',
    session_id: 'session-1',
    password_reset_required: false,
    workshop_id: 'workshop-1',
    is_owner: true,
    grants: [],
    login: 'owner',
    full_name: 'Workshop Owner',
    phone: null,
    name: null,
    preferred_branch_id: null,
    status: 'active',
    ...overrides,
  }
}

function status(overrides: Partial<WorkshopOnboardingStatus> = {}): WorkshopOnboardingStatus {
  return {
    branch_configured: false,
    materials_added: false,
    setup_complete: false,
    first_branch_id: 'branch-1',
    ...overrides,
  }
}

describe('onboarding store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // Node's jsdom setup can expose an incomplete localStorage shim. Use a full
    // in-memory Storage implementation (productionCheckpoints.spec precedent).
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: memoryStorage(),
    })
  })

  it('refreshes derived status for an eligible owner', async () => {
    useAuthStore().me = me()
    apiGet.mockResolvedValueOnce(status())
    const onboarding = useOnboardingStore()

    const result = await onboarding.refresh()

    expect(apiGet).toHaveBeenCalledWith('/workshop/onboarding', { accessToken: 'access-token' })
    expect(result).toEqual(status())
    expect(onboarding.loaded).toBe(true)
    expect(onboarding.showChecklist).toBe(true)
  })

  it('never calls the API for staff or a pending password gate', async () => {
    const auth = useAuthStore()
    const onboarding = useOnboardingStore()

    auth.me = me({ is_owner: false })
    expect(await onboarding.refresh()).toBeNull()

    auth.me = me({ password_reset_required: true })
    expect(await onboarding.refresh()).toBeNull()

    expect(apiGet).not.toHaveBeenCalled()
    expect(onboarding.showChecklist).toBe(false)
  })

  it('keeps the last status when a refetch fails — the helper never breaks the page', async () => {
    useAuthStore().me = me()
    const onboarding = useOnboardingStore()
    apiGet.mockResolvedValueOnce(status())
    await onboarding.refresh()

    apiGet.mockRejectedValueOnce(new Error('network'))
    const result = await onboarding.refresh()

    expect(result).toEqual(status())
    expect(onboarding.showChecklist).toBe(true)
  })

  it('hides the checklist once setup is complete', async () => {
    useAuthStore().me = me()
    const onboarding = useOnboardingStore()
    apiGet.mockResolvedValueOnce(
      status({ branch_configured: true, materials_added: true, setup_complete: true }),
    )

    await onboarding.refresh()

    expect(onboarding.showChecklist).toBe(false)
  })

  it('shows a pending hint once, then only on an explicit force', async () => {
    useAuthStore().me = me()
    const onboarding = useOnboardingStore()
    apiGet.mockResolvedValueOnce(status())
    await onboarding.refresh()

    expect(onboarding.requestHint('branch-pricing')).toBe(true)
    onboarding.dismissHint({ markSeen: true })

    expect(onboarding.requestHint('branch-pricing')).toBe(false)
    expect(onboarding.requestHint('branch-pricing', { force: true })).toBe(true)
  })

  it('refuses a hint whose step is already done, even when forced', async () => {
    useAuthStore().me = me()
    const onboarding = useOnboardingStore()
    apiGet.mockResolvedValueOnce(status({ branch_configured: true }))
    await onboarding.refresh()

    expect(onboarding.requestHint('branch-pricing', { force: true })).toBe(false)
    expect(onboarding.requestHint('catalog-add')).toBe(true)
  })

  it('scopes seen-markers to the principal', async () => {
    useAuthStore().me = me()
    const onboarding = useOnboardingStore()
    apiGet.mockResolvedValue(status())
    await onboarding.refresh()
    onboarding.requestHint('catalog-add')
    onboarding.dismissHint({ markSeen: true })
    expect(onboarding.hasSeenHint('catalog-add')).toBe(true)

    useAuthStore().me = me({ principal_id: 'owner-2' })
    expect(onboarding.hasSeenHint('catalog-add')).toBe(false)
  })

  it('queues a hint and hands it over exactly once', () => {
    const onboarding = useOnboardingStore()
    onboarding.queueHint('catalog-add')

    expect(onboarding.consumeQueuedHint()).toBe('catalog-add')
    expect(onboarding.consumeQueuedHint()).toBeNull()
  })

  it('resets to a blank slate on logout', async () => {
    useAuthStore().me = me()
    const onboarding = useOnboardingStore()
    apiGet.mockResolvedValueOnce(status())
    await onboarding.refresh()
    onboarding.requestHint('branch-pricing')
    onboarding.queueHint('catalog-add')

    onboarding.reset()

    expect(onboarding.status).toBeNull()
    expect(onboarding.loaded).toBe(false)
    expect(onboarding.activeHintKey).toBeNull()
    expect(onboarding.queuedHintKey).toBeNull()
  })
})
