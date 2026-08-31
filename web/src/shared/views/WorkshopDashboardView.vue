<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { captureApiError } from '@/shared/api/client'
import { useRolePath } from '@/shared/app/paths'
import { dailyIncomeDelta, workshopDashboardAccess } from '@/shared/app/workshopDashboard'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { workerShortName, workshopStationLoad } from '@/shared/app/workshopProduction'
import { dashboardFailureLine, type DashboardSectionFailure } from '@/shared/app/workshopUi'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatDate,
  formatDateInputValue,
  formatDayMonthWeekday,
  formatRelative,
  formatSignedPercent,
  formatStockQuantity,
  formatTiyin,
  formatTiyinParts,
  formatTiyinRow,
} from '@/shared/formatters'
import AppIcon from '@/shared/components/AppIcon.vue'
import OnboardingChecklist from '@/shared/components/OnboardingChecklist.vue'
import SegmentedControl from '@/shared/components/SegmentedControl.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import {
  activeWorkshopStatuses,
  useOrdersStore,
  type OrderSummary,
  type WorkshopWorkerOption,
} from '@/shared/stores/orders'
import { useFinanceStore } from '@/shared/stores/finance'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

const rolePath = useRolePath()
const { t } = useI18n()
const permissions = useWorkshopPermissions()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const orders = useOrdersStore()
const finance = useFinanceStore()
const dashboardLoading = ref(false)
// First-load flag: drives skeletons on the very first paint only, so later
// refreshes / period / branch-context reloads swap data in place without flicker.
const dashboardReady = ref(false)
const dashboardFailures = ref<DashboardSectionFailure[]>([])
const chartDays = ref(14)
const chartPeriodOptions = [7, 14, 30]
// The orders page is read one page deep, so the active count is capped: past
// this the card says "100+" rather than silently undercounting.
const ORDER_PAGE_LIMIT = 100
const CHART_WIDTH = 300
const CHART_HEIGHT = 74
// Widest gap that still leaves a readable bar. 30 bars in the same 300 units
// need a narrower one, and on a phone the whole panel is ~340px wide, where a
// 3-unit gap eats the bar itself.
const CHART_GAP_WIDE = 3
const CHART_GAP_DENSE = 2
const CHART_GAP_NARROW = 1
// Below this the panel is full-bleed on a phone and the wide gap would eat the
// bars; expressed as a media query because the gap is in rescaled SVG units.
const CHART_NARROW_MAX_PX = 619

// Who sees what, and which of those cards may link anywhere — the whole rule
// lives in one pure function so it can be reasoned about and tested away from
// the markup (`workshopDashboard.ts`).
const access = computed(() =>
  // The selected branch is passed in because one section — Stansiyalar — is
  // mode-dependent: it is hidden on a simple-mode branch, whose station queues
  // are assignment-fed and therefore always empty (orders.md).
  workshopDashboardAccess(auth.me, workshop.branches, workshop.selectedBranchContext),
)

const hasAnyGrant = permissions.hasAnyGrant
const financeBranches = computed(() => access.value.financeBranches)
const orderBranches = computed(() => access.value.orderBranches)
const productionBranches = computed(() => access.value.productionBranches)
const inventoryBranches = computed(() => access.value.inventoryBranches)
const canFinance = computed(() => access.value.canFinance)
const canManageFinance = computed(() => access.value.canManageFinance)
const canInventory = computed(() => access.value.canInventory)
const canCatalog = computed(() => access.value.canCatalog)
const canOrders = computed(() => access.value.canOrders)
const canManageOrders = computed(() => access.value.canManageOrders)
const hasKpis = computed(() => access.value.hasKpis)
// A grant that lights up no section (manage_catalog, say) used to fall past the
// "no grants" empty state into a heading and a refresh button — the empty state
// has to cover "has grants, none of them surface here" as well (QAD-167).
const hasVisibleSection = computed(() => access.value.hasVisibleSection)

const selectedBranchName = computed(
  () =>
    workshop.branches.find((branch) => branch.id === workshop.selectedBranchContext)?.name ?? null,
)
// "7 avgust, juma". Recomputed rather than captured so a language switch
// relabels the day without a reload.
const todayLine = computed(() => formatDayMonthWeekday(new Date()))
const headSub = computed(() =>
  // No branch segment when the picker sits on all branches, or before the
  // context has landed — inventing one would name a branch that isn't in scope.
  selectedBranchName.value
    ? t('workshopAdmin.dashboard.subBranch', {
        branch: selectedBranchName.value,
        date: todayLine.value,
      })
    : todayLine.value,
)

const periodSegments = computed<ChoiceOption[]>(() =>
  chartPeriodOptions.map((days) => ({
    value: String(days),
    label: t('workshopAdmin.dashboard.periodOption', { n: days }, days),
  })),
)
const periodValue = computed(() => String(chartDays.value))

