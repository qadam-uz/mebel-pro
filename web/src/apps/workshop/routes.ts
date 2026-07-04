import type { RouteRecordRaw } from 'vue-router'

import { workshopPermissions as p } from '@/shared/app/workshopPermissions'

const orderAccess = [p.manageOrders]
const orderDetailAccess = [p.viewDashboard, p.manageOrders, p.processProduction]
const productionAccess = [p.processProduction, p.manageOrders]
const financeAccess = [p.manageFinance, p.viewFinanceReports]
export const workshopRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/workshop',
  },
  {
    path: '/auth/login',
    name: 'workshop-login',
    component: () => import('@/shared/views/WorkshopLoginView.vue'),
    meta: { layout: 'auth', title: 'Kirish' },
  },
  {
    path: '/workshop',
    name: 'workshop-home',
    component: () => import('@/shared/views/WorkshopDashboardView.vue'),
    meta: { title: 'Asosiy' },
  },
  {
    path: '/workshop/profile',
    name: 'workshop-profile',
    component: () => import('@/shared/views/WorkshopProfileView.vue'),
    meta: { title: 'Mening profilim' },
  },
  {
    path: '/workshop/orders',
    name: 'workshop-orders',
    component: () => import('@/shared/views/WorkshopOrdersView.vue'),
    meta: { title: 'Buyurtmalar', workshopAccess: { any: orderAccess } },
  },
  {
    path: '/workshop/orders/:order_id',
    name: 'workshop-order-detail',
    component: () => import('@/shared/views/WorkshopOrderDetailView.vue'),
    meta: { title: 'Buyurtma tafsilotlari', workshopAccess: { any: orderDetailAccess } },
  },
  {
    path: '/workshop/cutting',
    name: 'workshop-cutting-queue',
    component: () => import('@/shared/views/WorkshopCuttingQueueView.vue'),
    meta: { title: 'Kesish navbati', workshopAccess: { any: productionAccess } },
  },
  {
    path: '/workshop/banding',
    name: 'workshop-banding-queue',
    component: () => import('@/shared/views/WorkshopBandingQueueView.vue'),
    meta: { title: 'Krom navbati', workshopAccess: { any: productionAccess } },
  },
  {
    path: '/workshop/inventory',
    name: 'workshop-inventory',
    component: () => import('@/shared/views/WorkshopInventoryView.vue'),
    meta: { title: 'Ombor', workshopAccess: { any: [p.manageInventory] } },
  },
  {
    path: '/workshop/catalog',
    name: 'workshop-catalog',
    component: () => import('@/shared/views/WorkshopCatalogView.vue'),
    meta: { title: 'Material katalogi', workshopAccess: { any: [p.manageCatalog] } },
  },
  {
    path: '/workshop/settings/users',
    name: 'workshop-users',
    component: () => import('@/shared/views/WorkshopUsersView.vue'),
    meta: { title: 'Xodimlar', workshopAccess: { ownerOnly: true } },
  },
  {
    path: '/workshop/settings',
    name: 'workshop-settings',
    component: () => import('@/shared/views/WorkshopSettingsView.vue'),
    meta: { title: 'Sozlamalar', workshopAccess: { ownerOnly: true } },
  },
  {
    path: '/workshop/branches',
    name: 'workshop-branches',
    component: () => import('@/shared/views/WorkshopBranchesView.vue'),
    meta: { title: 'Filiallar', workshopAccess: { ownerOnly: true } },
  },
  {
    path: '/workshop/branches/:branch_id',
    name: 'workshop-branch-detail',
    component: () => import('@/shared/views/WorkshopBranchDetailView.vue'),
    meta: {
      title: 'Filial tafsilotlari',
      workshopAccess: { ownerOnly: true },
    },
  },
  {
    path: '/workshop/finance/income',
    name: 'workshop-finance-income',
    component: () => import('@/shared/views/WorkshopFinanceExpensesView.vue'),
    meta: { title: 'Tushum', workshopAccess: { any: [p.manageFinance] } },
  },
  {
    path: '/workshop/finance/expenses',
    name: 'workshop-finance-expenses',
    component: () => import('@/shared/views/WorkshopFinanceExpensesView.vue'),
    meta: { title: 'Tushum va xarajat', workshopAccess: { any: [p.manageFinance] } },
  },
  {
    path: '/workshop/finance/production',
    name: 'workshop-finance-production',
    component: () => import('@/shared/views/WorkshopFinanceProductionView.vue'),
    meta: { title: 'Ishlab chiqarish hisobotlari', workshopAccess: { any: financeAccess } },
  },
  {
    path: '/workshop/settings/users/:user_id',
    name: 'workshop-user-detail',
    component: () => import('@/shared/views/WorkshopUserDetailView.vue'),
    meta: { title: 'Xodim tafsilotlari', workshopAccess: { ownerOnly: true } },
  },
  {
    path: '/workshop/notifications',
    name: 'workshop-notifications',
    component: () => import('@/shared/views/WorkshopNotificationsView.vue'),
    meta: { title: 'Bildirishnomalar' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'workshop-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
    meta: { title: 'Sahifa topilmadi' },
  },
]
