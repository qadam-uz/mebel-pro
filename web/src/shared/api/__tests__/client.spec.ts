import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('shared API client', () => {
  it('uses same-origin /api/v1 by default', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )

    await expect(api.get<{ status: string }>('/readyz')).resolves.toEqual({ status: 'ok' })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/readyz', expect.any(Object))
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(init.credentials).toBe('include')
    expect(init.headers).toBeInstanceOf(Headers)
  })

  it('adds bearer auth when an access token is provided', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )

    await api.get('/auth/me', { accessToken: 'access-1' })

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    const headers = init.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer access-1')
  })

  it('does not parse empty 204 JSON responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, {
        status: 204,
        headers: { 'content-type': 'application/json' },
      }),
    )

    await expect(api.post('/auth/password/change', { current_password: 'A1a' })).resolves.toBe('')
  })

  it('throws ApiError with response body on failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ code: 'internal_error', trace_id: 'trace-1' }), {
        status: 500,
        headers: { 'content-type': 'application/json' },
      }),
    )

    await expect(api.get('/readyz')).rejects.toMatchObject({
      status: 500,
      body: { code: 'internal_error', trace_id: 'trace-1' },
    })
  })
})