// --- KPI row ---------------------------------------------------------------

// `daily_income` is dense and always ends today, so today is the last row and
// yesterday the one before it (`workshopDashboard.ts` owns the rule).
const incomeDelta = computed(() => dailyIncomeDelta(finance.summary?.daily_income))
const activeOrders = computed(() =>
  orders.workshopOrders.filter((order) => activeWorkshopStatuses.includes(order.status)),
)
const activeOrdersCapped = computed(() => orders.workshopOrdersHasMore)
const activeOrdersCount = computed(() =>
  activeOrdersCapped.value ? `${ORDER_PAGE_LIMIT}+` : String(activeOrders.value.length),
)
const activeOrdersTotal = computed(() =>
  activeOrders.value.reduce((sum, order) => sum + order.total_tiyin, 0),
)
const clientDebtTiyin = computed(() => finance.clientDebts?.they_owe_total_tiyin ?? 0)
// The caption names the population that actually produced the total: the rows
// with a debt on them. Balances can be negative (an overpaid client), hence the
// `> 0` — a raw row count would describe a different set from the sum above it.
const clientDebtorCount = computed(
  () => finance.clientDebts?.rows.filter((row) => row.balance_tiyin > 0).length ?? 0,
)
const lowStockCount = computed(() => workshop.lowStockItems.length)
// A negative balance is an unrecorded arrival, not a low shelf — it escalates
// from warn to danger (QAD-150).
const negativeStock = computed(() =>
  workshop.lowStockItems
    .filter((item) => item.on_hand < 0)
    .sort((left, right) => left.on_hand - right.on_hand),
)
// Every money figure on the row shares one scale, so the row can be read across
// instead of figure by figure (QAD-182).
const moneyKpis = computed(() =>
  formatTiyinRow([incomeDelta.value.todayTiyin, clientDebtTiyin.value]),
)
const todayIncomeParts = computed(() => moneyKpis.value[0])
const clientDebtParts = computed(() => moneyKpis.value[1])
const activeOrdersParts = computed(() => formatTiyinParts(activeOrdersTotal.value))
const activeOrdersAmount = computed(
  () => `${activeOrdersParts.value.amount} ${activeOrdersParts.value.unit}`,
)

// --- Sizdan kutilmoqda ------------------------------------------------------

interface WorklistRow {
  key: string
  title: string
  /** Signed quantity chip beside the title, when the row is about a balance. */
  chip: string | null
  detail: string
  /** `null` when this viewer's grants cannot run the row's action. */
  action: { label: string; to: string } | null
}

// The order rows behind (a) and (d) are `view_orders|manage_orders`-scoped,
// while `orders.newOrderCount` is `manage_orders`-scoped — deriving both the
// count and its detail line from the same list is what keeps them from
// disagreeing on screen.
const newOrders = computed(() =>
  orders.workshopOrders
    .filter((order) => order.status === 'new')
    .sort((left, right) => left.created_at.localeCompare(right.created_at)),
)

// There is no `ready_at` column. These three are the moments the order actually
// became ready, in the order they are set.
function readyAt(order: OrderSummary) {
  return order.edge_completed_at ?? order.cut_completed_at ?? order.updated_at
}

const readyOrders = computed(() =>
  orders.workshopOrders
    .filter((order) => order.status === 'ready')
    .sort((left, right) => readyAt(left).localeCompare(readyAt(right))),
)

/** Confirmed work with no saw operator on it, grouped by the branch it sits in. */
const cutterGaps = computed(() => {
  const groups = new Map<
    string,
    { branchId: string; branchName: string; count: number; firstOrderId: string }
  >()
  for (const order of orders.workshopOrders) {
    if (order.status !== 'confirmed' || order.assigned_cutter_user_id !== null) continue
    const group = groups.get(order.branch_id)
    if (group) group.count += 1
    else
      groups.set(order.branch_id, {
        branchId: order.branch_id,
        branchName: order.branch_name,
        count: 1,
        firstOrderId: order.id,
      })
  }
  return [...groups.values()].sort((left, right) => right.count - left.count)
})

// A production-only viewer has no source for any of these rows — their order
// rows are their own assignments — so the panel stays off rather than standing
// permanently empty.
const showWorklist = computed(() => canOrders.value || canInventory.value)

