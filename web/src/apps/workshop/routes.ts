import type { RouteLocationNormalized, RouteRecordRaw } from 'vue-router'

import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { useCuttingStore } from '@/shared/stores/cutting'
import { workshopCuttingEditorAdapter } from '@/apps/workshop/cuttingEditorAdapter'

// New-editor guard: the walk-in client must be resolved before the editor opens.
// After a mid-flow reload the store is empty, so rehydrate from the `client`
// query param; with neither, bounce back to the walk-in step.
async function ensureWalkInClient(to: RouteLocationNormalized) {
  const cutting = useCuttingStore()
  if (cutting.walkInClient) return true
  const clientId = typeof to.query.client === 'string' ? to.query.client : null
  if (clientId) {
    try {
      await cutting.loadWalkInClient(clientId)
      return true
    } catch {
      // fall through to the redirect
    }
  }
  return { path: '/workshop/orders/new' }
}

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
  // Staff order-creation flow. All under /workshop/orders/* and declared BEFORE
  // the `:order_id` detail route so `new`/`cutting` aren't captured as order ids.
  {
    path: '/workshop/orders/new',
    name: 'workshop-order-new-walkin',
    component: () => import('@/shared/views/WorkshopWalkInClientView.vue'),
    meta: { title: 'Yangi buyurtma', workshopAccess: { any: orderAccess } },
  },
  {
    path: '/workshop/orders/new/cutting',
    name: 'workshop-order-cutting-new',
    component: () => import('@/shared/views/CuttingEditorView.vue'),
    beforeEnter: ensureWalkInClient,
    meta: {
      title: 'Kesim chizmasi',
      workshopAccess: { any: orderAccess },
      cuttingEditorAdapter: workshopCuttingEditorAdapter,
    },
  },
  {
    path: '/workshop/orders/cutting/:id',
    name: 'workshop-order-cutting-editor',
    component: () => import('@/shared/views/CuttingEditorView.vue'),
    meta: {
      title: 'Kesim chizmasi',
      workshopAccess: { any: orderAccess },
      cuttingEditorAdapter: workshopCuttingEditorAdapter,
    },
  },
  {
    path: '/workshop/orders/cutting/:id/result',
    name: 'workshop-order-cutting-result',
    component: () => import('@/shared/views/CuttingResultView.vue'),
    meta: {
      title: 'Kesish natijasi',
      workshopAccess: { any: orderAccess },
      cuttingEditorAdapter: workshopCuttingEditorAdapter,
    },
  },
  {
    path: '/workshop/orders/new/:draft_id/checkout',
    name: 'workshop-order-checkout',
    component: () => import('@/shared/views/WorkshopOrderCheckoutView.vue'),
    meta: { title: 'Buyurtmani rasmiylashtirish', workshopAccess: { any: orderAccess } },
  },
  // Saved walk-in drafts — unfinished cuttings staff can resume. Declared before
  // `:order_id` so the literal `drafts` segment isn't captured as an order id.
  {
    path: '/workshop/orders/drafts',
    name: 'workshop-order-drafts',
    component: () => import('@/shared/views/WorkshopDraftsView.vue'),
    meta: { title: 'Saqlangan chizmalar', workshopAccess: { any: orderAccess } },
  },
  // Revision review: current vs. new price before applying an order edit
  // (docs/ref/features/orders.md "Revising a placed order").
  {
    path: '/workshop/orders/edit/:draft_id/review',
    name: 'workshop-order-edit-review',
    component: () => import('@/shared/views/WorkshopOrderEditReviewView.vue'),
    meta: { title: 'Tahrirni saqlash', workshopAccess: { any: orderAccess } },
  },
  {
    path: '/workshop/orders/:order_id',
    name: 'workshop-order-detail',
    component: () => import('@/shared/views/WorkshopOrderDetailView.vue'),
    meta: { title: 'Buyurtma tafsilotlari', workshopAccess: { any: orderDetailAccess } },
  },
  // The tabbed "Ishlarim" workspace split into the two station pages below;
  // its URL stays alive as a redirect so old bookmarks and ?station= links
  // land on the right station.
  {
    path: '/workshop/production',
    redirect: (to) =>
      to.query.station === 'banding'
        ? { path: '/workshop/banding' }
        : { path: '/workshop/cutting' },
  },
  {
    path: '/workshop/production/:order_id',
    name: 'workshop-production-job',
    component: () => import('@/shared/views/WorkshopProductionJobView.vue'),
    meta: { title: 'Chizma', workshopAccess: { any: productionAccess } },
  },
  {
    path: '/workshop/cutting',
    name: 'workshop-cutting',
    component: () => import('@/shared/views/WorkshopProductionView.vue'),
    props: { station: 'cutting' },
    meta: { title: 'Kesish', workshopAccess: { any: productionAccess } },
  },
  {
    path: '/workshop/banding',
    name: 'workshop-banding',
    component: () => import('@/shared/views/WorkshopProductionView.vue'),
    props: { station: 'banding' },
    meta: { title: 'Krom', workshopAccess: { any: productionAccess } },
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
    path: '/workshop/finance/debts',
    name: 'workshop-finance-debts',
    component: () => import('@/shared/views/WorkshopFinanceDebtsView.vue'),
    meta: { title: 'Qarzdorlik', workshopAccess: { any: [p.manageFinance] } },
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
