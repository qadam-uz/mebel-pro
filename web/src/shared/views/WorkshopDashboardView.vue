<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { useRolePath } from '@/shared/app/paths'
import { workshopProductionQueueCounts } from '@/shared/app/workshopProduction'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { orderPillClass, workshopStatusUz } from '@/shared/app/workshopUi'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatDate,
  formatDateInputValue,
  formatRelativeUz,
  formatTiyin,
  formatTiyinParts,
  formatStockQuantity,
} from '@/shared/formatters'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
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
const dashboardError = ref<string | null>(null)
const dashboardTraceId = ref<string | null>(null)
const chartDays = ref(14)
const chartPeriodOptions = [7, 14, 30]
const CHART_WIDTH = 640
// 196, not 218: the date labels moved out of the SVG (they'd distort under
// preserveAspectRatio="none"), so the viewBox stops just below the baseline.
const CHART_HEIGHT = 196
const CHART_BASELINE = 188
const CHART_MAX_BAR_HEIGHT = 154
const CHART_GAP = 4

const financePermissions = [p.manageFinance, p.viewFinanceReports]
const orderPermissions = [p.viewDashboard, p.manageOrders]

const hasAnyGrant = permissions.hasAnyGrant
const financeBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, financePermissions),
)
const orderBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, orderPermissions),
)
const productionBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, [p.processProduction]),
)
const inventoryBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, [p.manageInventory]),
)
const canFinance = computed(() => permissions.isOwner.value || financeBranches.value.length > 0)
const canInventory = computed(() => permissions.isOwner.value || inventoryBranches.value.length > 0)
const canOrders = computed(() => permissions.isOwner.value || orderBranches.value.length > 0)
const canProduction = computed(
  () => permissions.isOwner.value || productionBranches.value.length > 0,
)
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
const lowStock = computed(() => workshop.lowStockItems.slice(0, 5))
const netPositive = computed(() => (finance.summary?.net_tiyin ?? 0) >= 0)
const incomeParts = computed(() => formatTiyinParts(finance.summary?.income_tiyin ?? 0))
const expenseParts = computed(() => formatTiyinParts(finance.summary?.expense_tiyin ?? 0))
const netParts = computed(() => formatTiyinParts(finance.summary?.net_tiyin ?? 0))
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

function recordDashboardError(code: string, traceId: string | null) {
  if (dashboardError.value) return
  dashboardError.value = code
  dashboardTraceId.value = traceId
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
  await finance.loadSummary({
    ...chartRange(),
    branch_id:
      contextBranchFor(financeBranches.value) ??
      (permissions.isOwner.value ? null : (financeBranches.value[0]?.id ?? null)),
  })
  if (finance.error) recordDashboardError(finance.error, finance.traceId)
}

