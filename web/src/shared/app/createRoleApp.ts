import '@/assets/main.css'

import { createPinia } from 'pinia'
import { createApp, watch } from 'vue'
import {
  createRouter,
  createWebHistory,
  type NavigationGuardNext,
  type NavigationGuardWithThis,
  type RouteLocationRaw,
  type RouteRecordRaw,
} from 'vue-router'

import { configureSession } from '@/shared/api/client'
import { i18n, initialLocale, setLocale } from '@/shared/i18n'
import RoleApp from '@/shared/components/RoleApp.vue'
import {
  roleConfigKey,
  roleMessageKey,
  type RoleConfig,
  type RoleKey,
} from '@/shared/app/roleConfig'
import {
  canAccessWorkshopRoute,
  type WorkshopRouteRequirement,
} from '@/shared/app/workshopPermissions'
import { useAuthStore, type MeResponse } from '@/shared/stores/auth'
import { useCuttingStore } from '@/shared/stores/cutting'
import { useWorkshopStore } from '@/shared/stores/workshop'

export function resolveHistoryBase(
  localBase: string,
  pathname = window.location.pathname,
  isDev = import.meta.env.DEV,
): string {
  if (!isDev) return '/'
  const normalized = localBase.endsWith('/') ? localBase.slice(0, -1) : localBase
  return pathname === normalized || pathname.startsWith(`${normalized}/`) ? `${normalized}/` : '/'
}

export function normalizeRolePath(path: string, localBase: string, historyBase: string): string {
  if (historyBase === '/') return path

  const normalized = localBase.endsWith('/') ? localBase.slice(0, -1) : localBase
  if (path === normalized) return '/'
  if (path.startsWith(`${normalized}/`)) return path.slice(normalized.length)
  return path
}

// Redirect targets are route paths too — they need the same dev-base stripping
// as route records, whatever shape the redirect takes (string, object with a
// path, or a function returning either). Named-route targets pass through.
function normalizeRedirectTarget(
  target: RouteLocationRaw,
  localBase: string,
  historyBase: string,
): RouteLocationRaw {
  if (typeof target === 'string') return normalizeRolePath(target, localBase, historyBase)
  if ('path' in target && typeof target.path === 'string') {
    return { ...target, path: normalizeRolePath(target.path, localBase, historyBase) }
  }
  return target
}

function normalizeRedirect(
  redirect: RouteRecordRaw['redirect'],
  localBase: string,
  historyBase: string,
): RouteRecordRaw['redirect'] {
  if (typeof redirect === 'function') {
    return (to, from) => normalizeRedirectTarget(redirect(to, from), localBase, historyBase)
  }
  if (redirect) return normalizeRedirectTarget(redirect, localBase, historyBase)
  return redirect
}

// A `beforeEnter` guard that bounces elsewhere returns a route target as well,
// and it is written against the same absolute, role-prefixed paths as the route
// records around it. Without this it was the one target the dev-base stripping
// missed, so the guard sent the browser to a path that no longer existed and
// the navigation landed on nothing (QAD-178).
function normalizeGuard(
  guard: NavigationGuardWithThis<undefined>,
  localBase: string,
  historyBase: string,
): NavigationGuardWithThis<undefined> {
  // vue-router reads a guard's arity: one declaring the third `next` parameter
  // drives navigation through that callback instead of a return value, so there
  // is nothing to normalize and re-wrapping it would change how it is called.
  if (guard.length >= 3) return guard
  // Unreachable by the arity check above — a guard that ignores `next` in its
  // signature has no way to call it.
  const next: NavigationGuardNext = () => {
    throw new Error('Route guard called next() without declaring it')
  }

  // Exactly two declared parameters: vue-router must keep treating the return
  // value, not a `next` call, as this guard's verdict.
  return async function (this: undefined, to, from) {
    const result = await guard.call(this, to, from, next)
    if (result == null || typeof result === 'boolean' || result instanceof Error) return result
    return normalizeRedirectTarget(result, localBase, historyBase)
  }
}

function normalizeBeforeEnter(
  beforeEnter: RouteRecordRaw['beforeEnter'],
  localBase: string,
  historyBase: string,
): RouteRecordRaw['beforeEnter'] {
  if (!beforeEnter) return beforeEnter
  if (Array.isArray(beforeEnter)) {
    return beforeEnter.map((guard) => normalizeGuard(guard, localBase, historyBase))
  }
  return normalizeGuard(beforeEnter, localBase, historyBase)
}

