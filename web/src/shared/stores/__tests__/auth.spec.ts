import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
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

  it('requests a client OTP and clears the last error (CB-110)', async () => {
    vi.mocked(api.post).mockResolvedValue({
      phone: '+998901234567',
      expires_at: '2026-06-02T10:05:00Z',
      resend_after_seconds: 60,
    })
    const auth = useAuthStore()

    const response = await auth.requestClientOtp('+998901234567')

    expect(api.post).toHaveBeenCalledWith('/auth/client/otp/request', { phone: '+998901234567' })
    expect(response.resend_after_seconds).toBe(60)
    expect(auth.lastError).toBeNull()
  })

  it('keeps the session anonymous when OTP verify reports a new client (CB-110)', async () => {
    vi.mocked(api.post).mockResolvedValue({ is_new: true })
    const auth = useAuthStore()

    const response = await auth.verifyClientOtp('+998901234567', '000000')

    expect(response).toEqual({ is_new: true })
    expect(auth.accessToken).toBeNull()
    expect(auth.status).toBe('anonymous')
  })

  it('applies the token when OTP verify returns a session (CB-110)', async () => {
    const clientToken: TokenResponse = {
      ...tokenResponse,
      me: { ...tokenResponse.me, principal_type: 'client', name: 'Mijoz' },
    }
    vi.mocked(api.post).mockResolvedValue(clientToken)
    const auth = useAuthStore()

    await auth.verifyClientOtp('+998901234567', '000000', 'Mijoz')

    expect(auth.accessToken).toBe('access-1')
    expect(auth.me?.principal_type).toBe('client')
    expect(auth.isAllowedFor('client')).toBe(true)
  })

  it('maps an OTP verify failure to a last-error code + details (CB-110)', async () => {
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(422, { code: 'invalid_code', details: { attempts_remaining: 3 } }),
    )
    const auth = useAuthStore()

    await expect(auth.verifyClientOtp('+998901234567', '000001')).rejects.toBeInstanceOf(ApiError)
    expect(auth.lastError).toBe('invalid_code')
    expect(auth.lastErrorDetails).toEqual({ attempts_remaining: 3 })
    expect(auth.status).toBe('anonymous')
  })
})
