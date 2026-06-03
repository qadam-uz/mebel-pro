// Thin fetch wrapper for the backend JSON API. Empty VITE_API_BASE_URL keeps
// requests same-origin in dev and production.

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const API_PREFIX = '/api/v1'

export interface ApiRequestInit extends RequestInit {
  accessToken?: string | null
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API ${status}`)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { accessToken, headers, ...requestInit } = init
  const mergedHeaders = new Headers(headers)
  if (!mergedHeaders.has('Content-Type') && requestInit.body !== undefined) {
    mergedHeaders.set('Content-Type', 'application/json')
  }
  if (accessToken) {
    mergedHeaders.set('Authorization', `Bearer ${accessToken}`)
  }
  const res = await fetch(`${BASE_URL}${API_PREFIX}${path}`, {
    credentials: 'include',
    headers: mergedHeaders,
    ...requestInit,
  })
  const isJson = res.headers.get('content-type')?.includes('application/json')
  const text = res.status === 204 ? '' : await res.text()
  const body = isJson && text.length > 0 ? JSON.parse(text) : text
  if (!res.ok) throw new ApiError(res.status, body)
  return body as T
}

export const api = {
  get: <T>(path: string, init?: ApiRequestInit) => request<T>(path, init),
  post: <T>(path: string, data?: unknown, init?: ApiRequestInit) =>
    request<T>(path, {
      method: 'POST',
      body: data === undefined ? undefined : JSON.stringify(data),
      ...init,
    }),
  put: <T>(path: string, data: unknown, init?: ApiRequestInit) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(data), ...init }),
  patch: <T>(path: string, data: unknown, init?: ApiRequestInit) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(data), ...init }),
  del: <T>(path: string, init?: ApiRequestInit) => request<T>(path, { method: 'DELETE', ...init }),
}
