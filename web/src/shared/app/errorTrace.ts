// Rendering helpers for the trace_id shown next to error states. The backend
// stamps trace_id on every error body (backend/app/core/errors.py), so a
// missing trace on an API failure means the response never came from the app —
// a connection or proxy failure, not a lookup miss.

/**
 * Standalone diagnostic line for a load-error state: the trace when the
 * backend answered, otherwise the connection cause. Only for errors that are
 * always API-sourced — never next to local validation messages.
 */
export function traceLine(traceId: string | null | undefined): string {
  return traceId ? `trace_id: ${traceId}` : "Serverga ulanib bo'lmadi"
}

/**
 * Inline " · trace_id: …" suffix for an action-error banner; empty when there
 * is no trace. Action banners can also carry local validation hints that never
 * hit the API, so this deliberately does not claim a connection failure.
 */
export function traceSuffix(traceId: string | null | undefined): string {
  return traceId ? ` · trace_id: ${traceId}` : ''
}
