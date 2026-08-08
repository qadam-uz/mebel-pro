import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  ApiTimeoutError,
  api,
  apiTraceId,
  captureApiError,
  configureSession,
  isAbortError,
  withQuery,
} from '@/shared/api/client'

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

  it('captureApiError maps 403, preserves the backend code, else falls back (CB-100)', () => {
    expect(captureApiError(new ApiError(403, { code: 'whatever' }), 'fb')).toEqual({
      code: 'permission_denied',
      traceId: null,
    })
    expect(captureApiError(new ApiError(409, { code: 'order_version_conflict' }), 'fb')).toEqual({
      code: 'order_version_conflict',
      traceId: null,
    })
    expect(captureApiError(new ApiError(500, { trace_id: 'tr-9' }), 'fb')).toEqual({
      code: 'fb',
      traceId: 'tr-9',
    })
    expect(captureApiError(new Error('network'), 'fb')).toEqual({ code: 'fb', traceId: null })
  })

  it('builds query strings, keeping false/0 but dropping null/undefined/"" (CB-98)', () => {
    // `tape=false` is the live case: it selects the panel-shaped half of a
    // branch's catalog, so dropping it would silently return tapes instead.
    expect(withQuery('/m', { tape: false, count: 0 })).toBe('/m?tape=false&count=0')
    expect(withQuery('/m', { a: null, b: undefined, c: '' })).toBe('/m')
    expect(withQuery('/m', { keep: 'yes', drop: null, flag: false })).toBe('/m?keep=yes&flag=false')
    expect(withQuery('/m', {})).toBe('/m')
  })

  it('reports a refused authed call so the shell can re-read its grants (QAD-172)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ code: 'forbidden' }, 403))
    const onForbidden = vi.fn()
    configureSession({ refresh: vi.fn(), onExpired: vi.fn(), onForbidden })

    await expect(
      api.get('/workshop/branches/b-1/stock', { accessToken: 'access-1' }),
    ).rejects.toMatchObject({ status: 403 })
    expect(onForbidden).toHaveBeenCalledTimes(1)
  })

  it('never reports a refused /auth call, so revalidation cannot recurse (QAD-172)', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ code: 'forbidden' }, 403),
    )
    const onForbidden = vi.fn()
    configureSession({ refresh: vi.fn(), onExpired: vi.fn(), onForbidden })

    await expect(api.get('/auth/me', { accessToken: 'access-1' })).rejects.toMatchObject({
      status: 403,
    })
    // Unauthenticated calls carry no grant set to revalidate either.
    await expect(api.get('/workshop/orders')).rejects.toMatchObject({ status: 403 })
    expect(onForbidden).not.toHaveBeenCalled()
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

  // A dropped connection never settles `fetch`, so before this the calling screen
  // kept its skeleton up for the life of the tab — the reported "search freezes".
  it('rejects with ApiTimeoutError when a request outlives its ceiling', async () => {
    vi.useFakeTimers()
    try {
      vi.spyOn(globalThis, 'fetch').mockImplementation(
        (_url, init) =>
          new Promise((_resolve, reject) => {
            const signal = (init as RequestInit).signal
            signal?.addEventListener('abort', () =>
              reject(new DOMException('Aborted', 'AbortError')),
            )
          }),
      )

      const pending = api.get('/workshop/orders', { timeoutMs: 5_000 })
      const assertion = expect(pending).rejects.toBeInstanceOf(ApiTimeoutError)
      await vi.advanceTimersByTimeAsync(5_000)
      await assertion
    } finally {
      vi.useRealTimers()
    }
  })

  it('maps a timeout to request_timeout so the UI can name the cause', () => {
    expect(captureApiError(new ApiTimeoutError(20_000), 'orders_load_failed')).toEqual({
      code: 'request_timeout',
      traceId: null,
    })
  })

  // A superseded search aborts its predecessor. That is not a failure, and the
  // screen must not paint an error for it — only `isAbortError` can tell them
  // apart once both arrive as a rejected promise.
  it('reports a caller cancellation as an abort, not a timeout', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          const signal = (init as RequestInit).signal
          signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        }),
    )
    const controller = new AbortController()

    const pending = api.get('/workshop/orders', { signal: controller.signal })
    controller.abort()

    await expect(pending).rejects.toSatisfy(isAbortError)
    await expect(pending).rejects.not.toBeInstanceOf(ApiTimeoutError)
  })

  it('leaves the request alone when the ceiling is disabled', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse({ status: 'ok' }, 200))

    await api.get('/readyz', { timeoutMs: null })

    // No signal means no timer was armed — a stream can outlive any ceiling.
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).signal).toBeUndefined()
  })
})