const worklistRows = computed<WorklistRow[]>(() => {
  const rows: WorklistRow[] = []
  if (canOrders.value && newOrders.value.length > 0) {
    const oldest = newOrders.value[0]
    rows.push({
      key: 'new-orders',
      title: t(
        'workshopAdmin.dashboard.waitNewOrders',
        { n: newOrders.value.length },
        newOrders.value.length,
      ),
      chip: null,
      detail: t('workshopAdmin.dashboard.waitNewOrdersDetail', {
        order: oldest.order_number,
        client: oldest.contact_name,
        age: formatRelative(oldest.created_at),
      }),
      action: {
        label: t('workshopAdmin.dashboard.waitNewOrdersAction'),
        // The board is `manage_orders`; a `view_orders` reader gets the order
        // itself, which is the page their grant can actually open.
        to: canManageOrders.value
          ? rolePath('/workshop/orders')
          : rolePath(`/workshop/orders/${oldest.id}`),
      },
    })
  }
  if (canOrders.value && readyOrders.value.length > 0) {
    const listed = readyOrders.value.slice(0, 3)
    const rest = readyOrders.value.length - listed.length
    const waits = listed.map((order) =>
      t('workshopAdmin.dashboard.waitReadyOrdersItem', {
        order: order.order_number,
        age: formatRelative(readyAt(order)),
      }),
    )
    if (rest > 0) waits.push(t('workshopAdmin.dashboard.waitReadyOrdersMore', { n: rest }))
    rows.push({
      key: 'ready-orders',
      title: t(
        'workshopAdmin.dashboard.waitReadyOrders',
        { n: readyOrders.value.length },
        readyOrders.value.length,
      ),
      chip: null,
      detail: waits.join(' · '),
      // Not «Eslatma yuborish»: there is no client-callable endpoint that sends
      // a reminder anywhere in the API, and the Telegram gateway is OTP-only. A
      // button must not promise a message the system cannot send — so it opens
      // the orders instead, and says so.
      action: canManageOrders.value
        ? {
            label: t('workshopAdmin.dashboard.waitReadyOrdersAction'),
            to: rolePath('/workshop/orders'),
          }
        : {
            label: t('workshopAdmin.dashboard.waitReadyOrdersActionOne'),
            to: rolePath(`/workshop/orders/${readyOrders.value[0].id}`),
          },
    })
  }
  if (canInventory.value && negativeStock.value.length > 0) {
    const item = negativeStock.value[0]
    rows.push({
      key: 'negative-stock',
      title: t('workshopAdmin.dashboard.waitNegativeStock', { material: item.material.label }),
      chip: formatStockQuantity(item.on_hand, item.display_unit),
      detail: t('workshopAdmin.dashboard.waitNegativeStockDetail'),
      // The arrival form is a page of its own, and the row already names the
      // material that went negative — so the link seeds line 1 with it.
      action: {
        label: t('workshopAdmin.dashboard.waitNegativeStockAction'),
        to: `${rolePath('/workshop/inventory/invoices/new')}?material=${item.branch_material_id}`,
      },
    })
  }
  if (canOrders.value) {
    for (const gap of cutterGaps.value) {
      rows.push({
        key: `cutter-gap-${gap.branchId}`,
        title: t('workshopAdmin.dashboard.waitNoCutter', { branch: gap.branchName }),
        chip: null,
        detail: t('workshopAdmin.dashboard.waitNoCutterDetail', { n: gap.count }, gap.count),
        // The assign selects live on the order page and are `manage_orders` ON
        // THAT BRANCH — the order detail view gates them with
        // `canOnBranch(manageOrders, order.branch_id)`. The branch-blind
        // `canManageOrders` was the wrong question: a staffer holding
        // manage_orders on one branch and view_orders on another got a
        // «Xodim tayinlash» button for the second branch that opened the order
        // read-only, with no cutter select and no explanation. The row still
        // reports the stall for a reader who cannot act on it.
        action: permissions.canOnBranch(p.manageOrders, gap.branchId)
          ? {
              label: t('workshopAdmin.dashboard.waitNoCutterAction'),
              to: rolePath(`/workshop/orders/${gap.firstOrderId}`),
            }
          : null,
      })
    }
  }
  return rows
})

// Exactly one graphite button in the panel — the first row that has an action,
// which is also the most urgent since the rows are built in urgency order.
const worklistPrimaryKey = computed(
  () => worklistRows.value.find((row) => row.action !== null)?.key ?? null,
)

// --- Stansiyalar ------------------------------------------------------------

// Station-wide, from the order rows already on the page: the queue endpoint is
// personal for every principal, the owner included, so it cannot answer "what
// is at the saw right now" (`workshopStationLoad`).
const stationLoad = computed(() => workshopStationLoad(orders.workshopOrders))
const stationWorkersByBranch = ref<Record<string, WorkshopWorkerOption[]>>({})
// Permission *and* mode — `workshopDashboard.ts` owns the rule, because
// `hasVisibleSection` has to agree with it: a `process_production`-only staffer
// on a simple branch loses their only section and must land in the existing
// "nothing here for you" empty state, not on a blank page.
const showStations = computed(() => access.value.showStations)
const stationsHref = computed(() => rolePath('/workshop/cutting'))

function resolveWorkerName(userId: string): string | null {
  for (const workers of Object.values(stationWorkersByBranch.value)) {
    const found = workers.find((worker) => worker.id === userId)
    if (found) return found.full_name
  }
  return null
}

