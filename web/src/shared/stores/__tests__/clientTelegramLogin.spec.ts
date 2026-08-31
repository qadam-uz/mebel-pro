import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import { useAuthStore, type MeResponse } from '@/shared/stores/auth'

const clientMe: MeResponse = {
  principal_type: 'client',
  principal_id: 'client-1',
  session_id: 'session-1',
  password_reset_required: false,
  workshop_id: null,
  workshop_name: null,
  is_owner: false,
  grants: [],
  login: null,
  full_name: null,
  phone: '+998901112233',
  name: 'Dilshod',
  preferred_branch_id: null,
  status: 'active',
}

const session = {
  access_token: 'access-1',
  token_type: 'bearer' as const,
  access_token_expires_at: '2026-01-01T00:05:00Z',
  me: clientMe,
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('client Telegram sign-in (auth store)', () => {
  it('mints a handshake and hands back the deep link the QR renders', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      token: 'tok',
      poll_secret: 'secret',
      deep_link: 'https://t.me/mebelpro_bot?start=tok',
      expires_at: '2026-01-01T00:05:00Z',
    })
    const auth = useAuthStore()

    const issued = await auth.createClientLoginToken()

    expect(post).toHaveBeenCalledWith('/auth/client/telegram/token')
    expect(issued.deep_link).toBe('https://t.me/mebelpro_bot?start=tok')
    expect(auth.lastError).toBeNull()
  })

  it('keeps the token-creation throttle code and its retry budget', async () => {
    vi.spyOn(api, 'post').mockRejectedValue(
      new ApiError(429, {
        code: 'login_token_rate_limited',
        details: { retry_after_seconds: 42 },
      }),
    )
    const auth = useAuthStore()

    await expect(auth.createClientLoginToken()).rejects.toBeInstanceOf(ApiError)
    expect(auth.lastError).toBe('login_token_rate_limited')
    expect(auth.lastErrorDetails).toEqual({ retry_after_seconds: 42 })
  })

  it('polls with the poll secret and stays anonymous while the handshake runs', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ status: 'started', expired: false })
    const auth = useAuthStore()

    const answer = await auth.pollClientLogin('secret')

    expect(post).toHaveBeenCalledWith('/auth/client/telegram/poll', { poll_secret: 'secret' })
    expect(answer).toEqual({ status: 'started', expired: false })
    expect(auth.isAuthenticated).toBe(false)
  })

  it('signs in when the poll answers with a session', async () => {
    vi.spyOn(api, 'post').mockResolvedValue(session)
    const auth = useAuthStore()

    await auth.pollClientLogin('secret')

    expect(auth.accessToken).toBe('access-1')
    expect(auth.me?.principal_type).toBe('client')
    expect(auth.status).toBe('authenticated')
  })

  it('signs in on a redeemed fallback code', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue(session)
    const auth = useAuthStore()

    await auth.redeemClientLoginCode('123456')

    expect(post).toHaveBeenCalledWith('/auth/client/telegram/code', { code: '123456' })
    expect(auth.isAuthenticated).toBe(true)
  })

  it('leaves the card anonymous and keeps the generic code refusal', async () => {
    vi.spyOn(api, 'post').mockRejectedValue(new ApiError(400, { code: 'invalid_code' }))
    const auth = useAuthStore()

    await expect(auth.redeemClientLoginCode('123456')).rejects.toBeInstanceOf(ApiError)
    expect(auth.lastError).toBe('invalid_code')
    expect(auth.status).toBe('anonymous')
    expect(auth.isAuthenticated).toBe(false)
  })
})
