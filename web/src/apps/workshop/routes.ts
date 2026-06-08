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
    path: '/workshop/orders',
    name: 'workshop-orders',
    component: () => import('@/shared/views/WorkshopOrdersView.vue'),
  },
  {
    path: '/workshop/orders/:order_id',
    name: 'workshop-order-detail',
    component: () => import('@/shared/views/WorkshopOrderDetailView.vue'),
  },
  {
    path: '/workshop/cutting',
    name: 'workshop-cutting-queue',
    component: () => import('@/shared/views/WorkshopCuttingQueueView.vue'),
  },
  {
    path: '/workshop/banding',
    name: 'workshop-banding-queue',
    component: () => import('@/shared/views/WorkshopBandingQueueView.vue'),
  },
  {
    path: '/workshop/settings/users',
    name: 'workshop-users',
    component: () => import('@/shared/views/WorkshopUsersView.vue'),
  },
  {
    path: '/workshop/branches',
    name: 'workshop-branches',
    component: () => import('@/shared/views/WorkshopBranchesView.vue'),
  },
  {
    path: '/workshop/branches/:branch_id',
    name: 'workshop-branch-detail',
    component: () => import('@/shared/views/WorkshopBranchDetailView.vue'),
  },
  {
    path: '/workshop/cutting-plans',
    name: 'workshop-cutting-plans',
    component: () => import('@/shared/views/WorkshopCuttingPlansView.vue'),
  },
  {
    path: '/workshop/finance',
    name: 'workshop-finance',
    component: () => import('@/shared/views/WorkshopFinanceView.vue'),
  },
  {
    path: '/workshop/finance/income',
    name: 'workshop-finance-income',
    component: () => import('@/shared/views/WorkshopFinanceIncomeView.vue'),
  },
  {
    path: '/workshop/finance/expenses',
    name: 'workshop-finance-expenses',
    component: () => import('@/shared/views/WorkshopFinanceExpensesView.vue'),
  },
  {
    path: '/workshop/finance/production',
    name: 'workshop-finance-production',
    component: () => import('@/shared/views/WorkshopFinanceProductionView.vue'),
  },
  {
    path: '/workshop/cutting-plans/:result_id',
    name: 'workshop-cutting-plan-detail',
    component: () => import('@/shared/views/WorkshopCuttingPlanDetailView.vue'),
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
