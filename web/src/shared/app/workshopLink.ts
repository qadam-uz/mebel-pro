/**
 * Absolute `/w/{code}` URLs, built from the **workshop** app.
 *
 * The "Mijoz havolasi" card renders inside the workshop SPA, and the link it
 * prints opens the **client** SPA — a different place in both environments, so
 * `window.location.origin` on its own is wrong in both:
 *
 * - **production** — the Caddy edge routes by subdomain (`deploy/Caddyfile`):
 *   the workshop app is `workshop.<domain>`, the client app is `app.<domain>`.
 * - **dev** — one Vite server hosts all three SPAs under a role base path, so
 *   the workshop app is `/workshop/...` and the client app is `/client/...`.
 *
 * Derived rather than configured, deliberately: the host scheme is the deploy's
 * contract, and `web/.env.*.example` still needs no public build-time config.
 * A deploy that serves the client app somewhere else falls back to the current
 * origin, which is at worst a link the owner can see is wrong.
 */

const WORKSHOP_HOST_PREFIX = 'workshop.'
const CLIENT_HOST_PREFIX = 'app.'
const WORKSHOP_DEV_BASE = '/workshop'
const CLIENT_DEV_BASE = '/client'

export function clientAppBase(
  origin: string = typeof window === 'undefined' ? '' : window.location.origin,
  pathname: string = typeof window === 'undefined' ? '/' : window.location.pathname,
  isDev: boolean = import.meta.env.DEV,
): string {
  if (isDev) {
    const mountedUnderRoleBase =
      pathname === WORKSHOP_DEV_BASE || pathname.startsWith(`${WORKSHOP_DEV_BASE}/`)
    return mountedUnderRoleBase ? `${origin}${CLIENT_DEV_BASE}` : origin
  }
  try {
    const url = new URL(origin)
    if (url.hostname.startsWith(WORKSHOP_HOST_PREFIX)) {
      url.hostname = `${CLIENT_HOST_PREFIX}${url.hostname.slice(WORKSHOP_HOST_PREFIX.length)}`
      return url.origin
    }
  } catch {
    // A non-URL origin (never in a browser) leaves the base as given.
  }
  return origin
}

/**
 * The link a workshop prints. Omit `branchNo` for the workshop-level link that
 * settings shows; pass it for the QR a branch puts on its counter.
 */
export function workshopLinkUrl(
  code: string,
  branchNo?: number | null,
  origin?: string,
  pathname?: string,
  isDev?: boolean,
): string {
  const suffix = branchNo == null ? '' : `/${branchNo}`
  return `${clientAppBase(origin, pathname, isDev)}/w/${code}${suffix}`
}
