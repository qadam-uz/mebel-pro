<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { formatDateInputValue, formatStockQuantity, formatTiyin } from '@/shared/formatters'
import { useFinanceStore, type ExpenseCategory, type IncomeType } from '@/shared/stores/finance'
import { useWorkshopStore } from '@/shared/stores/workshop'

const finance = useFinanceStore()
const workshop = useWorkshopStore()
const rolePath = useRolePath()
const today = new Date()
const dateFrom = ref(formatDateInputValue(new Date(today.getFullYear(), today.getMonth(), 1)))
const dateTo = ref(formatDateInputValue(today))
const branchId = ref('all')
const period = ref('month')

const incomeTypeLabel: Record<IncomeType, string> = {
  order_payment: "Buyurtma to'lovi",
  other: 'Boshqa tushum',
}
const expenseCategoryLabel: Record<ExpenseCategory, string> = {
  rent: 'Ijara',
  utilities: 'Kommunal',
  raw_materials: 'Xom ashyo',
  supplies: 'Aksessuar',
  transport: 'Transport',
  equipment: 'Texnika',
  marketing: 'Marketing',
  taxes_and_fees: 'Soliqlar',
  salary: 'Maosh',
  other: 'Boshqalar',
}
const periodOptions = [
  {
    value: 'month',
    label: 'Bu oy',
    meta: `${dateFrom.value} — ${dateTo.value}`,
    status: 'active' as const,
  },
  { value: 'last30', label: 'Oxirgi 30 kun', meta: 'harakatdagi davr', status: 'active' as const },
  {
    value: 'year',
    label: 'Yil boshidan',
    meta: String(today.getFullYear()),
    status: 'active' as const,
  },
]
const branchFilterOptions = computed(() => [
  {
    value: 'all',
    label: 'Barcha filiallar',
    meta: `${workshop.branches.length} filial`,
    status: 'active' as const,
  },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.status === 'temporarily_closed' ? 'vaqtincha yopiq' : branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  })),
])
const recentIncome = computed(() => finance.incomes.slice(0, 6))
const expenseBreakdown = computed(() => {
  const rows = Object.entries(finance.summary?.expense_by_category ?? {}) as Array<
    [ExpenseCategory, number]
  >
  return rows
    .filter(([, amount]) => amount > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([category, amount]) => ({ category, amount }))
})
const branchRows = computed(() => finance.summary?.branches ?? [])
const productionRows = computed(() => finance.production?.rows.slice(0, 6) ?? [])
const netIsPositive = computed(() => (finance.summary?.net_tiyin ?? 0) >= 0)

function branchName(id: string | null) {
  if (!id) return 'Ustaxona-keng'
  return workshop.branches.find((branch) => branch.id === id)?.name ?? 'Filial'
}

function applyPeriod() {
  const now = new Date()
  if (period.value === 'last30') {
    dateTo.value = formatDateInputValue(now)
    dateFrom.value = formatDateInputValue(
      new Date(now.getFullYear(), now.getMonth(), now.getDate() - 30),
    )
  } else if (period.value === 'year') {
    dateFrom.value = `${now.getFullYear()}-01-01`
    dateTo.value = formatDateInputValue(now)
  } else {
    dateFrom.value = formatDateInputValue(new Date(now.getFullYear(), now.getMonth(), 1))
    dateTo.value = formatDateInputValue(now)
  }
}

function edgeLengths(value: Record<string, number>) {
  const total = Object.values(value).reduce((sum, length) => sum + length, 0)
  return total > 0 ? formatStockQuantity(total, 'm') : '0 m'
}

