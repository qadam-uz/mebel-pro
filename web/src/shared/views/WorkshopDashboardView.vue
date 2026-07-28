<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { captureApiError } from '@/shared/api/client'
import { traceLine } from '@/shared/app/errorTrace'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { useRolePath } from '@/shared/app/paths'
import { workshopDashboardAccess } from '@/shared/app/workshopDashboard'
import { workshopProductionQueueCounts } from '@/shared/app/workshopProduction'
import {
  dashboardFailureLine,
  orderPillClass,
  workshopStatusUz,
  type DashboardSectionFailure,
} from '@/shared/app/workshopUi'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatDate,
  formatDateInputValue,
  formatRelativeUz,
  formatTiyin,
  formatTiyinRow,
  formatStockQuantity,
} from '@/shared/formatters'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import OnboardingChecklist from '@/shared/components/OnboardingChecklist.vue'
import { activeWorkshopStatuses, useOrdersStore } from '@/shared/stores/orders'
import { useFinanceStore } from '@/shared/stores/finance'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

const rolePath = useRolePath()
const router = useRouter()
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
const CHART_WIDTH = 640
// 196, not 218: the date labels moved out of the SVG (they'd distort under
// preserveAspectRatio="none"), so the viewBox stops just below the baseline.
const CHART_HEIGHT = 196
const CHART_BASELINE = 188
const CHART_MAX_BAR_HEIGHT = 154
const CHART_GAP = 4