/**
 * Who is holding the station's work, in words. Empty string — not "nobody" —
 * when there are assignees whose names this viewer may not read: a
 * `process_production` staffer cannot fetch the worker list, and telling them
 * the station is unmanned would be a lie rather than a degradation.
 */
function stationStaffLine(userIds: string[]): string {
  if (userIds.length === 0) return t('workshopAdmin.dashboard.stationNobody')
  return userIds
    .map(resolveWorkerName)
    .filter((name): name is string => name !== null)
    .map(workerShortName)
    .join(' · ')
}

const stations = computed(() => [
  {
    key: 'cutting',
    icon: 'scissors',
    name: t('workshopAdmin.dashboard.stationCutting'),
    count: stationLoad.value.cutting,
    staff: stationStaffLine(stationLoad.value.cutters),
  },
  {
    key: 'banding',
    icon: 'layers',
    name: t('workshopAdmin.dashboard.stationBanding'),
    count: stationLoad.value.banding,
    staff: stationStaffLine(stationLoad.value.edgers),
  },
])

const hasSideCards = computed(() => showStations.value || canFinance.value)
const isSplit = computed(() => showWorklist.value && hasSideCards.value)

// --- Savdo ------------------------------------------------------------------

const chartRows = computed(() => finance.summary?.daily_income ?? [])
const chartMax = computed(() => Math.max(1, ...chartRows.value.map((row) => row.income_tiyin)))
const hasIncome = computed(() => chartRows.value.some((row) => row.income_tiyin > 0))
// The 620px rule needs the viewport, not a container query: the gap lives in
// SVG user units that `preserveAspectRatio="none"` rescales with the panel.
const narrowViewport = ref(false)
let viewportQuery: MediaQueryList | null = null
function onViewportChange(event: MediaQueryListEvent | MediaQueryList) {
  narrowViewport.value = event.matches
}
const chartGap = computed(() => {
  if (narrowViewport.value) return CHART_GAP_NARROW
  return chartRows.value.length >= 30 ? CHART_GAP_DENSE : CHART_GAP_WIDE
})
const chartBars = computed(() => {
  const rows = chartRows.value
  if (rows.length === 0) return []
  const gap = chartGap.value
  const width = Math.max(1, (CHART_WIDTH - gap * (rows.length - 1)) / rows.length)
  return rows.map((row, index) => {
    const height =
      row.income_tiyin > 0 ? Math.max(4, (row.income_tiyin / chartMax.value) * CHART_HEIGHT) : 0
    return {
      day: row.day,
      income_tiyin: row.income_tiyin,
      x: index * (width + gap),
      y: CHART_HEIGHT - height,
      width,
      height,
      className:
        index === rows.length - 1
          ? 'today'
          : row.income_tiyin === chartMax.value && row.income_tiyin > 0
            ? 'peak'
            : '',
    }
  })
})
const chartLabels = computed(() => {
  const rows = chartRows.value
  if (rows.length === 0) return []
  const indexes = [...new Set([0, Math.floor(rows.length / 2), rows.length - 1])]
  return indexes.map((index) => formatDate(rows[index].day))
})
const chartToday = computed(() =>
  chartRows.value.length > 0 ? chartRows.value[chartRows.value.length - 1] : null,
)
const chartPeak = computed(() =>
  chartRows.value.reduce<{ day: string; income_tiyin: number } | null>((peak, row) => {
    if (!peak || row.income_tiyin > peak.income_tiyin) return row
    return peak
  }, null),
)
const salesTotalParts = computed(() => formatTiyinParts(finance.summary?.income_tiyin ?? 0))
const salesTotal = computed(() => `${salesTotalParts.value.amount} ${salesTotalParts.value.unit}`)
// The three-step ramp is deliberately quiet, so the numbers have to be reachable
// as text: this sentence plus a `<title>` on every bar.
const chartSummary = computed(() => {
  const days = chartDays.value
  if (chartRows.value.length === 0) {
    return t('workshopAdmin.dashboard.chartSummaryEmpty', { n: days }, days)
  }
  const today = chartToday.value
  const peak = chartPeak.value
  return [
    t(
      'workshopAdmin.dashboard.chartSummaryTotal',
      { n: days, amount: formatTiyin(finance.summary?.income_tiyin ?? 0) },
      days,
    ),
    today
      ? t('workshopAdmin.dashboard.chartSummaryToday', { amount: formatTiyin(today.income_tiyin) })
      : '',
    peak
      ? t('workshopAdmin.dashboard.chartSummaryPeak', {
          date: formatDate(peak.day),
          amount: formatTiyin(peak.income_tiyin),
        })
      : '',
  ]
    .filter(Boolean)
    .join(' ')
})

// --- Loading ----------------------------------------------------------------

function chartRange() {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - chartDays.value + 1)
  return {
    date_from: formatDateInputValue(start),
    date_to: formatDateInputValue(end),
  }
}

