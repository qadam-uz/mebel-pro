import {
  branchesWithAnyPermission,
  hasAnyPermission,
  isWorkshopOwner,
  workshopPermissions as p,
  type PermissionBranch,
  type WorkshopPrincipal,
} from '@/shared/app/workshopPermissions'
import type { ProductionMode } from '@/shared/stores/workshop'

const FINANCE_PERMISSIONS = [p.manageFinance, p.viewFinanceReports] as const
const ORDER_PERMISSIONS = [p.viewOrders, p.manageOrders] as const

/** A branch as this module reads it. `production_mode` is optional so a caller
 *  that predates the mode (tests, an older payload) keeps the full dashboard:
 *  only an explicit `simple` hides the stations — the same rule `workshopNav`
 *  applies to the Kesish/Krom sidebar items. */
export interface DashboardBranch extends PermissionBranch {
  production_mode?: ProductionMode
}

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
export interface WorkshopDashboardAccess<TBranch extends DashboardBranch> {
  /** Branches whose data each section may load. */
  orderBranches: TBranch[]
  financeBranches: TBranch[]
  inventoryBranches: TBranch[]
  productionBranches: TBranch[]
  /** Renders the «Ishlab chiqarishda» KPI and the order-derived work-list rows. */
  canOrders: boolean
  /** Opens `/workshop/orders`, and turns the order rows' buttons live. */
  canManageOrders: boolean
  /** Renders «Bugungi tushum» and the Savdo chart. */
  canFinance: boolean
  /** Renders «Mijozlar qarzi» and opens the ledgers and the debt board. */
  canManageFinance: boolean
  /** Renders «Kam qolgan material» and the negative-stock row; opens Ombor. */
  canInventory: boolean
  /** Opens `/workshop/catalog` — no dashboard section of its own. */
  canCatalog: boolean
  /** Holds `process_production` somewhere — the permission half of the station
   *  question, and what opens the station pages. Whether the Stansiyalar panel
   *  actually renders is `showStations`, which adds the branch's mode. */
  canProduction: boolean
  /**
   * Renders the Stansiyalar panel — `canProduction` or `canManageOrders`, and
   * only while the selected branch runs `full`. A simple-mode branch never
   * writes an assignment, so both station queues are permanently empty there
   * and the panel would report "0 · hech kim" forever. Hiding it mirrors
   * `workshopNav` dropping the Kesish/Krom sidebar items on the same branch.
   */
  showStations: boolean
  /** At least one tile in the KPI grid, and therefore the card grid, renders. */
  hasKpis: boolean
  /**
   * At least one section of the page renders. False with a non-empty grant set
   * means the page would be a heading and a refresh button, which is what the
   * "nothing here for you" empty state exists to replace (QAD-167).
   */
  hasVisibleSection: boolean
}

export function workshopDashboardAccess<TBranch extends DashboardBranch>(
  principal: WorkshopPrincipal | null | undefined,
  branches: TBranch[],
  selectedBranchId: string | null = null,
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
  const canManageOrders = hasAnyPermission(principal, [p.manageOrders])
  const hasKpis = canOrders || canFinance || canInventory

  // The dashboard follows the sidebar's branch picker, like every list surface
  // (orders.md). With «Hammasi» selected — or before the context lands — this
  // falls back to the first branch, the same resolution `workshopNav` uses, so
  // the panel and the station nav items never disagree with each other.
  const selectedBranch = branches.find((branch) => branch.id === selectedBranchId) ?? branches[0]
  const showStations =
    (canProduction || canManageOrders) && selectedBranch?.production_mode !== 'simple'

  return {
    orderBranches,
    financeBranches,
    inventoryBranches,
    productionBranches,
    canOrders,
    canManageOrders,
    canFinance,
    canManageFinance: hasAnyPermission(principal, [p.manageFinance]),
    canInventory,
    canCatalog,
    canProduction,
    showStations,
    hasKpis,
    // The Stansiyalar panel is the one section outside the KPI/card grid, and
    // it is the whole of what `canProduction` lights up: drop it and a
    // process_production-only staffer lands in the "nothing here for you" empty
    // state instead of on the two station queues (QAD-167).
    //
    // Which is exactly what must happen on a simple-mode branch, where the
    // panel is hidden: that staffer has no section left, so the page owes them
    // the existing empty state rather than a heading over blank space.
    hasVisibleSection: hasKpis || showStations,
  }
}

/** How today's income compares with yesterday's, and whether it compares at all. */
export interface DailyIncomeDelta {
  todayTiyin: number
  /** `null` when the series is too short to hold a yesterday. */
  yesterdayTiyin: number | null
  /**
   * `percent` — a real ratio to show.
   * `noYesterday` — yesterday was zero, so a percentage is undefined and the
   * caption states the fact in words instead of rendering "∞%" or "+0%".
   * `noCompare` — the series has no yesterday row to compare against.
   */
  kind: 'percent' | 'noYesterday' | 'noCompare'
  /** Whole signed percent; only meaningful when `kind === 'percent'`. */
  percent: number
  /** Today at or above yesterday — the pill's ok/bad tone. */
  up: boolean
}

/**
 * Today vs. yesterday out of the finance summary's daily series.
 *
 * `daily_income` is densely filled by the backend (every calendar day in the
 * range, zeros included) and always ends on today, so today is the last row and
 * yesterday the one before it — no date arithmetic, and no gap to trip over.
 */
export function dailyIncomeDelta(
  rows: ReadonlyArray<{ income_tiyin: number }> | null | undefined,
): DailyIncomeDelta {
  const series = rows ?? []
  const todayTiyin = series.length > 0 ? series[series.length - 1].income_tiyin : 0
  const yesterdayTiyin = series.length > 1 ? series[series.length - 2].income_tiyin : null
  if (yesterdayTiyin === null) {
    return { todayTiyin, yesterdayTiyin, kind: 'noCompare', percent: 0, up: todayTiyin > 0 }
  }
  if (yesterdayTiyin === 0) {
    return { todayTiyin, yesterdayTiyin, kind: 'noYesterday', percent: 0, up: todayTiyin > 0 }
  }
  return {
    todayTiyin,
    yesterdayTiyin,
    kind: 'percent',
    percent: Math.round(((todayTiyin - yesterdayTiyin) / yesterdayTiyin) * 100),
    up: todayTiyin >= yesterdayTiyin,
  }
}
