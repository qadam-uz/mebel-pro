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
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/readyz',
      expect.objectContaining({
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    )
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
