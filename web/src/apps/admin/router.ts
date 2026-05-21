import { createRouter, createWebHistory } from 'vue-router'
import { installAuthGuard } from '@/shared/guards'
import AdminLayout from './layout/AdminLayout.vue'
import { useAdminAuth } from './store'

const router = createRouter({
  history: createWebHistory('/admin.html'),
  routes: [
    { path: '/', redirect: '/admin' },
    {
      path: '/auth/login',
      name: 'login',
      component: () => import('./views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/auth/change-password',
      name: 'change-password',
      component: () => import('./views/ChangePasswordView.vue'),
    },
    {
      path: '/admin',
      component: AdminLayout,
      children: [
        { path: '', name: 'dashboard', component: () => import('./views/DashboardView.vue') },
        {
          path: 'workshops',
          name: 'workshops',
          component: () => import('./views/WorkshopsView.vue'),
        },
        {
          path: 'workshops/:id',
          name: 'workshop-detail',
          component: () => import('./views/WorkshopDetailView.vue'),
        },
        {
          path: 'materials',
          name: 'materials',
          component: () => import('./views/MaterialsView.vue'),
        },
        { path: 'platform/jobs', name: 'jobs', component: () => import('./views/JobsView.vue') },
        {
          path: 'platform/errors',
          name: 'errors',
          component: () => import('./views/ErrorsView.vue'),
        },
        {
          path: 'platform/users',
          name: 'operators',
          component: () => import('./views/PlatformUsersView.vue'),
        },
        { path: 'audit', name: 'audit', component: () => import('./views/AuditView.vue') },
        { path: 'profile', name: 'profile', component: () => import('./views/ProfileView.vue') },
        {
          path: 'notifications',
          name: 'notifications',
          component: () => import('./views/NotificationsView.vue'),
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/shared/ui/NotFoundView.vue'),
    },
  ],
})

installAuthGuard(router, {
  loginRoute: '/auth/login',
  changePasswordRoute: '/auth/change-password',
  homeRoute: '/admin',
  useAuth: () => useAdminAuth(),
})

export default router