// Section labels for the partial-load banner (also its dedupe keys). Resolved
// per call, never captured, so a language switch cannot leave a stale label.
function dashboardSections() {
  return {
    branches: t('workshopAdmin.dashboard.sectionBranches'),
    orders: t('workshopAdmin.dashboard.sectionOrders'),
    finance: t('workshopAdmin.dashboard.sectionFinance'),
    inventory: t('workshopAdmin.dashboard.sectionInventory'),
  }
}

function recordDashboardError(section: string, code: string, traceId: string | null) {
  // First failure per section wins — a follow-up call for the same section
  // repeats the same cause.
  if (dashboardFailures.value.some((failure) => failure.section === section)) return
  dashboardFailures.value.push({ section, code, traceId })
}

function contextBranchFor(branches: Array<{ id: string }>) {
  const contextBranchId = workshop.selectedBranchContext
  if (!contextBranchId) return null
  return branches.some((branch) => branch.id === contextBranchId) ? contextBranchId : null
}

function setChartPeriod(value: string) {
  const days = Number(value)
  if (!Number.isFinite(days) || chartDays.value === days) return
  chartDays.value = days
  // Only the sales chart depends on the period — reload just the finance
  // summary so the KPI, work-list and station panels don't flicker on a filter.
  void loadFinanceSummary()
}

async function loadFinanceSummary() {
  if (!canFinance.value) return
  // Period/branch filter changes re-fetch finance alone — drop its previous
  // verdict so the banner reflects the latest attempt.
  dashboardFailures.value = dashboardFailures.value.filter(
    (failure) => failure.section !== dashboardSections().finance,
  )
  await finance.loadSummary({
    ...chartRange(),
    branch_id:
      contextBranchFor(financeBranches.value) ??
      (permissions.isOwner.value ? null : (financeBranches.value[0]?.id ?? null)),
  })
  if (finance.error) {
    recordDashboardError(dashboardSections().finance, finance.error, finance.traceId)
  }
}

/**
 * Station staff names, best effort. The worker list needs `manage_orders` on the
 * branch, so the gate is checked *before* the request rather than after a 403:
 * a `process_production` viewer is the very audience the station panel is for,
 * and their screen degrades to counts without names instead of logging a refusal.
 */
async function loadStationWorkers() {
  if (!showStations.value) return
  const branchIds = [...new Set(orders.workshopOrders.map((order) => order.branch_id))]
  for (const branchId of branchIds) {
    if (stationWorkersByBranch.value[branchId]) continue
    if (!permissions.canOnBranch(p.manageOrders, branchId)) continue
    try {
      await orders.loadWorkers(branchId)
      stationWorkersByBranch.value = {
        ...stationWorkersByBranch.value,
        [branchId]: [...orders.workerOptions],
      }
    } catch {
      // Names are a courtesy on this panel; the queue counts are the point.
    }
  }
}

// Orders, finance and inventory are independent of each other, so their loads
// run side by side. Within a group the calls stay sequential on purpose: each
// store shares one `loading`/`error` pair across its actions, so two of its
// loads in parallel would race those flags and clear a skeleton (or an error)
// that still belongs to the other.
async function loadOrderSection() {
  // `showStations`, not `canProduction`: on a simple branch the panel is gone,
  // so a production-only viewer has nothing left for these rows to feed.
  if (!canOrders.value && !showStations.value) return
  const visibleOrderBranches = canOrders.value ? orderBranches.value : productionBranches.value
  const orderBranchId = contextBranchFor(visibleOrderBranches)
  await orders.loadWorkshopOrders({
    status: 'active',
    limit: ORDER_PAGE_LIMIT,
    branch_id: orderBranchId,
  })
  if (orders.error) recordDashboardError(dashboardSections().orders, orders.error, orders.traceId)
  await loadStationWorkers()
}

async function loadFinanceSection() {
  await loadFinanceSummary()
  // Best-effort tile: a failed debts load must not take the dashboard down.
  if (!canManageFinance.value) return
  await finance.loadClientDebts({ only_with_debt: true }).catch(() => {})
}

async function loadInventorySection() {
  const inventoryContextBranchId = contextBranchFor(inventoryBranches.value)
  const inventoryBranchIds =
    inventoryContextBranchId !== null
      ? [inventoryContextBranchId]
      : inventoryBranches.value.map((branch) => branch.id)
  if (!canInventory.value || inventoryBranchIds.length === 0) return
  workshop.inventoryLoading = true
  try {
    await workshop.loadLowStock(inventoryBranchIds)
    workshop.inventoryError = null
    workshop.inventoryTraceId = null
  } catch (errorValue) {
    const captured = captureApiError(errorValue, 'inventory_load_failed')
    workshop.inventoryError = captured.code
    workshop.inventoryTraceId = captured.traceId
    recordDashboardError(dashboardSections().inventory, captured.code, captured.traceId)
  } finally {
    workshop.inventoryLoading = false
  }
}