// Who sees what, and which of those cards may link anywhere — the whole rule
// lives in one pure function so it can be reasoned about and tested away from
// the markup (`workshopDashboard.ts`).
const access = computed(() => workshopDashboardAccess(auth.me, workshop.branches))

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
const canProduction = computed(() => access.value.canProduction)
const hasKpis = computed(() => access.value.hasKpis)
// A grant that lights up no section (manage_catalog, say) used to fall past the
// "no grants" empty state into a heading and a refresh button — the empty state
// has to cover "has grants, none of them surface here" as well (QAD-167).
const hasVisibleSection = computed(() => access.value.hasVisibleSection)
const activeOrders = computed(() =>
  orders.workshopOrders.filter((order) => activeWorkshopStatuses.includes(order.status)),
)
const recentOrders = computed(() => orders.recentWorkshopOrders)
const productionQueueCounts = computed(() =>
  workshopProductionQueueCounts(orders.workshopOrders, auth.me?.principal_id),
)
// The personal queue is production staff's main entry point, so they keep it
// even when empty; the owner manages rather than cuts, so the card would sit
// permanently empty — show it to the owner only on actual self-assignment.
const showProductionQueue = computed(
  () =>
    canProduction.value && (!permissions.isOwner.value || productionQueueCounts.value.total > 0),
)
// A card links only where its viewer can actually go: null means "render this
// tile, but not as a link" (QAD-170).
const ordersHref = computed(() =>
  access.value.canManageOrders ? rolePath('/workshop/orders') : null,
)
const incomeHref = computed(() =>
  canManageFinance.value ? rolePath('/workshop/finance/income') : null,
)
const expensesHref = computed(() =>
  canManageFinance.value ? rolePath('/workshop/finance/expenses') : null,
)
const debtsHref = computed(() =>
  canManageFinance.value ? rolePath('/workshop/finance/debts') : null,
)
const inventoryHref = computed(() => (canInventory.value ? rolePath('/workshop/inventory') : null))
// Branch pages are owner-only, so the per-branch production tiles are links for
// the owner alone — every other order reader got a dead link.
const branchesHref = computed(() =>
  permissions.isOwner.value ? rolePath('/workshop/branches') : null,
)
function branchHref(branchId: string) {
  return permissions.isOwner.value ? rolePath(`/workshop/branches/${branchId}`) : null
}
const lowStock = computed(() => workshop.lowStockItems.slice(0, 5))
const netPositive = computed(() => (finance.summary?.net_tiyin ?? 0) >= 0)
// Every money KPI on the page shares one scale, so the row can be read across
// instead of figure by figure (QAD-182).
const moneyKpis = computed(() =>
  formatTiyinRow([
    finance.summary?.income_tiyin ?? 0,
    finance.summary?.expense_tiyin ?? 0,
    finance.summary?.net_tiyin ?? 0,
    finance.supplierDebts?.we_owe_total_tiyin ?? 0,
    finance.clientDebts?.they_owe_total_tiyin ?? 0,
    workshop.stockValueTiyin ?? 0,
  ]),
)
const incomeParts = computed(() => moneyKpis.value[0])
const expenseParts = computed(() => moneyKpis.value[1])
const netParts = computed(() => moneyKpis.value[2])
const supplierDebtParts = computed(() => moneyKpis.value[3])
const clientDebtParts = computed(() => moneyKpis.value[4])
const stockValueParts = computed(() => moneyKpis.value[5])
const chartRows = computed(() => finance.summary?.daily_income ?? [])
const chartMax = computed(() => Math.max(1, ...chartRows.value.map((row) => row.income_tiyin)))
const hasIncome = computed(() => chartRows.value.some((row) => row.income_tiyin > 0))
const chartBars = computed(() => {
  const rows = chartRows.value
  if (rows.length === 0) return []
  const width = Math.max(3, (CHART_WIDTH - CHART_GAP * (rows.length + 1)) / rows.length)
  return rows.map((row, index) => {
    const height =
      row.income_tiyin > 0
        ? Math.max(6, (row.income_tiyin / chartMax.value) * CHART_MAX_BAR_HEIGHT)
        : 0
    return {
      day: row.day,
      income_tiyin: row.income_tiyin,
      x: CHART_GAP + index * (width + CHART_GAP),
      y: CHART_BASELINE - height,
      width,
      height,
      className:
        index === rows.length - 1
          ? 'hi'
          : row.income_tiyin === chartMax.value && row.income_tiyin > 0
            ? 'md'
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
const todayHasIncome = computed(() => (chartToday.value?.income_tiyin ?? 0) > 0)
const selectedBranchName = computed(
  () =>
    workshop.branches.find((branch) => branch.id === workshop.selectedBranchContext)?.name ?? null,
)
const chartPeak = computed(() =>
  chartRows.value.reduce<{ day: string; income_tiyin: number } | null>((peak, row) => {
    if (!peak || row.income_tiyin > peak.income_tiyin) return row
    return peak
  }, null),
)
const chartSummary = computed(() => {
  if (chartRows.value.length === 0) return `So'nggi ${chartDays.value} kun uchun tushum yo'q.`
  const today = chartToday.value
  const peak = chartPeak.value
  return [
    `So'nggi ${chartDays.value} kun tushumi: ${formatTiyin(finance.summary?.income_tiyin ?? 0)}.`,
    today ? `Bugun: ${formatTiyin(today.income_tiyin)}.` : '',
    peak ? `Eng yuqori kun: ${formatDate(peak.day)} · ${formatTiyin(peak.income_tiyin)}.` : '',
  ]
    .filter(Boolean)
    .join(' ')
})

function chartRange() {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - chartDays.value + 1)
  return {
    date_from: formatDateInputValue(start),
    date_to: formatDateInputValue(end),
  }
}

// Uzbek section labels for the partial-load banner (also its dedupe keys).
const dashboardSections = {
  branches: 'Filiallar',
  orders: 'Buyurtmalar',
  finance: 'Moliya',
  inventory: 'Ombor',
}

function recordDashboardError(section: string, code: string, traceId: string | null) {
  // First failure per section wins — a follow-up call for the same section
  // (e.g. recent orders after active orders) repeats the same cause.
  if (dashboardFailures.value.some((failure) => failure.section === section)) return
  dashboardFailures.value.push({ section, code, traceId })
}

function contextBranchFor(branches: Array<{ id: string }>) {
  const contextBranchId = workshop.selectedBranchContext
  if (!contextBranchId) return null
  return branches.some((branch) => branch.id === contextBranchId) ? contextBranchId : null
}

function openOrder(orderId: string) {
  void router.push(rolePath(`/workshop/orders/${orderId}`))
}

function setChartPeriod(days: number) {
  if (chartDays.value === days) return
  chartDays.value = days
  // Only the sales chart depends on the period — reload just the finance
  // summary so the orders/branch/inventory cards don't flicker on a filter.
  void loadFinanceSummary()
}

async function loadFinanceSummary() {
  if (!canFinance.value) return
  // Period/branch filter changes re-fetch finance alone — drop its previous
  // verdict so the banner reflects the latest attempt.
  dashboardFailures.value = dashboardFailures.value.filter(
    (failure) => failure.section !== dashboardSections.finance,
  )
  await finance.loadSummary({
    ...chartRange(),
    branch_id:
      contextBranchFor(financeBranches.value) ??
      (permissions.isOwner.value ? null : (financeBranches.value[0]?.id ?? null)),
  })
  if (finance.error) recordDashboardError(dashboardSections.finance, finance.error, finance.traceId)
}

async function loadDashboard() {
  dashboardLoading.value = true
  dashboardFailures.value = []
  await workshop.loadBranchContext().catch((errorValue) => {
    const captured = captureApiError(errorValue, 'branch_context_load_failed')
    recordDashboardError(dashboardSections.branches, captured.code, captured.traceId)
  })
  if (canOrders.value || canProduction.value) {
    const visibleOrderBranches = canOrders.value ? orderBranches.value : productionBranches.value
    const orderBranchId = contextBranchFor(visibleOrderBranches)
    await orders.loadWorkshopOrders({
      status: 'active',
      limit: 100,
      branch_id: orderBranchId,
    })
    if (orders.error) recordDashboardError(dashboardSections.orders, orders.error, orders.traceId)
    if (canOrders.value) {
      await orders.loadRecentWorkshopOrders({
        branch_id: orderBranchId,
        limit: 8,
      })
      if (orders.error) recordDashboardError(dashboardSections.orders, orders.error, orders.traceId)
    }
  }
  await loadFinanceSummary()
  // Best-effort tiles: a failed debts load must not take the dashboard down.
  if (canManageFinance.value) {
    await finance.loadSupplierDebts({ only_with_debt: true }).catch(() => {})
    await finance.loadClientDebts({ only_with_debt: true }).catch(() => {})
  }
  const inventoryContextBranchId = contextBranchFor(inventoryBranches.value)
  const inventoryBranchIds =
    inventoryContextBranchId !== null
      ? [inventoryContextBranchId]
      : inventoryBranches.value.map((branch) => branch.id)
  if (canInventory.value && inventoryBranchIds.length > 0) {
    workshop.inventoryLoading = true
    try {
      await workshop.loadLowStock(inventoryBranchIds)
      // Best-effort tile — a failed valuation must not take the dashboard down.
      await workshop.loadStockValue(inventoryBranchIds).catch(() => undefined)
      workshop.inventoryError = null
      workshop.inventoryTraceId = null
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'inventory_load_failed')
      workshop.inventoryError = captured.code
      workshop.inventoryTraceId = captured.traceId
      recordDashboardError(dashboardSections.inventory, captured.code, captured.traceId)
    } finally {
      workshop.inventoryLoading = false
    }
  }
  dashboardLoading.value = false
  dashboardReady.value = true
}

onMounted(loadDashboard)

watch(
  () => workshop.selectedBranchContext,
  () => {
    void loadDashboard()
  },
)
</script>

<template>
  <section class="workshop-dashboard">
    <div class="page-head">
      <div>
        <h1>Asosiy</h1>
        <div class="sub">
          {{
            selectedBranchName
              ? `${selectedBranchName} ko'rsatkichlari`
              : "Ustaxona ko'rsatkichlari"
          }}
        </div>
      </div>
      <!-- No «Yangilash». Page heads are title-only (DESIGN.md), the dashboard
           already refetches on mount and on a branch switch, and on a phone the
           button became the most prominent thing on the screen (QAD-182). The
           error banner below still offers a retry, which is when a manual
           refresh is actually the answer. -->
    </div>

    <OnboardingChecklist />

    <div v-if="dashboardFailures.length > 0" class="banner danger mb-4" role="alert">
      <div class="grow">
        <p class="font-bold">Dashboard ma'lumotlarini to'liq yuklab bo'lmadi</p>
        <ul class="mt-1 grid gap-0.5">
          <li v-for="failure in dashboardFailures" :key="failure.section">
            {{ dashboardFailureLine(failure) }}
          </li>
        </ul>
      </div>
      <button
        class="mp-button mp-button-outline min-h-8 px-3 text-xs"
        type="button"
        @click="loadDashboard"
      >
        Qayta urinish
      </button>
    </div>

    <div v-if="!hasAnyGrant" class="st-empty">
      <h3>Sizga hali hech qanday ruxsat berilmagan</h3>
      <p>Filial va vazifa biriktirilgach, ishingiz shu yerda ko'rinadi.</p>
    </div>

    <div v-else-if="dashboardReady && !hasVisibleSection" class="st-empty">
      <h3>Bu yerda ko'rsatiladigan ma'lumot yo'q</h3>
      <p>
        Sizdagi ruxsatlar asosiy panelda ko'rsatkich chiqarmaydi — ishingiz alohida bo'limlarda
        turadi.
      </p>
      <div v-if="canCatalog" class="mt-4">
        <RouterLink :to="rolePath('/workshop/catalog')" class="mp-button mp-button-primary">
          Material katalogi
        </RouterLink>
      </div>
    </div>

    <template v-else>
      <div v-if="hasKpis" class="kpis kpis-dash">
        <component
          :is="ordersHref ? RouterLink : 'div'"
          v-if="canOrders"
          :to="ordersHref"
          class="kpi"
          :class="ordersHref ? 'no-underline' : ''"
        >
          <div class="lbl">Ishlab chiqarishda</div>
          <div class="v num">
            <span v-if="dashboardReady">{{ activeOrders.length }}</span>
            <span v-else class="sk block h-7 w-12"></span>
          </div>
          <div class="d"><span>faol buyurtmalar</span></div>
        </component>

        <component
          :is="incomeHref ? RouterLink : 'div'"
          v-if="canFinance"
          :to="incomeHref"
          class="kpi"
          :class="incomeHref ? 'no-underline' : ''"
        >
          <div class="lbl">Tushum</div>
          <div class="v num">
            <span v-if="dashboardReady" :title="incomeParts.full"
              >{{ incomeParts.amount }} <small>{{ incomeParts.unit }}</small></span
            >
            <span v-else class="sk block h-7 w-28"></span>
          </div>
          <div class="d">
            <span>so'nggi {{ chartDays }} kun</span>
          </div>
        </component>

        <component
          :is="expensesHref ? RouterLink : 'div'"
          v-if="canFinance"
          :to="expensesHref"
          class="kpi"
          :class="expensesHref ? 'no-underline' : ''"
        >
          <div class="lbl">Xarajatlar</div>
          <div class="v num">
            <span v-if="dashboardReady" :title="expenseParts.full"
              >{{ expenseParts.amount }} <small>{{ expenseParts.unit }}</small></span
            >
            <span v-else class="sk block h-7 w-28"></span>
          </div>
          <div class="d">
            <span>so'nggi {{ chartDays }} kun</span>
          </div>
        </component>

        <div v-if="canFinance" class="kpi" :class="netPositive ? '' : 'bad'">
          <div class="lbl" :class="netPositive ? 'success-text' : 'danger-text'">Foyda</div>
          <div class="v num" :class="netPositive ? 'success-text' : 'danger-text'">
            <span v-if="dashboardReady" :title="netParts.full"
              >{{ netParts.amount }} <small>{{ netParts.unit }}</small></span
            >
            <span v-else class="sk block h-7 w-28"></span>
          </div>
          <div class="d"><span>tushum − xarajat</span></div>
        </div>

        <RouterLink
          v-if="debtsHref"
          :to="debtsHref"
          class="kpi no-underline"
          :class="(finance.supplierDebts?.we_owe_total_tiyin ?? 0) > 0 ? 'warn' : ''"
        >
          <div class="lbl">Ta'minotchilarga qarzimiz</div>
          <div
            class="v num"
            :class="(finance.supplierDebts?.we_owe_total_tiyin ?? 0) > 0 ? 'warn-text' : ''"
          >
            <span v-if="dashboardReady" :title="supplierDebtParts.full"
              >{{ supplierDebtParts.amount }} <small>{{ supplierDebtParts.unit }}</small></span
            >
            <span v-else class="sk block h-7 w-28"></span>
          </div>
          <div class="d"><span>yetkazmalar − to'lovlar</span></div>
        </RouterLink>

        <RouterLink v-if="debtsHref" :to="debtsHref" class="kpi no-underline">
          <div class="lbl">Mijozlar qarzi</div>
          <div class="v num">
            <span v-if="dashboardReady" :title="clientDebtParts.full"
              >{{ clientDebtParts.amount }} <small>{{ clientDebtParts.unit }}</small></span
            >
            <span v-else class="sk block h-7 w-28"></span>
          </div>
          <div class="d"><span>buyurtmalar − to'lovlar</span></div>
        </RouterLink>

        <RouterLink
          v-if="inventoryHref"
          :to="inventoryHref"
          class="kpi no-underline"
          :class="lowStock.length > 0 ? 'warn' : ''"
        >
          <div class="lbl">Kam qolgan materiallar</div>
          <div class="v num" :class="lowStock.length > 0 ? 'warn-text' : ''">
            <span v-if="dashboardReady">{{ lowStock.length }}</span>
            <span v-else class="sk block h-7 w-12"></span>
          </div>
          <div class="d"><span>me'yordan kam</span></div>
        </RouterLink>

        <RouterLink
          v-if="inventoryHref && workshop.stockValueTiyin !== null"
          :to="inventoryHref"
          class="kpi no-underline"
        >
          <div class="lbl">Ombor qiymati</div>
          <div class="v num">
            <span v-if="dashboardReady" :title="stockValueParts.full"
              >{{ stockValueParts.amount }} <small>{{ stockValueParts.unit }}</small></span
            >
            <span v-else class="sk block h-7 w-28"></span>
          </div>
          <div class="d"><span>oxirgi kirim narxida</span></div>
        </RouterLink>
      </div>

      <div v-if="showProductionQueue" class="card mb-[18px]">
        <div class="card-h">
          <div>
            <h2>Mening ishlab chiqarish navbatim</h2>
            <div class="sub">Rahbar tayinlagan kesish va kromka ishlari.</div>
          </div>
        </div>
        <div class="card-b">
          <div
            v-if="productionQueueCounts.total > 0"
            class="grid gap-px overflow-hidden rounded-lg border border-hairline bg-hairline md:grid-cols-2"
          >
            <RouterLink
              :to="rolePath('/workshop/cutting')"
              class="bg-elevated p-4 no-underline transition hover:bg-sunk"
            >
              <div class="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-muted">
                Kesish
              </div>
              <div class="mt-2 font-serif text-3xl font-semibold text-ink">
                {{ productionQueueCounts.cutting }}
                <small class="font-sans text-sm text-ink-muted">ish</small>
              </div>
              <p class="mt-2 font-sans text-[12.5px] text-ink-muted">
                Tasdiqlangan yoki kesilayotgan, sizga tayinlangan buyurtmalar.
              </p>
            </RouterLink>
            <RouterLink
              :to="rolePath('/workshop/banding')"
              class="bg-elevated p-4 no-underline transition hover:bg-sunk"
            >
              <div class="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-muted">
                Kromka
              </div>
              <div class="mt-2 font-serif text-3xl font-semibold text-ink">
                {{ productionQueueCounts.banding }}
                <small class="font-sans text-sm text-ink-muted">ish</small>
              </div>
              <p class="mt-2 font-sans text-[12.5px] text-ink-muted">
                Kromka bosqichida sizga biriktirilgan buyurtmalar.
              </p>
            </RouterLink>
          </div>
          <p v-else class="text-[13px] text-ink-soft">
            Hozir sizga ish tayinlanmagan — rahbar buyurtmani tayinlagach, u kesish yoki kromka
            navbatida shu yerda ko'rinadi.
          </p>
        </div>
      </div>

      <div v-if="hasKpis" class="grid gap-[18px]">
        <div v-if="canFinance" class="card">
          <div class="card-h">
            <div>
              <h2>Savdo · so'nggi {{ chartDays }} kun</h2>
              <div class="sub">
                Jami · <b>{{ formatTiyin(finance.summary?.income_tiyin ?? 0) }}</b>
              </div>
            </div>
            <div class="flex gap-1" role="group" aria-label="Davr (kun)">
              <button
                v-for="days in chartPeriodOptions"
                :key="days"
                class="mp-button min-h-8 px-2 text-xs"
                :class="days === chartDays ? 'mp-button-primary' : 'mp-button-outline'"
                type="button"
                :disabled="finance.loading"
                :aria-pressed="days === chartDays"
                @click="setChartPeriod(days)"
              >
                {{ days }} kun
              </button>
            </div>
          </div>
          <div class="card-b">
            <div v-if="!dashboardReady" class="sk block h-[150px] w-full"></div>
            <div v-else-if="chartRows.length === 0 || !hasIncome" class="st-empty !py-8">
              <h3>Savdo yozuvi yo'q</h3>
              <p>Tanlangan davrda hali tushum yozilmagan.</p>
            </div>
            <div v-else>
              <p class="sr-only">{{ chartSummary }}</p>
              <div class="chart-plot">
                <span class="chart-max" aria-hidden="true">{{ formatTiyin(chartMax) }}</span>
                <svg
                  class="chart workshop-sales-chart"
                  :viewBox="`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`"
                  preserveAspectRatio="none"
                  role="img"
                  :aria-label="chartSummary"
                >
                  <g class="grid" aria-hidden="true">
                    <line x1="0" y1="34" :x2="CHART_WIDTH" y2="34" />
                    <line x1="0" y1="72" :x2="CHART_WIDTH" y2="72" />
                    <line x1="0" y1="110" :x2="CHART_WIDTH" y2="110" />
                    <line x1="0" y1="148" :x2="CHART_WIDTH" y2="148" />
                  </g>
                  <g class="bars">
                    <rect
                      v-for="bar in chartBars"
                      :key="bar.day"
                      :class="bar.className"
                      :x="bar.x"
                      :y="bar.y"
                      :width="bar.width"
                      :height="bar.height"
                      rx="2"
                    >
                      <title>{{ formatDate(bar.day) }} · {{ formatTiyin(bar.income_tiyin) }}</title>
                    </rect>
                  </g>
                  <g aria-hidden="true">
                    <line
                      x1="0"
                      :y1="CHART_BASELINE"
                      :x2="CHART_WIDTH"
                      :y2="CHART_BASELINE"
                      class="axis"
                    />
                  </g>
                </svg>
              </div>
              <!-- Dates live outside the SVG: preserveAspectRatio="none" would
                     stretch/squash glyphs with the bars on wide/narrow screens. -->
              <div class="chart-x" aria-hidden="true">
                <span v-for="label in chartLabels" :key="label">{{ label }}</span>
              </div>
              <div class="chart-legend">
                <span v-if="todayHasIncome"><i class="chart-key today"></i>Bugun</span>
                <span><i class="chart-key peak"></i>Eng yuqori</span>
                <span><i class="chart-key other"></i>Boshqalar</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="canOrders" class="card">
          <div class="card-h">
            <h2>Ishlab chiqarish · filiallar bo'yicha</h2>
            <RouterLink v-if="branchesHref" :to="branchesHref" class="more">filiallar</RouterLink>
          </div>
          <div class="card-b">
            <div
              class="grid gap-px overflow-hidden rounded-lg border border-hairline bg-hairline grid-cols-[repeat(auto-fit,minmax(220px,1fr))]"
            >
              <template v-if="!dashboardReady">
                <div v-for="n in 2" :key="'skb' + n" class="bg-elevated p-4">
                  <span class="sk block h-3 w-24"></span>
                  <span class="sk mt-3 block h-8 w-16"></span>
                  <span class="sk mt-3 block h-3 w-32"></span>
                </div>
              </template>
              <component
                :is="branchHref(branch.id) ? RouterLink : 'div'"
                v-for="branch in workshop.branches"
                v-else
                :key="branch.id"
                :to="branchHref(branch.id)"
                class="bg-elevated p-4"
                :class="branchHref(branch.id) ? 'no-underline transition hover:bg-sunk' : ''"
              >
                <div class="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-muted">
                  {{ branch.name }}
                </div>
                <div class="mt-2 font-serif text-3xl font-semibold text-ink">
                  {{ activeOrders.filter((order) => order.branch_id === branch.id).length }}
                  <small class="font-sans text-sm text-ink-muted">buyurtma</small>
                </div>
                <p class="mt-2 font-mono text-[11px] text-ink-muted">
                  {{ branch.status === 'temporarily_closed' ? 'vaqtincha yopiq' : branch.address }}
                </p>
              </component>
            </div>
          </div>
        </div>

        <div v-if="canInventory" class="card">
          <div class="card-h">
            <h2>Kam qolgan materiallar</h2>
            <RouterLink v-if="inventoryHref" :to="inventoryHref" class="more">ombor</RouterLink>
          </div>
          <div class="card-b">
            <div v-if="workshop.inventoryLoading" class="grid gap-3">
              <span class="sk-line"></span>
              <span class="sk-line"></span>
              <span class="sk-line"></span>
            </div>
            <div v-else-if="workshop.inventoryError" class="st-error !py-8">
              <h3>Zaxira ma'lumotini yuklab bo'lmadi</h3>
              <p>{{ traceLine(workshop.inventoryTraceId) }}</p>
            </div>
            <div v-else-if="lowStock.length === 0" class="st-empty !py-8">
              <h3>Kam qolgan material yo'q</h3>
              <p>Tanlangan filial materiallari me'yorda.</p>
            </div>
            <div v-else class="grid gap-x-8 md:grid-cols-2">
              <div v-for="item in lowStock" :key="item.id" class="row-item">
                <div class="flex min-w-0 items-center gap-3">
                  <div
                    class="sw relative overflow-hidden"
                    :class="materialSwatchClass(item.material)"
                  >
                    <AuthFileImage
                      v-if="item.material.image_file_id"
                      :file-id="item.material.image_file_id"
                      alt=""
                      class="absolute inset-0 h-full w-full object-cover"
                    />
                  </div>
                  <div class="min-w-0">
                    <div class="nm truncate">{{ item.material.name }}</div>
                    <small class="text-ink-muted"
                      >min {{ formatStockQuantity(item.min_stock, item.display_unit) }}</small
                    >
                  </div>
                </div>
                <!-- A negative balance is an unrecorded arrival, not a low
                     shelf — it escalates from warn to danger (QAD-150). -->
                <div class="meta" :class="item.on_hand < 0 ? 'danger-text' : 'warn-text'">
                  {{ formatStockQuantity(item.on_hand, item.display_unit) }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="canOrders" class="card">
          <div class="card-h">
            <div>
              <h2>So'nggi buyurtmalar</h2>
              <div class="sub">Oxirgi yozuvlar · {{ recentOrders.length }} ta</div>
            </div>
            <RouterLink v-if="ordersHref" :to="ordersHref" class="more"
              >barchasini ko'rish</RouterLink
            >
          </div>
          <div class="card-b !p-0">
            <div class="table-wrap">
              <table class="tbl">
                <thead>
                  <tr>
                    <th>Buyurtma</th>
                    <th>Mijoz</th>
                    <th>Filial</th>
                    <th>Holat</th>
                    <th>Qachon</th>
                    <th class="right">Summa</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-if="!dashboardReady">
                    <tr v-for="n in 4" :key="'skr' + n">
                      <td colspan="6"><span class="sk sk-line" style="width: 100%"></span></td>
                    </tr>
                  </template>
                  <template v-else>
                    <tr
                      v-for="order in recentOrders"
                      :key="order.id"
                      class="clickable"
                      @click="openOrder(order.id)"
                    >
                      <td class="id">
                        <RouterLink
                          :to="rolePath(`/workshop/orders/${order.id}`)"
                          class="no-underline"
                        >
                          {{ order.order_number }}
                        </RouterLink>
                      </td>
                      <td class="nm">{{ order.contact_name }}</td>
                      <td>{{ order.branch_name }}</td>
                      <td>
                        <span :class="orderPillClass(order.status)">
                          <span class="pd"></span>{{ workshopStatusUz[order.status] }}
                        </span>
                      </td>
                      <td class="text-ink-soft" :title="formatDate(order.created_at)">
                        {{ formatRelativeUz(order.created_at) }}
                      </td>
                      <td class="amt">{{ formatTiyin(order.total_tiyin) }}</td>
                    </tr>
                    <tr v-if="recentOrders.length === 0">
                      <td colspan="6">
                        <div class="st-empty !border-0 !py-8">
                          <h3>Buyurtma yo'q</h3>
                          <p>Mijozlar buyurtma bergach shu yerda chiqadi.</p>
                        </div>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
