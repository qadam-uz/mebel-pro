/**
 * Sanitize a post-login `?redirect=` target.
 *
 * Returns `redirect` only when it is a safe **same-origin path**; otherwise `fallback`.
 * Rejects non-strings, anything not starting with `/`, protocol-relative (`//host`)
 * and backslash-smuggled (`/\host`) targets, and absolute/scheme URLs — all of which
 * a router could follow off-origin (open redirect).
 */
export function safeRedirectPath(redirect: unknown, fallback: string): string {
  if (typeof redirect !== 'string') return fallback
  if (!redirect.startsWith('/')) return fallback
  if (redirect.startsWith('//') || redirect.startsWith('/\\')) return fallback
  return redirect
}
