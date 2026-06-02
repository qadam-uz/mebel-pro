import type { RouteRecordRaw } from 'vue-router'

export const adminRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/admin',
  },
  {
    path: '/auth/login',
    name: 'admin-login',
    component: () => import('@/shared/views/LoginView.vue'),
    meta: { layout: 'auth' },
  },
  {
    path: '/admin',
    name: 'admin-home',
    component: () => import('@/shared/views/DashboardView.vue'),
  },
  {
    path: '/admin/profile',
    name: 'admin-profile',
    component: () => import('@/shared/views/ProfileView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'admin-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
  },
]
