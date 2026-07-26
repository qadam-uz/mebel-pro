import {
  branchesWithAnyPermission,
  hasAnyPermission,
  isWorkshopOwner,
  workshopPermissions as p,
  type PermissionBranch,
  type WorkshopPrincipal,
} from '@/shared/app/workshopPermissions'

const FINANCE_PERMISSIONS = [p.manageFinance, p.viewFinanceReports] as const
const ORDER_PERMISSIONS = [p.viewOrders, p.manageOrders] as const

/**
 * What the workshop dashboard shows a given principal, and where it may link.
 *
 * Two distinct questions, deliberately answered separately (QAD-170): a `can*`
 * flag decides whether a card **renders**, while the `canManage*` flags decide
 * whether that card's "more" link may point at the page behind it. They are not
 * the same permission — `view_orders` renders the order cards but cannot open
 * `/workshop/orders`, and `view_finance_reports` renders the money tiles but
 * cannot open the ledgers. Gating a link on the rendering flag produced links
 * that bounced off the router guard straight back to the dashboard.
 *
 * The `canManage*` predicates are branch-blind on purpose — that is exactly what
 * the router guard tests, and a link must agree with the guard it will hit.
 */
export interface WorkshopDashboardAccess<TBranch extends PermissionBranch> {
  /** Branches whose data each section may load. */
  orderBranches: TBranch[]
  financeBranches: TBranch[]
  inventoryBranches: TBranch[]
  productionBranches: TBranch[]
  /** Renders the order KPI, the per-branch card and the recent-orders table. */
  canOrders: boolean
  /** Opens `/workshop/orders`. */
  canManageOrders: boolean
  /** Renders the money tiles and the sales chart. */
  canFinance: boolean
  /** Opens the income / expense ledgers and the debt board; also renders the debt tiles. */
  canManageFinance: boolean
  /** Renders the stock tiles and the low-stock card; also opens `/workshop/inventory`. */
  canInventory: boolean
  /** Opens `/workshop/catalog` — no dashboard section of its own. */
  canCatalog: boolean
  /** Renders the personal production queue; also opens the station pages. */
  canProduction: boolean
  /** At least one tile in the KPI grid, and therefore the card grid, renders. */
  hasKpis: boolean
  /**
   * At least one section of the page renders. False with a non-empty grant set
   * means the page would be a heading and a refresh button, which is what the
   * "nothing here for you" empty state exists to replace (QAD-167).
   */
  hasVisibleSection: boolean
}

export function workshopDashboardAccess<TBranch extends PermissionBranch>(
  principal: WorkshopPrincipal | null | undefined,
  branches: TBranch[],
): WorkshopDashboardAccess<TBranch> {
  const isOwner = isWorkshopOwner(principal)
  const orderBranches = branchesWithAnyPermission(principal, branches, ORDER_PERMISSIONS)
  const financeBranches = branchesWithAnyPermission(principal, branches, FINANCE_PERMISSIONS)
  const inventoryBranches = branchesWithAnyPermission(principal, branches, [p.manageInventory])
  const productionBranches = branchesWithAnyPermission(principal, branches, [p.processProduction])
  const catalogBranches = branchesWithAnyPermission(principal, branches, [p.manageCatalog])

  // `isOwner ||` is not redundant: the branch lists are empty until the branch
  // context lands, and the owner's sections must not blink out while it loads.
  const canOrders = isOwner || orderBranches.length > 0
  const canFinance = isOwner || financeBranches.length > 0
  const canInventory = isOwner || inventoryBranches.length > 0
  const canProduction = isOwner || productionBranches.length > 0
  const canCatalog = isOwner || catalogBranches.length > 0
  const hasKpis = canOrders || canFinance || canInventory

  return {
    orderBranches,
    financeBranches,
    inventoryBranches,
    productionBranches,
    canOrders,
    canManageOrders: hasAnyPermission(principal, [p.manageOrders]),
    canFinance,
    canManageFinance: hasAnyPermission(principal, [p.manageFinance]),
    canInventory,
    canCatalog,
    canProduction,
    hasKpis,
    // The production queue is the one section outside the KPI/card grid.
    hasVisibleSection: hasKpis || canProduction,
  }
}
