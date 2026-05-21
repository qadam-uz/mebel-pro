// Typed fetch wrapper for the backend JSON API (/api/v1).
//
// - Attaches `Authorization: Bearer <access>` from per-app token storage.
// - On 401, tries POST /auth/refresh with the stored refresh token exactly
//   once, retries the request, and on failure clears tokens + redirects to the
//   app's login route.
// - Parses the { code, detail, trace_id } error envelope into a typed ApiError.
//
// In dev VITE_API_BASE_URL is empty and Vite proxies /api → :8000; same in
// prod (the Caddy edge serves the API same-origin). Don't hardcode a host.

import type { ApiErrorBody, RefreshResponse } from '@/shared/types'
import type { AppKey } from './storage'
import { clearTokens, getTokens, setAccessToken } from './storage'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const API_PREFIX = '/api/v1'

export class ApiError extends Error {
  readonly code: string
  readonly detail: string
  readonly traceId?: string

  constructor(
    readonly status: number,
    body: unknown,
  ) {
    const envelope = (body ?? {}) as Partial<ApiErrorBody>
    const detail =
      typeof envelope.detail === 'string' ? envelope.detail : `Request failed (${status})`
    super(detail)
    this.name = 'ApiError'
    this.code = typeof envelope.code === 'string' ? envelope.code : `http_${status}`
    this.detail = detail
    this.traceId = typeof envelope.trace_id === 'string' ? envelope.trace_id : undefined
  }
}

// Per-app config: which storage bucket to use and where to send the user when
// the session can't be refreshed. Set once at app bootstrap by configureApi().
interface ApiConfig {
  app: AppKey
  loginPath: string
}

let config: ApiConfig | null = null

export function configureApi(cfg: ApiConfig): void {
  config = cfg
}

function requireConfig(): ApiConfig {
  if (!config) throw new Error('configureApi() must be called before using the API client.')
  return config
}

function redirectToLogin(): void {
  const cfg = requireConfig()
  clearTokens(cfg.app)
  // Hard redirect — the router may not be mounted yet, and we want a clean slate.
  if (typeof window !== 'undefined' && !window.location.pathname.endsWith(cfg.loginPath)) {
    window.location.assign(cfg.loginPath)
  }
}

async function parseBody(res: Response): Promise<unknown> {
  if (res.status === 204) return null
  const isJson = res.headers.get('content-type')?.includes('application/json')
  return isJson ? res.json() : res.text()
}

// One in-flight refresh shared by concurrent 401s so we hit /auth/refresh once.
let refreshInFlight: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    const cfg = requireConfig()
    const tokens = getTokens(cfg.app)
    if (!tokens?.refresh) return false
    try {
      const res = await fetch(`${BASE_URL}${API_PREFIX}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: tokens.refresh }),
      })
      if (!res.ok) return false
      const body = (await res.json()) as RefreshResponse
      if (!body.access_token) return false
      setAccessToken(cfg.app, body.access_token)
      return true
    } catch {
      return false
    }
  })()
  try {
    return await refreshInFlight
  } finally {
    refreshInFlight = null
  }
}

interface RequestOptions extends RequestInit {
  // Skip the Authorization header (e.g. the login/refresh calls themselves).
  auth?: boolean
}

async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
  const cfg = requireConfig()
  const { auth = true, ...rest } = init

  const send = (): Promise<Response> => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(rest.headers as Record<string, string> | undefined),
    }
    if (auth) {
      const tokens = getTokens(cfg.app)
      if (tokens?.access) headers.Authorization = `Bearer ${tokens.access}`
    }
    return fetch(`${BASE_URL}${API_PREFIX}${path}`, { ...rest, headers })
  }

  let res = await send()

  if (res.status === 401 && auth) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      res = await send()
    }
    if (res.status === 401) {
      redirectToLogin()
      throw new ApiError(401, await parseBody(res))
    }
  }

  const body = await parseBody(res)
  if (!res.ok) throw new ApiError(res.status, body)
  return body as T
}

export const api = {
  get: <T>(path: string, init?: RequestOptions) => request<T>(path, init),
  post: <T>(path: string, data?: unknown, init?: RequestOptions) =>
    request<T>(path, {
      ...init,
      method: 'POST',
      body: data === undefined ? null : JSON.stringify(data),
    }),
  put: <T>(path: string, data?: unknown, init?: RequestOptions) =>
    request<T>(path, {
      ...init,
      method: 'PUT',
      body: data === undefined ? null : JSON.stringify(data),
    }),
  patch: <T>(path: string, data?: unknown, init?: RequestOptions) =>
    request<T>(path, {
      ...init,
      method: 'PATCH',
      body: data === undefined ? null : JSON.stringify(data),
    }),
  del: <T>(path: string, init?: RequestOptions) => request<T>(path, { ...init, method: 'DELETE' }),
}
