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

export function mountRoleApp(config: RoleConfig, routes: RouteRecordRaw[], localBase: string) {
  const pinia = createPinia()
  const router = createRouter({
    history: createWebHistory(resolveHistoryBase(localBase)),
    routes,
    scrollBehavior: () => ({ top: 0 }),
  })
  const auth = useAuthStore(pinia)

  router.beforeEach(async (to) => {
    await auth.restore()
    const isAuthRoute = to.meta.layout === 'auth'
    if (isAuthRoute) {
      if (auth.isAllowedFor(config.role)) return config.homePath
      return true
    }
    if (!auth.isAllowedFor(config.role)) {
      return { path: config.loginPath, query: { redirect: to.fullPath } }
    }
    if (auth.me?.password_reset_required && to.path !== config.profilePath) {
      return { path: config.profilePath }
    }
    return true
  })

  const app = createApp(RoleApp)
  app.provide(roleConfigKey, config)
  app.use(pinia)
  app.use(router)
  app.mount('#app')
}
