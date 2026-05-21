<script setup lang="ts">
// Workshop dashboard — branch-scoped KPIs (orders in production, income,
// expenses, profit, low-stock), recent orders, and a sales chart placeholder.
// Mirrors prototype workshop/dashboard.html. Branch picker (auth.branchScope)
// drives the scope; permission gating hides cards the user can't see.
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtTiyin } from '@/shared/format'
import { useWorkshopAuth } from '../store'
import { useBranchesStore } from '../stores/branches'
import * as api from '../api'
import type { FinanceReport, OrderCard } from '../api/types'

const auth = useWorkshopAuth()
const branchesStore = useBranchesStore()
const router = useRouter()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const orders = ref<OrderCard[]>([])
const report = ref<FinanceReport | null>(null)

const canOrders = computed(() => auth.can('manage_orders') || auth.can('view_dashboard'))
const canFinance = computed(() => auth.can('manage_finance') || auth.can('view_finance_reports'))
const canInventory = computed(() => auth.can('manage_inventory'))
const hasAnyGrant = computed(() => auth.isOwner || auth.grants.length > 0)

const inProduction = computed(
  () =>
    orders.value.filter((o) =>
      ['new', 'confirmed', 'cutting', 'edge_banding', 'ready'].includes(o.status),
    ).length,
)
const lowStockCount = computed(() => {
  const scope = auth.branchScope
  return branchesStore.branches
    .filter((b) => !scope || b.id === scope)
    .reduce((a, b) => a + b.low_stock_count, 0)
})
const income = computed(() => report.value?.income_total_tiyin ?? 0)
const expense = computed(() => report.value?.expense_total_tiyin ?? 0)
const net = computed(() => report.value?.net_tiyin ?? 0)

const recent = computed(() => orders.value.slice(0, 8))

function periodRange(): { start: string; end: string } {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 30)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return { start: fmt(start), end: fmt(end) }
}

async function load() {
  loading.value = true
  error.value = null
  try {
    await branchesStore.load()
    const branchId = auth.branchScope
    const tasks: Promise<unknown>[] = []
    if (canOrders.value) {
      tasks.push(api.listOrders({ branchId }).then((b) => (orders.value = b.orders)))
    } else {
      orders.value = []
    }
    if (canFinance.value) {
      const { start, end } = periodRange()
      tasks.push(
        api
          .financeReport({
            period_start: start,
            period_end: end,
            branchIds: branchId ? [branchId] : undefined,
          })
          .then((r) => (report.value = r))
          .catch(() => (report.value = null)),
      )
    } else {
      report.value = null
    }
    await Promise.all(tasks)
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

watch(() => auth.branchScope, load)
onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('workshop.dashTitle') }}</h1>
        <div class="date">{{ branchesStore.nameOf(auth.branchScope) }}</div>
      </div>
      <div class="tools">
        <button class="btn btn-ghost btn-sm" type="button" @click="load">
          {{ t('workshop.dashRefresh') }}
        </button>
      </div>
    </div>

    <div v-if="!hasAnyGrant" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.zeroGrantTitle') }}</h3>
      <p>{{ t('workshop.zeroGrantBody') }}</p>
    </div>

    <template v-else>
      <ErrorState v-if="error" :error="error" :retry="load" />

      <template v-else>
        <div class="kpis">
          <template v-if="loading">
            <div v-for="n in 4" :key="n" class="kpi">
              <div class="sk sk-line" style="width: 50%" />
              <div class="sk sk-line" style="width: 70%; margin-top: 12px; height: 22px" />
            </div>
          </template>
          <template v-else>
            <div
              v-if="canOrders"
              class="kpi"
              style="cursor: pointer"
              @click="router.push('/workshop/orders')"
            >
              <div class="lbl">{{ t('workshop.kpiInProduction') }}</div>
              <div class="v num">{{ inProduction }}</div>
              <div class="d">
                <span class="muted">{{ t('workshop.kpiInProductionHint') }}</span>
              </div>
            </div>
            <div
              v-if="canFinance"
              class="kpi"
              style="cursor: pointer"
              @click="router.push('/workshop/finance')"
            >
              <div class="lbl">{{ t('workshop.kpiIncome') }}</div>
              <div class="v num">{{ fmtTiyin(income) }}</div>
              <div class="d">
                <span class="muted">{{ t('workshop.recordedHint') }}</span>
              </div>
            </div>
            <div
              v-if="canFinance"
              class="kpi"
              style="cursor: pointer"
              @click="router.push('/workshop/finance/expenses')"
            >
              <div class="lbl">{{ t('workshop.kpiExpenses') }}</div>
              <div class="v num">{{ fmtTiyin(expense) }}</div>
              <div class="d">
                <span class="muted">{{ t('workshop.recordedHint') }}</span>
              </div>
            </div>
            <div
              v-if="canFinance"
              class="kpi"
              :style="`background:${net >= 0 ? 'var(--success-tint)' : 'var(--danger-tint)'};border-color:${net >= 0 ? 'var(--success-tint)' : 'var(--danger-tint)'}`"
            >
              <div class="lbl" :style="`color:${net >= 0 ? 'var(--success)' : 'var(--danger)'}`">
                {{ t('workshop.kpiProfit') }}
              </div>
              <div class="v num" :class="net >= 0 ? 'success-text' : 'danger-text'">
                {{ fmtTiyin(net) }}
              </div>
              <div class="d">
                <span class="muted">{{ t('workshop.kpiProfitHint') }}</span>
              </div>
            </div>
            <div
              v-if="canInventory"
              class="kpi warn"
              style="cursor: pointer"
              @click="router.push('/workshop/branches')"
            >
              <div class="lbl">{{ t('workshop.kpiLowStock') }}</div>
              <div class="v num" style="color: var(--warn)">{{ lowStockCount }}</div>
            </div>
          </template>
        </div>

        <section v-if="canOrders" class="card" style="margin-top: 18px">
          <div class="card-h">
            <h2>{{ t('workshop.recentOrders') }}</h2>
            <RouterLink class="more" to="/workshop/orders">{{
              t('workshop.openBoard')
            }}</RouterLink>
          </div>
          <div class="card-b" style="padding-top: 0">
            <div v-if="loading">
              <div v-for="n in 4" :key="n" class="sk sk-line" style="margin: 12px 0" />
            </div>
            <div v-else-if="recent.length === 0" class="st-empty" style="border: 0">
              <div class="ic">∅</div>
              <p>{{ t('common.empty') }}</p>
            </div>
            <table v-else class="tbl">
              <thead>
                <tr>
                  <th>{{ t('workshop.colId') }}</th>
                  <th>{{ t('workshop.colClient') }}</th>
                  <th>{{ t('workshop.colBranch') }}</th>
                  <th>{{ t('workshop.colStatus') }}</th>
                  <th class="right">{{ t('workshop.colAmount') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="o in recent"
                  :key="o.id"
                  class="clickable"
                  @click="router.push(`/workshop/orders/${o.id}`)"
                >
                  <td class="id">{{ o.order_number }}</td>
                  <td class="nm">{{ o.contact_name || '—' }}</td>
                  <td>{{ branchesStore.nameOf(o.branch_id) }}</td>
                  <td><StatusBadge :state="o.status" /></td>
                  <td class="amt">{{ fmtTiyin(o.total_tiyin) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>
