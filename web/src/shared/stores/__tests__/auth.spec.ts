import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import { useAuthStore, type TokenResponse } from '@/shared/stores/auth'

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
    api: {
      post: vi.fn(),
      get: vi.fn(),
      del: vi.fn(),
    },
  }
})

const tokenResponse: TokenResponse = {
  access_token: 'access-1',
  token_type: 'bearer',
  access_token_expires_at: '2026-06-02T10:00:00Z',
  me: {
    principal_type: 'platform_user',
    principal_id: 'user-1',
    session_id: 'session-1',
    password_reset_required: false,
    workshop_id: null,
    is_owner: false,
    grants: [],
    login: 'admin',
    full_name: 'Admin User',
    phone: '+998901234567',
    name: null,
    preferred_branch_id: null,
    status: 'active',
  },
}

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.post).mockReset()
    vi.mocked(api.get).mockReset()
    vi.mocked(api.del).mockReset()
  })

  it('restores from the refresh cookie once and applies role checks', async () => {
    vi.mocked(api.post).mockResolvedValue(tokenResponse)
    const auth = useAuthStore()

    await auth.restore()
    await auth.restore()

    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/auth/refresh')
    expect(auth.displayName).toBe('Admin User')
    expect(auth.isAllowedFor('admin')).toBe(true)
    expect(auth.isAllowedFor('workshop')).toBe(false)
  })

  it('logs in platform users and keeps the access token in memory', async () => {
    vi.mocked(api.post).mockResolvedValue(tokenResponse)
    const auth = useAuthStore()

    await auth.platformLogin('admin', 'Admin123')

    expect(api.post).toHaveBeenCalledWith('/auth/platform/login', {
      login: 'admin',
      password: 'Admin123',
    })
    expect(auth.accessToken).toBe('access-1')
    expect(auth.me?.principal_type).toBe('platform_user')
  })

  it('clears memory state after logout', async () => {
    vi.mocked(api.post).mockResolvedValue(tokenResponse)
    vi.mocked(api.del).mockResolvedValue('')
    const auth = useAuthStore()
    await auth.platformLogin('admin', 'Admin123')

    await auth.logoutCurrent()

    expect(api.del).toHaveBeenCalledWith('/auth/sessions/current', { accessToken: 'access-1' })
    expect(auth.accessToken).toBeNull()
    expect(auth.me).toBeNull()
  })
})