export function normalizeRoleRoutes(
  routes: RouteRecordRaw[],
  localBase: string,
  historyBase: string,
): RouteRecordRaw[] {
  return routes.flatMap((route) => {
    const nextRoute = {
      ...route,
      path: normalizeRolePath(route.path, localBase, historyBase),
      redirect: normalizeRedirect(route.redirect, localBase, historyBase),
      beforeEnter: normalizeBeforeEnter(route.beforeEnter, localBase, historyBase),
    } as RouteRecordRaw & { children?: RouteRecordRaw[] }

    if (route.children) {
      nextRoute.children = normalizeRoleRoutes(route.children, localBase, historyBase)
    }

    if (nextRoute.path === '/' && nextRoute.redirect === '/') return []
    return [nextRoute]
  })
}

export function normalizeRoleConfig(
  config: RoleConfig,
  localBase: string,
  historyBase: string,
): RoleConfig {
  const normalize = (path: string) => normalizeRolePath(path, localBase, historyBase)

  return {
    ...config,
    homePath: normalize(config.homePath),
    loginPath: normalize(config.loginPath),
    profilePath: normalize(config.profilePath),
    primaryActionTo: normalize(config.primaryActionTo),
    nav: config.nav.map((item) => ({ ...item, to: normalize(item.to) })),
  }
}

/** A route declares `meta.titleKey`; the tab title is resolved here so it
 *  follows the active locale rather than freezing at whatever was loaded when
 *  the route module was first evaluated. */
export function roleDocumentTitle(
  titleKey: unknown,
  config: RoleConfig,
  translate: (key: string) => string = (key) => i18n.global.t(key),
): string {
  const key =
    typeof titleKey === 'string' && titleKey.trim()
      ? titleKey.trim()
      : roleMessageKey(config.role, 'dashboardTitle')
  return `${translate(key)} — ${config.productLabel} · ${translate(roleMessageKey(config.role, 'label'))}`
}

export function roleRoutePermissionAllowed(
  role: RoleKey,
  me: MeResponse | null,
  meta: Record<string, unknown>,
  params: Record<string, unknown> = {},
): boolean {
  if (role !== 'workshop') return true
  return canAccessWorkshopRoute(
    me,
    meta.workshopAccess as WorkshopRouteRequirement | null | undefined,
    params,
  )
}

function focusAdminContent(toMeta: Record<string, unknown>) {
  if (toMeta.layout === 'auth') return
  requestAnimationFrame(() => {
    document.getElementById('admin-content')?.focus({ preventScroll: true })
  })
}

// Every route component is a lazy `import()` of a content-hashed chunk. A deploy
// replaces `dist/`, so a tab left open across one is still holding the *old*
// filenames: the import 404s, and vue-router aborts the navigation with nothing
// on screen. The symptom is a shell that looks alive — the page under it still
// works — while every sidebar link is dead until the operator happens to reload.
//
// The three engines word the same failure differently, and none of them exposes
// a code, so the message is all there is to match on.
const STALE_CHUNK_MESSAGES = [
  'failed to fetch dynamically imported module', // Chromium
  'error loading dynamically imported module', // Firefox
  'importing a module script failed', // Safari
]

export function isStaleChunkError(error: unknown): boolean {
  const message = (error instanceof Error ? error.message : String(error)).toLowerCase()
  return STALE_CHUNK_MESSAGES.some((phrase) => message.includes(phrase))
}

const STALE_RELOAD_KEY = 'mp-stale-chunk-reload'

/** Per-tab, so one tab recovering never suppresses another's reload. */
function tabStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage
  } catch {
    return null
  }
}

/**
 * Decides what to do with a failed navigation. Returns the path to hard-load,
 * or `null` to let the failure stand.
 *
 * Recovery is a full page load **of the target**, not a bare reload: the click
 * still lands where it was aimed, and the fresh HTML carries the new chunk
 * names. It happens at most once per target per tab — if the chunk is still
 * missing after that, the deploy itself is broken and a reload loop would be
 * worse for the operator than a dead link.
 */
export function staleChunkRecovery(
  error: unknown,
  targetPath: string,
  storage: Storage | null = tabStorage(),
): string | null {
  if (!isStaleChunkError(error)) return null
  if (storage?.getItem(STALE_RELOAD_KEY) === targetPath) return null
  storage?.setItem(STALE_RELOAD_KEY, targetPath)
  return targetPath
}