async function loadDashboard() {
  dashboardLoading.value = true
  dashboardFailures.value = []
  await workshop.loadBranchContext().catch((errorValue) => {
    const captured = captureApiError(errorValue, 'branch_context_load_failed')
    recordDashboardError(dashboardSections().branches, captured.code, captured.traceId)
  })
  // `allSettled`, not `all`: each section is written to record its own failure
  // and resolve, but one that ever threw would take the other two down with it
  // and — before the `finally` below — leave the skeleton up for good. The
  // sections are independent, so a thrown one must not hide the rest.
  try {
    await Promise.allSettled([loadOrderSection(), loadFinanceSection(), loadInventorySection()])
  } finally {
    dashboardLoading.value = false
    dashboardReady.value = true
  }
}

// The shell resolves the branch context asynchronously and then writes
// `selectedBranchContext`. Loading on mount ran the whole chain once with no
// branch selected — which queries *every* branch — and the watcher ran it again
// a moment later with one, so every dashboard request went out twice with the
// second reply discarding the first. Wait for the context, then load once.
// `undefined` means "no load has happened yet", distinct from a null context.
let loadedForContext: string | null | undefined

function loadDashboardFor(context: string | null) {
  loadedForContext = context
  // Worker names are cached per branch for the life of the page; a branch
  // switch changes which branches are in scope, so the cache goes with it.
  stationWorkersByBranch.value = {}
  void loadDashboard()
}

watch(
  () => [workshop.branchContextLoaded, workshop.selectedBranchContext] as const,
  ([contextLoaded, context]) => {
    if (!contextLoaded) return
    if (loadedForContext !== undefined && context === loadedForContext) return
    loadDashboardFor(context)
  },
  // `post` so the shell's own watcher has already written its branch pick for
  // this tick; otherwise we would load with a context that is about to change.
  { immediate: true, flush: 'post' },
)

onMounted(async () => {
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    viewportQuery = window.matchMedia(`(max-width: ${CHART_NARROW_MAX_PX}px)`)
    onViewportChange(viewportQuery)
    viewportQuery.addEventListener('change', onViewportChange)
  }
  try {
    await workshop.loadBranchContext()
  } catch {
    // The context failed, so the watcher above will never fire. Load anyway —
    // the dashboard renders the failure per section, which is far better than
    // a skeleton that never resolves.
    if (loadedForContext === undefined) loadDashboardFor(workshop.selectedBranchContext)
  }
})

onBeforeUnmount(() => {
  viewportQuery?.removeEventListener('change', onViewportChange)
})
</script>

