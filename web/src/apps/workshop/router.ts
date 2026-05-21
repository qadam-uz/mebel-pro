import { createRouter, createWebHistory } from 'vue-router'
import { installAuthGuard } from '@/shared/guards'
import WorkshopLayout from './layout/WorkshopLayout.vue'
import { useWorkshopAuth } from './store'

const router = createRouter({
  history: createWebHistory('/workshop.html'),
  routes: [
    { path: '/', redirect: '/workshop' },
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
      path: '/workshop',
      component: WorkshopLayout,
      children: [
        { path: '', name: 'dashboard', component: () => import('./views/DashboardView.vue') },
        { path: 'orders', name: 'orders', component: () => import('./views/OrdersView.vue') },
        {
          path: 'orders/:id',
          name: 'order-detail',
          component: () => import('./views/OrderDetailView.vue'),
        },
        {
          path: 'cutting',
          name: 'cutting',
          component: () => import('./views/CuttingQueueView.vue'),
        },
        {
          path: 'banding',
          name: 'banding',
          component: () => import('./views/BandingQueueView.vue'),
        },
        {
          path: 'branches',
          name: 'branches',
          component: () => import('./views/BranchesView.vue'),
          meta: { ownerOnly: true },
        },
        {
          path: 'branches/:id',
          name: 'branch-detail',
          component: () => import('./views/branch/BranchDetailView.vue'),
          meta: { ownerOnly: true },
        },
        {
          path: 'finance',
          name: 'finance',
          component: () => import('./views/finance/FinanceView.vue'),
        },
        {
          path: 'finance/income',
          name: 'finance-income',
          component: () => import('./views/finance/FinanceView.vue'),
        },
        {
          path: 'finance/expenses',
          name: 'finance-expenses',
          component: () => import('./views/finance/FinanceView.vue'),
        },
        {
          path: 'finance/production',
          name: 'finance-production',
          component: () => import('./views/finance/FinanceView.vue'),
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('./views/SettingsView.vue'),
          meta: { ownerOnly: true },
        },
        {
          path: 'settings/users',
          name: 'users',
          component: () => import('./views/users/UsersView.vue'),
          meta: { ownerOnly: true },
        },
        {
          path: 'settings/users/:id',
          name: 'user-detail',
          component: () => import('./views/users/UserDetailView.vue'),
          meta: { ownerOnly: true },
        },
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
  homeRoute: '/workshop',
  useAuth: () => useWorkshopAuth(),
})

export default router