/** Called once a navigation lands, so a later deploy can recover in this tab too. */
export function clearStaleChunkMark(storage: Storage | null = tabStorage()): void {
  storage?.removeItem(STALE_RELOAD_KEY)
}

export async function mountRoleApp(
  config: RoleConfig,
  routes: RouteRecordRaw[],
  localBase: string,
) {
  // Before anything renders: a locale switched in a previous session must be in
  // place for the first paint, not applied over an Uzbek flash.
  await setLocale(initialLocale())

  const historyBase = resolveHistoryBase(localBase)
  const roleConfig = normalizeRoleConfig(config, localBase, historyBase)
  const pinia = createPinia()
  const router = createRouter({
    history: createWebHistory(historyBase),
    routes: normalizeRoleRoutes(routes, localBase, historyBase),
    scrollBehavior: () => ({ top: 0 }),
  })
  const auth = useAuthStore(pinia)

  // The shared cutting store defaults to the client API surface ('/client/*');
  // the workshop SPA flips it to the '/workshop/*' mirror once at bootstrap.
  // Each SPA owns its Pinia instance, so this can never leak across apps.
  if (roleConfig.role === 'workshop') {
    useCuttingStore(pinia).configureScope('workshop')
  }

  // A refused request means the grant set the shell was built from is stale —
  // the owner revoked something while this tab was open (QAD-172). Re-read the
  // principal and, for the workshop app, the branch context the sidebar is
  // built from; if the page the user is on is no longer allowed, send them
  // home. Server-side enforcement was never fooled; this is the screen catching
  // up. Serialized so a burst of 403s costs one round-trip.
  let revalidating: Promise<void> | null = null
  function revalidateAccess() {
    if (revalidating) return
    revalidating = (async () => {
      await auth.refreshMe()
      if (!auth.isAuthenticated) return
      if (roleConfig.role === 'workshop') {
        await useWorkshopStore(pinia)
          .loadBranchContext({ force: true })
          .catch(() => undefined)
      }
      const current = router.currentRoute.value
      if (current.meta.layout === 'auth') return
      if (!roleRoutePermissionAllowed(roleConfig.role, auth.me, current.meta, current.params)) {
        void router.replace(roleConfig.homePath)
      }
    })().finally(() => {
      revalidating = null
    })
  }

  // Transparent 401 handling (CB-08): the API client refreshes silently and
  // retries; if that fails (refreshSession has already cleared auth) it bounces
  // to login with a notice.
  configureSession({
    refresh: () => auth.refreshSession(),
    onExpired: () => {
      const current = router.currentRoute.value
      if (current.meta.layout === 'auth') return
      void router.push({
        path: roleConfig.loginPath,
        query: { redirect: current.fullPath, reason: 'session_expired' },
      })
    },
    onForbidden: revalidateAccess,
  })

  router.beforeEach(async (to) => {
    await auth.restore()
    const isAuthRoute = to.meta.layout === 'auth'
    if (isAuthRoute) {
      if (auth.isAllowedFor(roleConfig.role)) return roleConfig.homePath
      return true
    }
    if (!auth.isAllowedFor(roleConfig.role)) {
      return { path: roleConfig.loginPath, query: { redirect: to.fullPath } }
    }
    if (auth.me?.password_reset_required && to.path !== roleConfig.profilePath) {
      return { path: roleConfig.profilePath }
    }
    if (!roleRoutePermissionAllowed(roleConfig.role, auth.me, to.meta, to.params)) {
      return roleConfig.homePath
    }
    return true
  })

  router.afterEach((to) => {
    clearStaleChunkMark()
    document.title = roleDocumentTitle(to.meta.titleKey, roleConfig)
    if (roleConfig.role === 'admin') focusAdminContent(to.meta)
  })

  router.onError((error, to) => {
    const recoverTo = staleChunkRecovery(error, to.fullPath)
    if (recoverTo === null) return
    window.location.assign(recoverTo)
  })

  // Switching language mid-session must retitle the tab too — `afterEach` only
  // fires on navigation, and a user who stays put would keep the old language
  // in their tab strip and browser history.
  watch(i18n.global.locale, () => {
    document.title = roleDocumentTitle(router.currentRoute.value.meta.titleKey, roleConfig)
  })

  const app = createApp(RoleApp)
  app.provide(roleConfigKey, roleConfig)
  app.use(pinia)
  app.use(router)
  app.use(i18n)
  app.mount('#app')
}
