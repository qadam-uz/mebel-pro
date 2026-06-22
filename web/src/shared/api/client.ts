// Thin fetch wrapper for the same-origin backend JSON API.

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

export function apiTraceId(error: unknown): string | null {
  if (!(error instanceof ApiError) || typeof error.body !== 'object' || error.body === null) {
    return null
  }
  const traceId = (error.body as { trace_id?: unknown }).trace_id
  return typeof traceId === 'string' ? traceId : null
}

export function apiErrorCode(error: unknown): string | null {
  if (!(error instanceof ApiError) || typeof error.body !== 'object' || error.body === null) {
    return null
  }
  const code = (error.body as { code?: unknown }).code
  return typeof code === 'string' ? code : null
}

/**
 * Canonical error capture for stores (CB-100): a 403 always maps to
 * `permission_denied`; otherwise the backend `code` is preserved so the UI's
 * translation layer (`clientErrorLabel`) can show a specific message, falling back
 * to `fallback` for non-ApiError failures or a code-less body. Replaces three
 * divergent per-store variants, one of which dropped the backend code entirely.
 */
export function captureApiError(
  error: unknown,
  fallback: string,
): { code: string; traceId: string | null } {
  let code = fallback
  if (error instanceof ApiError) {
    code = error.status === 403 ? 'permission_denied' : (apiErrorCode(error) ?? fallback)
  }
  return { code, traceId: apiTraceId(error) }
}

// Build a query string, dropping only null/undefined/empty-string — `false` and
// `0` ARE sent (e.g. `carried_only=false`). One shared copy replaces six
// store-local `withQuery`s, three of which used a truthy check that silently
// dropped `false`/`0` (CB-98).
export function withQuery(
  path: string,
  params: Record<string, string | number | boolean | null | undefined>,
): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

// Session bridge for transparent token refresh on 401 (CB-08). The app wires
// this at bootstrap so the framework-agnostic client can ask the auth store to
// refresh and, on failure, redirect to login — without importing the store
// (which would create a cycle).
export interface SessionHooks {
  // Silently refresh the access token; resolves to the new token, or null when
  // the session can't be renewed.
  refresh: () => Promise<string | null>
  // Called when refresh fails — clear auth and route to login.
  onExpired: () => void
}

let sessionHooks: SessionHooks | null = null
let refreshInFlight: Promise<string | null> | null = null

export function configureSession(hooks: SessionHooks | null) {
  sessionHooks = hooks
}

// Dedupe concurrent 401s onto a single refresh round-trip.
function runRefresh(): Promise<string | null> {
  if (!sessionHooks) return Promise.resolve(null)
  if (!refreshInFlight) {
    const hooks = sessionHooks
    refreshInFlight = hooks
      .refresh()
      .catch(() => null)
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

async function request<T>(path: string, init: ApiRequestInit = {}, retrying = false): Promise<T> {
  const { accessToken, headers, ...requestInit } = init
  const mergedHeaders = new Headers(headers)
  const isFormData = typeof FormData !== 'undefined' && requestInit.body instanceof FormData
  if (!mergedHeaders.has('Content-Type') && requestInit.body !== undefined && !isFormData) {
    mergedHeaders.set('Content-Type', 'application/json')
  }
  if (accessToken) {
    mergedHeaders.set('Authorization', `Bearer ${accessToken}`)
  }
  const res = await fetch(`${API_PREFIX}${path}`, {
    credentials: 'include',
    headers: mergedHeaders,
    ...requestInit,
  })
  const isJson = res.headers.get('content-type')?.includes('application/json')
  const text = res.status === 204 ? '' : await res.text()
  const body = isJson && text.length > 0 ? JSON.parse(text) : text
  if (!res.ok) {
    // An authed call whose token expired: try one silent refresh + retry, then
    // hand off to the session bridge to redirect to login (CB-08). The refresh
    // call itself carries no accessToken, so it never recurses here.
    if (
      res.status === 401 &&
      accessToken &&
      !retrying &&
      sessionHooks &&
      !path.startsWith('/auth/refresh')
    ) {
      const newToken = await runRefresh()
      if (newToken) return request<T>(path, { ...init, accessToken: newToken }, true)
      sessionHooks.onExpired()
    }
    throw new ApiError(res.status, body)
  }
  return body as T
}

async function requestBlob(path: string, init: ApiRequestInit = {}): Promise<Blob> {
  const { accessToken, headers, ...requestInit } = init
  const mergedHeaders = new Headers(headers)
  if (accessToken) {
    mergedHeaders.set('Authorization', `Bearer ${accessToken}`)
  }
  const res = await fetch(`${API_PREFIX}${path}`, {
    credentials: 'include',
    headers: mergedHeaders,
    ...requestInit,
  })
  if (!res.ok) {
    const isJson = res.headers.get('content-type')?.includes('application/json')
    const text = await res.text()
    const body = isJson && text.length > 0 ? JSON.parse(text) : text
    throw new ApiError(res.status, body)
  }
  return await res.blob()
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
  postForm: <T>(path: string, data: FormData, init?: ApiRequestInit) =>
    request<T>(path, { method: 'POST', body: data, ...init }),
  blob: (path: string, init?: ApiRequestInit) => requestBlob(path, init),
  del: <T>(path: string, init?: ApiRequestInit) => request<T>(path, { method: 'DELETE', ...init }),
}