async function loadDashboard() {
  dashboardLoading.value = true
  dashboardError.value = null
  dashboardTraceId.value = null
  await workshop
    .loadBranchContext()
    .catch((errorValue) =>
      recordDashboardError('branch_context_load_failed', apiTraceId(errorValue)),
    )
  if (canOrders.value || canProduction.value) {
    const visibleOrderBranches = canOrders.value ? orderBranches.value : productionBranches.value
    const orderBranchId = contextBranchFor(visibleOrderBranches)
    await orders.loadWorkshopOrders({
      status: 'active',
      limit: 100,
      branch_id: orderBranchId,
    })
    if (orders.error) recordDashboardError(orders.error, orders.traceId)
    if (canOrders.value) {
      await orders.loadRecentWorkshopOrders({
        branch_id: orderBranchId,
        limit: 8,
      })
      if (orders.error) recordDashboardError(orders.error, orders.traceId)
    }
  }
  await loadFinanceSummary()
  const inventoryContextBranchId = contextBranchFor(inventoryBranches.value)
  const inventoryBranchIds =
    inventoryContextBranchId !== null
      ? [inventoryContextBranchId]
      : inventoryBranches.value.map((branch) => branch.id)
  if (canInventory.value && inventoryBranchIds.length > 0) {
    workshop.inventoryLoading = true
    try {
      await workshop.loadLowStock(inventoryBranchIds)
      workshop.inventoryError = null
      workshop.inventoryTraceId = null
    } catch (errorValue) {
      workshop.inventoryError = 'inventory_load_failed'
      workshop.inventoryTraceId = apiTraceId(errorValue)
      recordDashboardError('inventory_load_failed', workshop.inventoryTraceId)
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
      <div class="tools">
        <button
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          type="button"
          :disabled="dashboardLoading"
          @click="loadDashboard"
        >
          {{ dashboardLoading ? 'Yuklanmoqda' : 'Yangilash' }}
        </button>
      </div>
    </div>

    <div v-if="dashboardError" class="banner danger mb-4">
      <div class="grow">
        Dashboard ma'lumotlarini to'liq yuklab bo'lmadi · trace_id:
        {{ dashboardTraceId ?? 'unavailable' }}
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

    <template v-else>
      <div class="kpis kpis-dash">
        <RouterLink v-if="canOrders" :to="rolePath('/workshop/orders')" class="kpi no-underline">
          <div class="lbl">Ishlab chiqarishda</div>
          <div class="v num">
            <span v-if="dashboardReady">{{ activeOrders.length }}</span>
            <span v-else class="sk block h-7 w-12"></span>
          </div>
          <div class="d"><span>faol buyurtmalar</span></div>
        </RouterLink>

        <RouterLink
          v-if="canFinance"
          :to="rolePath('/workshop/finance/income')"
          class="kpi no-underline"
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
        </RouterLink>

        <RouterLink
          v-if="canFinance"
          :to="rolePath('/workshop/finance/expenses')"
          class="kpi no-underline"
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
        </RouterLink>

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
          v-if="canInventory"
          :to="rolePath('/workshop/inventory')"
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
      </div>

      <div v-if="showProductionQueue" class="card mb-[18px]">
        <div class="card-h">
          <div>
            <h2>Mening ishlab chiqarish navbatim</h2>
            <div class="sub">Rahbar tayinlagan kesish va krom ishlari.</div>
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
                Krom
              </div>
              <div class="mt-2 font-serif text-3xl font-semibold text-ink">
                {{ productionQueueCounts.banding }}
                <small class="font-sans text-sm text-ink-muted">ish</small>
              </div>
              <p class="mt-2 font-sans text-[12.5px] text-ink-muted">
                Krom bosqichida sizga biriktirilgan buyurtmalar.
              </p>
            </RouterLink>
          </div>
          <p v-else class="text-[13px] text-ink-soft">
            Hozir sizga ish tayinlanmagan — rahbar buyurtmani tayinlagach, u kesish yoki krom
            navbatida shu yerda ko'rinadi.
          </p>
        </div>
      </div>

      <div v-if="canFinance || canOrders || canInventory" class="grid gap-[18px]">
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
            <RouterLink :to="rolePath('/workshop/branches')" class="more">filiallar</RouterLink>
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
              <RouterLink
                v-for="branch in workshop.branches"
                v-else
                :key="branch.id"
                :to="rolePath(`/workshop/branches/${branch.id}`)"
                class="bg-elevated p-4 no-underline transition hover:bg-sunk"
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
              </RouterLink>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-h">
            <h2>Kam qolgan materiallar</h2>
            <RouterLink :to="rolePath('/workshop/inventory')" class="more">ombor</RouterLink>
          </div>
          <div class="card-b">
            <div v-if="workshop.inventoryLoading" class="grid gap-3">
              <span class="sk-line"></span>
              <span class="sk-line"></span>
              <span class="sk-line"></span>
            </div>
            <div v-else-if="workshop.inventoryError" class="st-error !py-8">
              <h3>Zaxira ma'lumotini yuklab bo'lmadi</h3>
              <p>trace_id: {{ workshop.inventoryTraceId ?? 'unavailable' }}</p>
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
                <div class="meta warn-text">
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
            <RouterLink :to="rolePath('/workshop/orders')" class="more"
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
