// Thin fetch wrapper for the same-origin backend JSON API.

const API_PREFIX = '/api/v1'

// `fetch` has no timeout of its own: a connection the network drops without an
// RST never settles, so the promise stays pending for the life of the tab. Every
// screen that awaits one keeps its skeleton up forever — the reported "search
// freezes and never comes back". A ceiling turns that into an error state the UI
// already knows how to render, which is what `web/CLAUDE.md`'s UX bar requires
// ("every load that can hang gets a timeout → error path; no infinite spinners").
const DEFAULT_TIMEOUT_MS = 20_000
// Blobs are PDFs and images over links this app is explicitly built for; they
// deserve room that a JSON read does not.
const BLOB_TIMEOUT_MS = 120_000

export interface ApiRequestInit extends RequestInit {
  accessToken?: string | null
  /** Override the request ceiling. `null` disables it — use only for streams. */
  timeoutMs?: number | null
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

/** The request hit its ceiling. Distinct from a caller's own cancellation. */
export class ApiTimeoutError extends Error {
  constructor(readonly timeoutMs: number) {
    super(`API timeout after ${timeoutMs}ms`)
    this.name = 'ApiTimeoutError'
  }
}

/**
 * True when a rejection is a deliberate cancellation rather than a failure.
 *
 * A superseded search aborts its predecessor; that predecessor must not paint an
 * error, because nothing went wrong and a newer request already owns the screen.
 */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

/**
 * One signal that fires when the caller's signal fires or the deadline passes.
 *
 * Hand-rolled rather than `AbortSignal.any()` + `AbortSignal.timeout()`: those
 * need Safari 17.4+, and this app's users are exactly the people on older
 * phones. Returns the cleanup so the timer never outlives its request.
 */
function requestSignal(
  callerSignal: AbortSignal | null | undefined,
  timeoutMs: number | null,
): { signal: AbortSignal | undefined; timedOut: () => boolean; cleanup: () => void } {
  if (!callerSignal && timeoutMs === null) {
    return { signal: undefined, timedOut: () => false, cleanup: () => {} }
  }
  const controller = new AbortController()
  let didTimeOut = false

  const onCallerAbort = () => controller.abort(callerSignal?.reason)
  if (callerSignal) {
    if (callerSignal.aborted) controller.abort(callerSignal.reason)
    else callerSignal.addEventListener('abort', onCallerAbort, { once: true })
  }

  const timer =
    timeoutMs === null
      ? undefined
      : setTimeout(() => {
          didTimeOut = true
          controller.abort()
        }, timeoutMs)

  return {
    signal: controller.signal,
    timedOut: () => didTimeOut,
    cleanup: () => {
      if (timer !== undefined) clearTimeout(timer)
      callerSignal?.removeEventListener('abort', onCallerAbort)
    },
  }
}

export function apiTraceId(error: unknown): string | null {
  if (!(error instanceof ApiError) || typeof error.body !== 'object' || error.body === null) {
    return null
  }
  const traceId = (error.body as { trace_id?: unknown }).trace_id
  return typeof traceId === 'string' ? traceId : null
}

/** A refusal, as opposed to a transport failure or a server fault (QAD-172). */
export function isPermissionDenied(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403
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
  if (error instanceof ApiTimeoutError) {
    // Its own code: "the connection is slow, try again" is actionable, where the
    // generic fallback reads as a bug in the app.
    code = 'request_timeout'
  } else if (error instanceof ApiError) {
    code = error.status === 403 ? 'permission_denied' : (apiErrorCode(error) ?? fallback)
  }
  return { code, traceId: apiTraceId(error) }
}

// Build a query string, dropping only null/undefined/empty-string — `false` and
// `0` ARE sent (e.g. `tape=false`, which selects the panel-shaped half of a
// branch's catalog, and `price_tiyin=0` in an attach payload). One shared copy replaces six
// store-local `withQuery`s, three of which used a truthy check that silently
// dropped `false`/`0` (CB-98). Array values become repeated params
// (`?id=a&id=b`, which FastAPI reads as a `list[...]`); an empty array adds none.
export function withQuery(
  path: string,
  params: Record<string, string | number | boolean | readonly string[] | null | undefined>,
): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, String(item))
    } else {
      search.set(key, String(value as string | number | boolean))
    }
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
  // Called when an authed call is refused (403). The grant set the shell was
  // built from may be out of date, so the app re-reads the principal and
  // re-tests the current route (QAD-172). Fire-and-forget: the caller still
  // gets its ApiError and renders its own failure.
  onForbidden?: () => void
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
  const { accessToken, headers, timeoutMs, signal, ...requestInit } = init
  const mergedHeaders = new Headers(headers)
  const isFormData = typeof FormData !== 'undefined' && requestInit.body instanceof FormData
  if (!mergedHeaders.has('Content-Type') && requestInit.body !== undefined && !isFormData) {
    mergedHeaders.set('Content-Type', 'application/json')
  }
  if (accessToken) {
    mergedHeaders.set('Authorization', `Bearer ${accessToken}`)
  }
  // An upload rides the same slow link a blob download does, so it gets the same
  // headroom unless the caller says otherwise.
  const ceiling =
    timeoutMs === undefined ? (isFormData ? BLOB_TIMEOUT_MS : DEFAULT_TIMEOUT_MS) : timeoutMs
  const attempt = requestSignal(signal, ceiling)
  let res: Response
  try {
    res = await fetch(`${API_PREFIX}${path}`, {
      credentials: 'include',
      headers: mergedHeaders,
      signal: attempt.signal,
      ...requestInit,
    })
  } catch (error) {
    // Our own deadline, not the caller's cancellation — report it as a failure so
    // the calling screen leaves its loading state and shows a retry.
    if (attempt.timedOut() && isAbortError(error)) throw new ApiTimeoutError(ceiling as number)
    throw error
  } finally {
    attempt.cleanup()
  }
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
    // A refusal means the shell's cached grant set disagrees with the server —
    // ask the app to re-read it (QAD-172). `/auth/*` is excluded so the
    // revalidation round-trip can never re-enter this branch.
    if (res.status === 403 && accessToken && !path.startsWith('/auth/')) {
      sessionHooks?.onForbidden?.()
    }
    throw new ApiError(res.status, body)
  }
  return body as T
}

async function requestBlob(path: string, init: ApiRequestInit = {}): Promise<Blob> {
  const { accessToken, headers, timeoutMs, signal, ...requestInit } = init
  const mergedHeaders = new Headers(headers)
  if (accessToken) {
    mergedHeaders.set('Authorization', `Bearer ${accessToken}`)
  }
  const ceiling = timeoutMs === undefined ? BLOB_TIMEOUT_MS : timeoutMs
  const attempt = requestSignal(signal, ceiling)
  let res: Response
  try {
    res = await fetch(`${API_PREFIX}${path}`, {
      credentials: 'include',
      headers: mergedHeaders,
      signal: attempt.signal,
      ...requestInit,
    })
  } catch (error) {
    if (attempt.timedOut() && isAbortError(error)) throw new ApiTimeoutError(ceiling as number)
    throw error
  } finally {
    attempt.cleanup()
  }
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