<template>
  <section class="workshop-dashboard">
    <div class="page-head">
      <div>
        <h1>{{ $t('workshopAdmin.dashboard.title') }}</h1>
        <div class="sub">{{ headSub }}</div>
      </div>
      <!-- The period drives the sales chart and nothing else, so it is not on
           the page at all for a viewer who cannot see finance. -->
      <div v-if="canFinance" class="tools">
        <SegmentedControl
          :label="$t('workshopAdmin.dashboard.periodGroup')"
          hide-label
          :model-value="periodValue"
          :options="periodSegments"
          :disabled="finance.loading"
          @update:model-value="setChartPeriod"
        />
      </div>
    </div>

    <OnboardingChecklist />

    <div v-if="dashboardFailures.length > 0" class="banner danger mb-4" role="alert">
      <div class="grow">
        <p class="font-bold">{{ $t('workshopAdmin.dashboard.partialTitle') }}</p>
        <ul class="mt-1 grid gap-0.5">
          <li v-for="failure in dashboardFailures" :key="failure.section">
            {{ dashboardFailureLine(failure) }}
          </li>
        </ul>
      </div>
      <button
        class="mp-button mp-button-outline min-h-8 px-3 text-xs"
        type="button"
        :disabled="dashboardLoading"
        @click="loadDashboard"
      >
        {{ $t('workshopAdmin.action.retry') }}
      </button>
    </div>

    <div v-if="!hasAnyGrant" class="st-empty">
      <h3>{{ $t('workshopAdmin.dashboard.noGrantsTitle') }}</h3>
      <p>{{ $t('workshopAdmin.dashboard.noGrantsBody') }}</p>
    </div>

    <div v-else-if="dashboardReady && !hasVisibleSection" class="st-empty">
      <h3>{{ $t('workshopAdmin.dashboard.noSectionTitle') }}</h3>
      <p>{{ $t('workshopAdmin.dashboard.noSectionBody') }}</p>
      <div v-if="canCatalog" class="mt-4">
        <RouterLink :to="rolePath('/workshop/catalog')" class="mp-button mp-button-primary">
          {{ $t('workshopAdmin.dashboard.catalogLink') }}
        </RouterLink>
      </div>
    </div>

    <template v-else>
      <div v-if="hasKpis" class="kpis kpis-dash">
        <div v-if="canFinance" class="kpi">
          <div class="lbl">{{ $t('workshopAdmin.dashboard.kpiIncomeToday') }}</div>
          <div class="v">
            <span v-if="dashboardReady" :title="todayIncomeParts.full"
              >{{ todayIncomeParts.amount }} <small>{{ todayIncomeParts.unit }}</small></span
            >
            <span v-else class="sk block h-7 w-28"></span>
          </div>
          <div class="d">
            <template v-if="dashboardReady">
              <!-- A percentage against a zero yesterday is undefined, so the
                   card states the fact in words instead of showing "+0%". -->
              <span
                v-if="incomeDelta.kind === 'percent'"
                class="kpi-pill"
                :class="incomeDelta.up ? 'ok' : 'bad'"
                >{{ formatSignedPercent(incomeDelta.percent) }}</span
              >
              <span v-if="incomeDelta.kind === 'percent'">{{
                $t('workshopAdmin.dashboard.kpiIncomeVsYesterday')
              }}</span>
              <span v-else-if="incomeDelta.kind === 'noYesterday'">{{
                $t('workshopAdmin.dashboard.kpiIncomeNoYesterday')
              }}</span>
              <span v-else>{{ $t('workshopAdmin.dashboard.kpiIncomeNoCompare') }}</span>
            </template>
            <span v-else class="sk block h-4 w-32"></span>
          </div>
        </div>

        <component
          :is="canManageOrders ? RouterLink : 'div'"
          v-if="canOrders"
          :to="canManageOrders ? rolePath('/workshop/orders') : null"
          class="kpi"
          :class="canManageOrders ? 'no-underline' : ''"
        >
          <div class="lbl">{{ $t('workshopAdmin.dashboard.kpiActive') }}</div>
          <div class="v">
            <span v-if="dashboardReady">{{ activeOrdersCount }}</span>
            <span v-else class="sk block h-7 w-12"></span>
          </div>
          <div class="d">
            <span v-if="dashboardReady" :title="activeOrdersParts.full">
              {{
                $t(
                  'workshopAdmin.dashboard.kpiActiveMeta',
                  { n: activeOrders.length, amount: activeOrdersAmount },
                  activeOrders.length,
                )
              }}
            </span>
            <span v-else class="sk block h-4 w-32"></span>
          </div>
        </component>

        <!-- `manage_finance` only: the debts read behind this figure is scoped
             to that grant, so a `view_finance_reports` reader never sees it. -->
        <div v-if="canManageFinance" class="kpi">
          <div class="lbl">{{ $t('workshopAdmin.dashboard.kpiClientDebt') }}</div>
          <div class="v">
            <span v-if="dashboardReady" :title="clientDebtParts.full"
              >{{ clientDebtParts.amount }} <small>{{ clientDebtParts.unit }}</small></span
            >
            <span v-else class="sk block h-7 w-28"></span>
          </div>
          <div class="d">
            <span v-if="dashboardReady">{{
              $t(
                'workshopAdmin.dashboard.kpiClientDebtMeta',
                { n: clientDebtorCount },
                clientDebtorCount,
              )
            }}</span>
            <span v-else class="sk block h-4 w-32"></span>
          </div>
        </div>

        <div v-if="canInventory" class="kpi">
          <div class="lbl">{{ $t('workshopAdmin.dashboard.kpiLowStock') }}</div>
          <div class="v" :class="lowStockCount > 0 ? 'warn-text' : ''">
            <span v-if="dashboardReady">{{ lowStockCount }}</span>
            <span v-else class="sk block h-7 w-12"></span>
          </div>
          <div class="d">
            <template v-if="dashboardReady">
              <span v-if="negativeStock.length > 0" class="kpi-pill bad">{{
                $t(
                  'workshopAdmin.dashboard.kpiLowStockNegative',
                  { n: negativeStock.length },
                  negativeStock.length,
                )
              }}</span>
              <span v-else>{{ $t('workshopAdmin.dashboard.kpiLowStockMeta') }}</span>
            </template>
            <span v-else class="sk block h-4 w-32"></span>
          </div>
        </div>
      </div>

      <div :class="isSplit ? 'dash-split' : 'dash-side'">
        <div v-if="showWorklist" class="card">
          <div class="card-h">
            <h2>{{ $t('workshopAdmin.dashboard.waitTitle') }}</h2>
            <span v-if="dashboardReady" class="meta">
              {{
                $t(
                  'workshopAdmin.dashboard.waitMeta',
                  { n: worklistRows.length },
                  worklistRows.length,
                )
              }}
              <!-- Every row here, and both station figures, are derived from one
                   page of orders. Past that page the counts are lower bounds, so
                   say which population they describe instead of printing a number
                   that quietly stops growing. -->
              <template v-if="activeOrdersCapped">
                ·
                {{ $t('workshopAdmin.dashboard.cappedNote', { n: ORDER_PAGE_LIMIT }) }}
              </template>
            </span>
          </div>
          <div class="card-b">
            <div v-if="!dashboardReady" class="worklist">
              <div v-for="n in 3" :key="'skw' + n" class="worklist-row">
                <div>
                  <span class="sk block h-4 w-56"></span>
                  <span class="sk mt-2 block h-3.5 w-72"></span>
                </div>
              </div>
            </div>
            <div v-else-if="worklistRows.length === 0" class="st-empty">
              <h3>{{ $t('workshopAdmin.dashboard.waitEmptyTitle') }}</h3>
              <p>{{ $t('workshopAdmin.dashboard.waitEmptyBody') }}</p>
            </div>
            <div v-else class="worklist">
              <div v-for="row in worklistRows" :key="row.key" class="worklist-row">
                <div class="min-w-0">
                  <div class="worklist-title">
                    <span>{{ row.title }}</span>
                    <span v-if="row.chip" class="pill p-bad">{{ row.chip }}</span>
                  </div>
                  <div class="worklist-detail">{{ row.detail }}</div>
                </div>
                <RouterLink
                  v-if="row.action"
                  :to="row.action.to"
                  class="worklist-action"
                  :class="row.key === worklistPrimaryKey ? 'primary' : ''"
                >
                  {{ row.action.label }}
                </RouterLink>
              </div>
            </div>
          </div>
        </div>

        <div :class="isSplit ? 'dash-side' : 'contents'">
          <div v-if="showStations" class="card">
            <div class="card-h">
              <h2>{{ $t('workshopAdmin.dashboard.stationsTitle') }}</h2>
              <RouterLink :to="stationsHref" class="link">
                {{ $t('workshopAdmin.dashboard.stationsLink') }}
              </RouterLink>
            </div>
            <div class="card-b">
              <!-- Reporting rows, not links. The figure is the station's whole
                   load — every order at that stage, whoever holds it — while
                   `/workshop/cutting` is a personal terminal that lists only the
                   viewer's own jobs, so a row carrying this number and opening
                   that page would promise 12 and show 0 to an owner who does not
                   cut. The header's «Navbatlar» link stays: it says "my queues"
                   and goes where that is true. -->
              <div v-for="station in stations" :key="station.key" class="station-row">
                <div class="station-icon"><AppIcon :name="station.icon" /></div>
                <div class="min-w-0 flex-1">
                  <div class="station-name truncate">{{ station.name }}</div>
                  <!-- Absent, not "nobody": a viewer who may not read the worker
                       list gets the counts without the names. -->
                  <div v-if="station.staff" class="station-staff truncate">{{ station.staff }}</div>
                </div>
                <div class="station-count">
                  <!-- `N+` for the same reason the active-orders KPI carries it:
                       the load is counted off one page of orders. -->
                  <span v-if="dashboardReady">{{
                    activeOrdersCapped ? `${station.count}+` : station.count
                  }}</span>
                  <span v-else class="sk block h-6 w-6"></span>
                  <span class="sr-only">
                    {{
                      $t(
                        'workshopAdmin.dashboard.stationQueueUnit',
                        { n: station.count },
                        station.count,
                      )
                    }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="canFinance" class="card">
            <div class="card-h">
              <h2>{{ $t('workshopAdmin.dashboard.salesTitle') }}</h2>
              <span class="meta" :title="salesTotalParts.full">{{
                $t(
                  'workshopAdmin.dashboard.salesMeta',
                  { n: chartDays, amount: salesTotal },
                  chartDays,
                )
              }}</span>
            </div>
            <div class="card-b">
              <div v-if="!dashboardReady" class="sk block h-[74px] w-full"></div>
              <div v-else-if="chartRows.length === 0 || !hasIncome" class="st-empty">
                <h3>{{ $t('workshopAdmin.dashboard.chartEmptyTitle') }}</h3>
                <p>{{ $t('workshopAdmin.dashboard.chartEmptyBody') }}</p>
              </div>
              <div v-else>
                <p class="sr-only">{{ chartSummary }}</p>
                <svg
                  class="sales-chart"
                  :viewBox="`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`"
                  preserveAspectRatio="none"
                  role="img"
                  :aria-label="chartSummary"
                >
                  <rect
                    v-for="bar in chartBars"
                    :key="bar.day"
                    :class="bar.className"
                    :x="bar.x"
                    :y="bar.y"
                    :width="bar.width"
                    :height="bar.height"
                    rx="3"
                  >
                    <title>{{ formatDate(bar.day) }} · {{ formatTiyin(bar.income_tiyin) }}</title>
                  </rect>
                </svg>
                <!-- Dates live outside the SVG: preserveAspectRatio="none" would
                     stretch/squash glyphs with the bars on wide/narrow screens. -->
                <div class="sales-axis" aria-hidden="true">
                  <span v-for="label in chartLabels" :key="label">{{ label }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
