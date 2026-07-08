import '@/assets/main.css'

import { createPinia } from 'pinia'
import { createApp } from 'vue'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { configureSession } from '@/shared/api/client'
import RoleApp from '@/shared/components/RoleApp.vue'
import { roleConfigKey, type RoleConfig, type RoleKey } from '@/shared/app/roleConfig'
import {
  canAccessWorkshopRoute,
  type WorkshopRouteRequirement,
} from '@/shared/app/workshopPermissions'
import { useAuthStore, type MeResponse } from '@/shared/stores/auth'
import { useCuttingStore } from '@/shared/stores/cutting'

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

function normalizeRedirect(
  redirect: RouteRecordRaw['redirect'],
  localBase: string,
  historyBase: string,
) {
  if (typeof redirect !== 'string') return redirect
  return normalizeRolePath(redirect, localBase, historyBase)
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