async function refresh() {
  applyPeriod()
  const filters = {
    date_from: dateFrom.value,
    date_to: dateTo.value,
    branch_id: branchId.value === 'all' ? null : branchId.value,
  }
  await finance.loadSummary(filters)
  await finance.loadIncome({ ...filters, status: 'recorded' })
  await finance.loadProduction(filters)
}

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  await refresh()
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Moliya hisobotlari</h1>
        <p class="sub">Tushum · xarajat · sof foyda · xodimlar mehnati — filiallar bo'yicha.</p>
      </div>
      <div class="tools">
        <ProjectDropdown v-model="period" label="Davr" :options="periodOptions" />
        <ProjectDropdown v-model="branchId" label="Filial" :options="branchFilterOptions" />
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          @click="refresh"
        >
          Yangilash
        </button>
        <RouterLink
          :to="rolePath('/workshop/finance/expenses')"
          class="mp-button mp-button-primary min-h-9 px-3 text-xs"
        >
          Tushum / xarajat
        </RouterLink>
      </div>
    </div>

    <section v-if="finance.loading && !finance.summary" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="finance.error && !finance.summary" class="st-error">
      <h3>Moliya hisobotini yuklab bo'lmadi</h3>
      <p>trace_id: {{ finance.traceId ?? 'unavailable' }}</p>
    </section>

    <section v-else-if="finance.summary">
      <div class="kpis">
        <article class="kpi">
          <div class="lbl">Tushum</div>
          <div class="v num success-text">{{ formatTiyin(finance.summary.income_tiyin) }}</div>
          <div class="d">
            <RouterLink :to="rolePath('/workshop/finance/expenses')" class="more"
              >tushum boshqaruvi</RouterLink
            >
          </div>
        </article>
        <article class="kpi">
          <div class="lbl">Xarajatlar</div>
          <div class="v num danger-text">{{ formatTiyin(finance.summary.expense_tiyin) }}</div>
          <div class="d">
            <RouterLink :to="rolePath('/workshop/finance/expenses')" class="more"
              >batafsil</RouterLink
            >
          </div>
        </article>
        <article class="kpi">
          <div class="lbl">Shundan maosh xarajati</div>
          <div class="v num">{{ formatTiyin(finance.summary.salary_expense_tiyin) }}</div>
          <div class="d"><span class="muted">maosh kategoriyasi</span></div>
        </article>
        <article class="kpi" :class="netIsPositive ? '' : 'warn'">
          <div class="lbl">{{ netIsPositive ? 'Foyda' : 'Zarar' }}</div>
          <div class="v num" :class="netIsPositive ? 'success-text' : 'danger-text'">
            {{ formatTiyin(finance.summary.net_tiyin) }}
          </div>
          <div class="d"><span class="muted">tushum - xarajat</span></div>
        </article>
      </div>

      <div class="two-col">
        <div>
          <section class="card">
            <div class="card-h">
              <h2>Tushum · so'nggi yozuvlar</h2>
              <RouterLink :to="rolePath('/workshop/finance/expenses')" class="more"
                >hammasi</RouterLink
              >
            </div>
            <div class="card-b !px-0">
              <div class="table-wrap">
                <table class="tbl">
                  <thead>
                    <tr>
                      <th>Sana</th>
                      <th>Turi</th>
                      <th>Buyurtma</th>
                      <th>Usul</th>
                      <th class="right">Summa</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="income in recentIncome" :key="income.id">
                      <td class="num text-ink-muted">{{ income.received_on }}</td>
                      <td>{{ incomeTypeLabel[income.type] }}</td>
                      <td class="id">{{ income.order_id ?? '—' }}</td>
                      <td>
                        <small class="text-ink-soft">{{ income.method }}</small>
                      </td>
                      <td class="amt success-text">{{ formatTiyin(income.amount_tiyin) }}</td>
                    </tr>
                    <tr v-if="recentIncome.length === 0">
                      <td colspan="5">
                        <div class="st-empty !border-0 !py-8"><h3>Bu davrda tushum yo'q</h3></div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <section class="card mt-4">
            <div class="card-h"><h2>Filiallar bo'yicha</h2></div>
            <div class="card-b !px-0">
              <div class="table-wrap">
                <table class="tbl">
                  <thead>
                    <tr>
                      <th>Filial</th>
                      <th class="right">Tushum</th>
                      <th class="right">Xarajat</th>
                      <th class="right">Sof</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in branchRows" :key="row.branch_id ?? 'workshop'">
                      <td class="nm">{{ branchName(row.branch_id) }}</td>
                      <td class="amt">{{ formatTiyin(row.income_tiyin) }}</td>
                      <td class="amt">{{ formatTiyin(row.expense_tiyin) }}</td>
                      <td class="amt" :class="row.net_tiyin >= 0 ? 'success-text' : 'danger-text'">
                        {{ formatTiyin(row.net_tiyin) }}
                      </td>
                    </tr>
                    <tr v-if="branchRows.length === 0">
                      <td colspan="4">
                        <div class="st-empty !border-0 !py-8">
                          <h3>Filial kesimida yozuv yo'q</h3>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>

        <div>
          <section class="card">
            <div class="card-h">
              <h2>Xarajatlar · kategoriya</h2>
              <RouterLink :to="rolePath('/workshop/finance/expenses')" class="more"
                >hammasi</RouterLink
              >
            </div>
            <div class="card-b">
              <div v-if="expenseBreakdown.length === 0" class="st-empty !border-0 !py-8">
                <h3>Bu davrda xarajat yo'q</h3>
              </div>
              <div v-for="row in expenseBreakdown" v-else :key="row.category" class="row-item">
                <div>
                  <div class="nm">{{ expenseCategoryLabel[row.category] }}</div>
                </div>
                <div class="meta">{{ formatTiyin(row.amount) }}</div>
              </div>
            </div>
          </section>

          <section class="card mt-4">
            <div class="card-h"><h2>Xodimlar mehnati · hisobot</h2></div>
            <div class="card-b !px-0">
              <p class="muted mx-5 my-3 text-xs">
                Buyurtma bosqichlaridan olinadi. Hisobchi maoshni qo'lda hisoblab, xarajat sifatida
                yozadi.
              </p>
              <div class="table-wrap">
                <table class="tbl">
                  <thead>
                    <tr>
                      <th>Xodim</th>
                      <th class="right">Panel</th>
                      <th class="right">Kesim</th>
                      <th class="right">Krom</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in productionRows" :key="row.user_id">
                      <td class="nm">{{ row.full_name }}</td>
                      <td class="amt">{{ row.panels_cut }}</td>
                      <td class="amt">{{ row.cut_count }}</td>
                      <td class="amt">{{ edgeLengths(row.edge_length_by_material) }}</td>
                    </tr>
                    <tr v-if="productionRows.length === 0">
                      <td colspan="4">
                        <div class="st-empty !border-0 !py-8">
                          <h3>Bu davrda ishlab chiqarish yo'q</h3>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>
  </section>
</template>
