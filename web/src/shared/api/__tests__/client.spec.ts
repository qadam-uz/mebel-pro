import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, apiTraceId, configureSession, withQuery } from '@/shared/api/client'

afterEach(() => {
  vi.restoreAllMocks()
  configureSession(null)
})

function jsonResponse(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

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

  it('extracts trace IDs from API errors', () => {
    const error = new ApiError(500, { code: 'internal_error', trace_id: 'trace-1' })

    expect(apiTraceId(error)).toBe('trace-1')
    expect(apiTraceId(new Error('nope'))).toBeNull()
  })

  it('does not force JSON content type for multipart uploads', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 'file-1' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    const formData = new FormData()
    formData.set('upload', new Blob(['hello']), 'receipt.png')

    await api.postForm('/files', formData, { accessToken: 'access-1' })

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    const headers = init.headers as Headers
    expect(headers.get('Content-Type')).toBeNull()
    expect(headers.get('Authorization')).toBe('Bearer access-1')
    expect(init.body).toBe(formData)
  })

  it('fetches blobs with bearer auth for protected files', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('image-bytes', {
        status: 200,
        headers: { 'content-type': 'image/png' },
      }),
    )

    const blob = await api.blob('/files/file-1', { accessToken: 'access-1' })

    expect(blob.size).toBe(11)
    expect(blob.type).toBe('image/png')
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    const headers = init.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer access-1')
  })

  it('refreshes once and retries the original request on 401 (CB-08)', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ code: 'unauthorized' }, 401))
      .mockResolvedValueOnce(jsonResponse({ ok: true }, 200))
    const refresh = vi.fn().mockResolvedValue('access-2')
    const onExpired = vi.fn()
    configureSession({ refresh, onExpired })

    await expect(api.get('/client/orders', { accessToken: 'access-1' })).resolves.toEqual({
      ok: true,
    })
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(onExpired).not.toHaveBeenCalled()
    const retryInit = fetchMock.mock.calls[1]?.[1] as RequestInit
    expect((retryInit.headers as Headers).get('Authorization')).toBe('Bearer access-2')
  })

  it('clears the session and rethrows when the refresh fails (CB-08)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ code: 'unauthorized' }, 401))
    const refresh = vi.fn().mockResolvedValue(null)
    const onExpired = vi.fn()
    configureSession({ refresh, onExpired })

    await expect(api.get('/client/orders', { accessToken: 'access-1' })).rejects.toMatchObject({
      status: 401,
    })
    expect(onExpired).toHaveBeenCalledTimes(1)
  })

  it('builds query strings, keeping false/0 but dropping null/undefined/"" (CB-98)', () => {
    expect(withQuery('/m', { carried_only: false, count: 0 })).toBe('/m?carried_only=false&count=0')
    expect(withQuery('/m', { a: null, b: undefined, c: '' })).toBe('/m')
    expect(withQuery('/m', { keep: 'yes', drop: null, flag: false })).toBe('/m?keep=yes&flag=false')
    expect(withQuery('/m', {})).toBe('/m')
  })

  it('does not attempt a refresh for unauthenticated 401s (CB-08)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ code: 'invalid_code' }, 401))
    const refresh = vi.fn()
    configureSession({ refresh, onExpired: vi.fn() })

    await expect(api.post('/auth/client/otp/verify', { code: '0' })).rejects.toMatchObject({
      status: 401,
    })
    expect(refresh).not.toHaveBeenCalled()
  })
})
