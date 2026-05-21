<script setup lang="ts">
// Finance dashboard — Income / Expenses / Net KPIs + per-category and
// per-branch breakdown over a date range (default last 30 days). Branch picker
// from the auth store scopes the report.
import { computed, onMounted, ref, watch } from 'vue'
import { ApiError } from '@/shared/api'
import { ErrorState, FormField } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtTiyin } from '@/shared/format'
import { useWorkshopAuth } from '../../store'
import { useBranchesStore } from '../../stores/branches'
import * as api from '../../api'
import type { FinanceReport } from '../../api/types'

const auth = useWorkshopAuth()
const branchesStore = useBranchesStore()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const report = ref<FinanceReport | null>(null)

function defaultRange() {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 30)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return { start: fmt(start), end: fmt(end) }
}
const range = ref(defaultRange())

const net = computed(() => report.value?.net_tiyin ?? 0)

const categories = computed(() =>
  Object.entries(report.value?.expenses_by_category ?? {}).sort((a, b) => b[1] - a[1]),
)

async function load() {
  loading.value = true
  error.value = null
  try {
    const branchId = auth.branchScope
    report.value = await api.financeReport({
      period_start: range.value.start,
      period_end: range.value.end,
      branchIds: branchId ? [branchId] : undefined,
    })
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

watch(() => auth.branchScope, load)
watch(range, load, { deep: true })
onMounted(load)
</script>

<template>
  <div style="margin-top: 16px">
    <div class="filters" style="margin-bottom: 14px">
      <FormField v-model="range.start" type="date" :label="t('workshop.periodFrom')" />
      <FormField v-model="range.end" type="date" :label="t('workshop.periodTo')" />
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />

    <template v-else>
      <div class="kpis">
        <div class="kpi">
          <div class="lbl">{{ t('workshop.incomeTotal') }}</div>
          <div class="v num">{{ fmtTiyin(report?.income_total_tiyin ?? 0) }}</div>
        </div>
        <div class="kpi">
          <div class="lbl">{{ t('workshop.expenseTotal') }}</div>
          <div class="v num">{{ fmtTiyin(report?.expense_total_tiyin ?? 0) }}</div>
        </div>
        <div
          class="kpi"
          :style="`background:${net >= 0 ? 'var(--success-tint)' : 'var(--danger-tint)'};border-color:${net >= 0 ? 'var(--success-tint)' : 'var(--danger-tint)'}`"
        >
          <div class="lbl" :style="`color:${net >= 0 ? 'var(--success)' : 'var(--danger)'}`">
            {{ t('workshop.netLabel') }}
          </div>
          <div class="v num" :class="net >= 0 ? 'success-text' : 'danger-text'">
            {{ fmtTiyin(net) }}
          </div>
        </div>
      </div>

      <section v-if="categories.length" class="card" style="margin-top: 16px">
        <div class="card-h">
          <h2>{{ t('workshop.kpiExpenses') }}</h2>
        </div>
        <div class="card-b" style="padding-top: 0">
          <div v-for="[cat, amount] in categories" :key="cat" class="row-item">
            <div class="nm">{{ t(`expenseCategory.${cat}`) }}</div>
            <div class="meta">{{ fmtTiyin(amount) }}</div>
          </div>
        </div>
      </section>

      <section
        v-if="report && Object.keys(report.per_branch).length"
        class="card"
        style="margin-top: 16px"
      >
        <div class="card-h">
          <h2>{{ t('workshop.productionByBranch') }}</h2>
        </div>
        <div class="card-b" style="padding-top: 0">
          <table class="tbl">
            <thead>
              <tr>
                <th>{{ t('workshop.colBranch') }}</th>
                <th class="right">{{ t('workshop.kpiIncome') }}</th>
                <th class="right">{{ t('workshop.kpiExpenses') }}</th>
                <th class="right">{{ t('workshop.netLabel') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="[bid, vals] in Object.entries(report.per_branch)" :key="bid">
                <td class="nm">{{ branchesStore.nameOf(bid) }}</td>
                <td class="amt">{{ fmtTiyin(vals.income_tiyin ?? 0) }}</td>
                <td class="amt">{{ fmtTiyin(vals.expense_tiyin ?? 0) }}</td>
                <td class="amt">{{ fmtTiyin(vals.net_tiyin ?? 0) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
