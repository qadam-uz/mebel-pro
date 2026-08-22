import type { RouteLocationNormalized, RouteRecordRaw } from 'vue-router'

import type { BranchScope } from '@/shared/app/branchScope'
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

/**
 * Every workshop route states how it relates to the topbar branch picker — the
 * type makes it a compile error to add one without a `branchScope` (see
 * `@/shared/app/branchScope`). `AppShell` reads it to decide whether the picker
 * is live or rendered disabled with a hint.
 */
type WorkshopRouteRecord = RouteRecordRaw & { meta: { branchScope: BranchScope } }

const orderAccess = [p.manageOrders]
const orderDetailAccess = [p.viewOrders, p.manageOrders, p.processProduction]
const productionAccess = [p.processProduction, p.manageOrders]
const financeAccess = [p.manageFinance, p.viewFinanceReports]
export const workshopRoutes: WorkshopRouteRecord[] = [
  {
    path: '/',
    redirect: '/workshop',
    meta: { branchScope: 'branch' },
  },
  {
    path: '/auth/login',
    name: 'workshop-login',
    component: () => import('@/shared/views/WorkshopLoginView.vue'),
    meta: { layout: 'auth', titleKey: 'routes.login', branchScope: 'workshop' },
  },
  {
    path: '/workshop',
    name: 'workshop-home',
    component: () => import('@/shared/views/WorkshopDashboardView.vue'),
    meta: { titleKey: 'routes.dashboard', branchScope: 'branch' },
  },
  {
    path: '/workshop/profile',
    name: 'workshop-profile',
    component: () => import('@/shared/views/WorkshopProfileView.vue'),
    meta: { titleKey: 'routes.myProfile', branchScope: 'workshop' },
  },
  {
    path: '/workshop/orders',
    name: 'workshop-orders',
    component: () => import('@/shared/views/WorkshopOrdersView.vue'),
    meta: {
      titleKey: 'routes.orders',
      workshopAccess: { any: orderAccess },
      branchScope: 'branch',
    },
  },
  // Staff order-creation flow. All under /workshop/orders/* and declared BEFORE
  // the `:order_id` detail route so `new`/`cutting` aren't captured as order ids.
  {
    path: '/workshop/orders/new',
    name: 'workshop-order-new-walkin',
    component: () => import('@/shared/views/WorkshopWalkInClientView.vue'),
    meta: {
      hideSearch: true,
      titleKey: 'routes.newOrder',
      workshopAccess: { any: orderAccess },
      branchScope: 'branch',
    },
  },
  {
    path: '/workshop/orders/new/cutting',
    name: 'workshop-order-cutting-new',
    component: () => import('@/shared/views/CuttingEditorView.vue'),
    beforeEnter: ensureWalkInClient,
    meta: {
      hideSearch: true,
      titleKey: 'routes.draft',
      workshopAccess: { any: orderAccess },
      cuttingEditorAdapter: workshopCuttingEditorAdapter,
      // The editor freezes its branch at mount and keeps its own in-page
      // control; a later topbar switch must not retarget the drawing.
      branchScope: 'entity',
    },
  },
  {
    path: '/workshop/orders/cutting/:id',
    name: 'workshop-order-cutting-editor',
    component: () => import('@/shared/views/CuttingEditorView.vue'),
    meta: {
      hideSearch: true,
      titleKey: 'routes.draft',
      workshopAccess: { any: orderAccess },
      cuttingEditorAdapter: workshopCuttingEditorAdapter,
      branchScope: 'entity',
    },
  },
  {
    path: '/workshop/orders/cutting/:id/result',
    name: 'workshop-order-cutting-result',
    component: () => import('@/shared/views/CuttingResultView.vue'),
    meta: {
      hideSearch: true,
      titleKey: 'routes.cuttingResult',
      workshopAccess: { any: orderAccess },
      cuttingEditorAdapter: workshopCuttingEditorAdapter,
      branchScope: 'entity',
    },
  },
  {
    path: '/workshop/orders/new/:draft_id/checkout',
    name: 'workshop-order-checkout',
    component: () => import('@/shared/views/WorkshopOrderCheckoutView.vue'),
    meta: {
      hideSearch: true,
      titleKey: 'routes.checkout',
      workshopAccess: { any: orderAccess },
      branchScope: 'entity',
    },
  },
  // Saved walk-in drafts — unfinished cuttings staff can resume. Declared before
  // `:order_id` so the literal `drafts` segment isn't captured as an order id.
  {
    path: '/workshop/orders/drafts',
    name: 'workshop-order-drafts',
    component: () => import('@/shared/views/WorkshopDraftsView.vue'),
    meta: {
      titleKey: 'routes.savedDrafts',
      workshopAccess: { any: orderAccess },
      branchScope: 'branch',
    },
  },
  // Revision review: current vs. new price before applying an order edit
  // (docs/ref/features/orders.md "Revising a placed order").
  {
    path: '/workshop/orders/edit/:draft_id/review',
    name: 'workshop-order-edit-review',
    component: () => import('@/shared/views/WorkshopOrderEditReviewView.vue'),
    meta: {
      titleKey: 'routes.editReview',
      workshopAccess: { any: orderAccess },
      branchScope: 'entity',
    },
  },
  {
    path: '/workshop/orders/:order_id',
    name: 'workshop-order-detail',
    component: () => import('@/shared/views/WorkshopOrderDetailView.vue'),
    meta: {
      titleKey: 'routes.orderDetail',
      workshopAccess: { any: orderDetailAccess },
      branchScope: 'entity',
    },
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
    meta: { branchScope: 'branch' },
  },
  {
    path: '/workshop/production/:order_id',
    name: 'workshop-production-job',
    component: () => import('@/shared/views/WorkshopProductionJobView.vue'),
    meta: {
      titleKey: 'routes.drawing',
      workshopAccess: { any: productionAccess },
      branchScope: 'entity',
    },
  },
  {
    path: '/workshop/cutting',
    name: 'workshop-cutting',
    component: () => import('@/shared/views/WorkshopProductionView.vue'),
    props: { station: 'cutting' },
    meta: {
      titleKey: 'routes.cutting',
      workshopAccess: { any: productionAccess },
      branchScope: 'branch',
    },
  },
  {
    path: '/workshop/banding',
    name: 'workshop-banding',
    component: () => import('@/shared/views/WorkshopProductionView.vue'),
    props: { station: 'banding' },
    meta: {
      titleKey: 'routes.banding',
      workshopAccess: { any: productionAccess },
      branchScope: 'branch',
    },
  },
  {
    path: '/workshop/inventory',
    name: 'workshop-inventory',
    component: () => import('@/shared/views/WorkshopInventoryView.vue'),
    meta: {
      titleKey: 'routes.inventory',
      workshopAccess: { any: [p.manageInventory] },
      branchScope: 'branch',
    },
  },
  // Arrival documents are pages, not modals: an operator types a whole faktura
  // here, and a form that long behind a dialog cannot be linked, reloaded or
  // left and come back to. Declared BEFORE nothing else — `/invoices/new` sits
  // above `:invoice_id` so the literal segment is not read as an id.
  {
    path: '/workshop/inventory/invoices/new',
    name: 'workshop-invoice-new',
    component: () => import('@/shared/views/WorkshopInvoiceFormView.vue'),
    meta: {
      titleKey: 'routes.invoiceNew',
      workshopAccess: { any: [p.manageInventory] },
      // A new arrival is entered into whichever branch the topbar names.
      branchScope: 'branch',
    },
  },
  {
    path: '/workshop/inventory/invoices/:invoice_id',
    name: 'workshop-invoice-detail',
    component: () => import('@/shared/views/WorkshopInvoiceDetailView.vue'),
    meta: {
      titleKey: 'routes.invoiceDetail',
      workshopAccess: { any: [p.manageInventory] },
      // An existing faktura carries its own branch; the picker steps aside.
      branchScope: 'entity',
    },
  },
  {
    path: '/workshop/inventory/invoices/:invoice_id/edit',
    name: 'workshop-invoice-edit',
    component: () => import('@/shared/views/WorkshopInvoiceFormView.vue'),
    meta: {
      titleKey: 'routes.invoiceEdit',
      workshopAccess: { any: [p.manageInventory] },
      branchScope: 'entity',
    },
  },
  // A material is a page too, and for the same reason the faktura is: it is
  // reached from a row, a link or a reload, and it carries its own branch (the
  // server derives it from the material) rather than depending on the topbar.
  {
    path: '/workshop/inventory/materials/:branch_material_id',
    name: 'workshop-material-detail',
    component: () => import('@/shared/views/WorkshopMaterialDetailView.vue'),
    meta: {
      titleKey: 'routes.materialDetail',
      workshopAccess: { any: [p.manageInventory] },
      branchScope: 'entity',
    },
  },
  {
    path: '/workshop/catalog',
    name: 'workshop-catalog',
    component: () => import('@/shared/views/WorkshopCatalogView.vue'),
    meta: {
      titleKey: 'routes.materialCatalog',
      workshopAccess: { any: [p.manageCatalog] },
      branchScope: 'branch',
    },
  },
  {
    path: '/workshop/settings/users',
    name: 'workshop-users',
    component: () => import('@/shared/views/WorkshopUsersView.vue'),
    meta: {
      // A Tizim page, so it is workshop-wide and the topbar picker steps aside
      // (QAD-182). The page keeps its own Filial filter — on a workshop-scoped
      // page that is the only branch control, not a second one.
      titleKey: 'routes.staff',
      workshopAccess: { ownerOnly: true },
      branchScope: 'workshop',
    },
  },
  {
    path: '/workshop/settings',
    name: 'workshop-settings',
    component: () => import('@/shared/views/WorkshopSettingsView.vue'),
    meta: {
      titleKey: 'routes.settings',
      workshopAccess: { ownerOnly: true },
      branchScope: 'workshop',
    },
  },
  {
    path: '/workshop/branches',
    name: 'workshop-branches',
    component: () => import('@/shared/views/WorkshopBranchesView.vue'),
    meta: {
      titleKey: 'routes.branches',
      workshopAccess: { ownerOnly: true },
      branchScope: 'workshop',
    },
  },
  {
    path: '/workshop/branches/:branch_id',
    name: 'workshop-branch-detail',
    component: () => import('@/shared/views/WorkshopBranchDetailView.vue'),
    meta: {
      titleKey: 'routes.branchDetail',
      workshopAccess: { ownerOnly: true },
      branchScope: 'entity',
    },
  },
  {
    path: '/workshop/finance/income',
    name: 'workshop-finance-income',
    component: () => import('@/shared/views/WorkshopFinanceExpensesView.vue'),
    meta: {
      titleKey: 'routes.income',
      workshopAccess: { any: [p.manageFinance] },
      branchScope: 'branch',
    },
  },
  {
    path: '/workshop/finance/expenses',
    name: 'workshop-finance-expenses',
    component: () => import('@/shared/views/WorkshopFinanceExpensesView.vue'),
    meta: {
      titleKey: 'routes.finance',
      workshopAccess: { any: [p.manageFinance] },
      branchScope: 'branch',
    },
  },
  {
    path: '/workshop/finance/debts',
    name: 'workshop-finance-debts',
    component: () => import('@/shared/views/WorkshopFinanceDebtsView.vue'),
    meta: {
      // Every term in the debt fold names a branch now (QAD-182), so the page
      // follows the picker like the rest of the finance module.
      titleKey: 'routes.debts',
      workshopAccess: { any: [p.manageFinance] },
      branchScope: 'branch',
    },
  },
  {
    path: '/workshop/finance/production',
    name: 'workshop-finance-production',
    component: () => import('@/shared/views/WorkshopFinanceProductionView.vue'),
    meta: {
      // One name in the nav, the tab title and the heading (QAD-182). Branch
      // scope like the rest of the finance module — the picker governs, and the
      // page carries no branch control of its own.
      titleKey: 'routes.labour',
      workshopAccess: { any: financeAccess },
      branchScope: 'branch',
    },
  },
  {
    path: '/workshop/settings/users/:user_id',
    name: 'workshop-user-detail',
    component: () => import('@/shared/views/WorkshopUserDetailView.vue'),
    meta: {
      titleKey: 'routes.staffDetail',
      workshopAccess: { ownerOnly: true },
      branchScope: 'entity',
    },
  },
  {
    path: '/workshop/notifications',
    name: 'workshop-notifications',
    component: () => import('@/shared/views/WorkshopNotificationsView.vue'),
    meta: { titleKey: 'routes.notifications', branchScope: 'workshop' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'workshop-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
    meta: { titleKey: 'routes.notFound', branchScope: 'workshop' },
  },
]
