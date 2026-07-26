import '@/assets/main.css'

import { createPinia } from 'pinia'
import { createApp } from 'vue'
import {
  createRouter,
  createWebHistory,
  type NavigationGuardNext,
  type NavigationGuardWithThis,
  type RouteLocationRaw,
  type RouteRecordRaw,
} from 'vue-router'

import { configureSession } from '@/shared/api/client'
import RoleApp from '@/shared/components/RoleApp.vue'
import { roleConfigKey, type RoleConfig, type RoleKey } from '@/shared/app/roleConfig'
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

export function roleDocumentTitle(pageTitle: unknown, config: RoleConfig): string {
  const title =
    typeof pageTitle === 'string' && pageTitle.trim() ? pageTitle.trim() : config.dashboardTitle
  return `${title} — ${config.productLabel} · ${config.roleLabel}`
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

export function mountRoleApp(config: RoleConfig, routes: RouteRecordRaw[], localBase: string) {
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
    document.title = roleDocumentTitle(to.meta.title, roleConfig)
    if (roleConfig.role === 'admin') focusAdminContent(to.meta)
  })

  const app = createApp(RoleApp)
  app.provide(roleConfigKey, roleConfig)
  app.use(pinia)
  app.use(router)
  app.mount('#app')
}
