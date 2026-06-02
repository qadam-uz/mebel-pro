import '@/assets/main.css'

import { createPinia } from 'pinia'
import { createApp } from 'vue'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import RoleApp from '@/shared/components/RoleApp.vue'
import { roleConfigKey, type RoleConfig } from '@/shared/app/roleConfig'

export function resolveHistoryBase(localBase: string, pathname = window.location.pathname): string {
  const normalized = localBase.endsWith('/') ? localBase.slice(0, -1) : localBase
  return pathname === normalized || pathname.startsWith(`${normalized}/`) ? `${normalized}/` : '/'
}

export function mountRoleApp(config: RoleConfig, routes: RouteRecordRaw[], localBase: string) {
  const router = createRouter({
    history: createWebHistory(resolveHistoryBase(localBase)),
    routes,
    scrollBehavior: () => ({ top: 0 }),
  })

  const app = createApp(RoleApp)
  app.provide(roleConfigKey, config)
  app.use(createPinia())
  app.use(router)
  app.mount('#app')
}
