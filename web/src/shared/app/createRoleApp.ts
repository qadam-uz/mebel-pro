import '@/assets/main.css'

import { createPinia } from 'pinia'
import { createApp } from 'vue'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import RoleApp from '@/shared/components/RoleApp.vue'
import { roleConfigKey, type RoleConfig } from '@/shared/app/roleConfig'
import { useAuthStore } from '@/shared/stores/auth'

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
    return true
  })

  const app = createApp(RoleApp)
  app.provide(roleConfigKey, roleConfig)
  app.use(pinia)
  app.use(router)
  app.mount('#app')
}
