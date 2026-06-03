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
    path: '/admin/workshops',
    name: 'admin-workshops',
    component: () => import('@/shared/views/AdminWorkshopsView.vue'),
  },
  {
    path: '/admin/catalog',
    name: 'admin-catalog',
    component: () => import('@/shared/views/AdminCatalogView.vue'),
  },
  {
    path: '/admin/workshops/:workshop_id',
    name: 'admin-workshop-detail',
    component: () => import('@/shared/views/AdminWorkshopDetailView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'admin-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
  },
]
