import type { RouteRecordRaw } from 'vue-router'

export const workshopRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/workshop',
  },
  {
    path: '/auth/login',
    name: 'workshop-login',
    component: () => import('@/shared/views/LoginView.vue'),
    meta: { layout: 'auth' },
  },
  {
    path: '/workshop',
    name: 'workshop-home',
    component: () => import('@/shared/views/DashboardView.vue'),
  },
  {
    path: '/workshop/profile',
    name: 'workshop-profile',
    component: () => import('@/shared/views/ProfileView.vue'),
  },
  {
    path: '/workshop/settings/users',
    name: 'workshop-users',
    component: () => import('@/shared/views/WorkshopUsersView.vue'),
  },
  {
    path: '/workshop/settings/users/:user_id',
    name: 'workshop-user-detail',
    component: () => import('@/shared/views/WorkshopUserDetailView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'workshop-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
  },
]
