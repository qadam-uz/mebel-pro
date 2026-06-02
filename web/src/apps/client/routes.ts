import type { RouteRecordRaw } from 'vue-router'

export const clientRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/c',
  },
  {
    path: '/auth/login',
    name: 'client-login',
    component: () => import('@/shared/views/LoginView.vue'),
    meta: { layout: 'auth' },
  },
  {
    path: '/c',
    name: 'client-home',
    component: () => import('@/shared/views/DashboardView.vue'),
  },
  {
    path: '/c/profile',
    name: 'client-profile',
    component: () => import('@/shared/views/ProfileView.vue'),
  },
  {
    path: '/c/cutting/drafts',
    name: 'client-cutting-drafts',
    component: () => import('@/shared/views/DraftsView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'client-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
  },
]
