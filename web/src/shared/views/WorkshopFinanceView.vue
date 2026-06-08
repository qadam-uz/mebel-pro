<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { formatDateInputValue, formatTiyin } from '@/shared/formatters'
import { useFinanceStore, type ExpenseCategory, type IncomeType } from '@/shared/stores/finance'
import { useWorkshopStore } from '@/shared/stores/workshop'

const finance = useFinanceStore()
const workshop = useWorkshopStore()
const rolePath = useRolePath()
const today = new Date()
const dateFrom = ref(formatDateInputValue(new Date(today.getFullYear(), today.getMonth(), 1)))
const dateTo = ref(formatDateInputValue(today))
const branchId = ref('all')
const incomeTypes: Array<{ key: IncomeType; label: string }> = [
  { key: 'order_payment', label: 'Order payments' },
  { key: 'other', label: 'Other income' },
]
const expenseCategories: Array<{ key: ExpenseCategory; label: string }> = [
  { key: 'rent', label: 'Rent' },
  { key: 'utilities', label: 'Utilities' },
  { key: 'raw_materials', label: 'Raw materials' },
  { key: 'supplies', label: 'Supplies' },
  { key: 'transport', label: 'Transport' },
  { key: 'equipment', label: 'Equipment' },
  { key: 'marketing', label: 'Marketing' },
  { key: 'taxes_and_fees', label: 'Taxes and fees' },
  { key: 'salary', label: 'Salary' },
  { key: 'other', label: 'Other' },
]

const branchOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: 'All branches', meta: 'workshop-wide' },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.status === 'temporarily_closed' ? 'temporarily closed' : branch.address,
  })),
])
const incomeBreakdown = computed(() =>
  incomeTypes.map((item) => ({
    ...item,
    amount: finance.summary?.income_by_type[item.key] ?? 0,
  })),
)
const expenseBreakdown = computed(() =>
  expenseCategories
    .map((item) => ({
      ...item,
      amount: finance.summary?.expense_by_category[item.key] ?? 0,
    }))
    .filter((item) => item.amount > 0),
)

async function refresh() {
  await finance.loadSummary({
    date_from: dateFrom.value,
    date_to: dateTo.value,
    branch_id: branchId.value === 'all' ? null : branchId.value,
  })
}

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  await refresh()
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Finance</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Ledger totals and finance reports for the workshop.
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <RouterLink :to="rolePath('/workshop/finance/income')" class="mp-button mp-button-outline">
          Income
        </RouterLink>
        <RouterLink
          :to="rolePath('/workshop/finance/expenses')"
          class="mp-button mp-button-outline"
        >
          Expenses
        </RouterLink>
        <RouterLink
          :to="rolePath('/workshop/finance/production')"
          class="mp-button mp-button-primary"
        >
          Production
        </RouterLink>
      </div>
    </div>

    <section class="mp-surface p-4">
      <div class="grid gap-3 md:grid-cols-[220px_1fr_1fr_auto]">
        <FormSelect v-model="branchId" label="Branch" :options="branchOptions" />
        <label class="block text-sm font-bold text-ink" for="finance-date-from">
          Date from
          <input id="finance-date-from" v-model="dateFrom" type="date" class="mp-input mt-1" />
        </label>
        <label class="block text-sm font-bold text-ink" for="finance-date-to">
          Date to
          <input id="finance-date-to" v-model="dateTo" type="date" class="mp-input mt-1" />
        </label>
        <button type="button" class="mp-button mp-button-primary self-end" @click="refresh">
          Apply
        </button>
      </div>
    </section>

    <section v-if="finance.loading" class="mp-surface p-5 text-sm font-bold text-ink-soft">
      Loading finance summary
    </section>
    <section v-else-if="finance.error" class="mp-surface p-5 text-sm font-bold text-danger">
      Finance summary could not be loaded.
      <span v-if="finance.traceId" class="font-mono">trace {{ finance.traceId }}</span>
    </section>
    <section v-else-if="finance.summary" class="space-y-5">
      <div class="grid gap-4 md:grid-cols-4">
        <article class="mp-surface p-5">
          <div class="text-sm font-bold text-ink-soft">Income</div>
          <div class="mt-2 font-mono text-2xl font-extrabold text-success">
            {{ formatTiyin(finance.summary.income_tiyin) }}
          </div>
        </article>
        <article class="mp-surface p-5">
          <div class="text-sm font-bold text-ink-soft">Expenses</div>
          <div class="mt-2 font-mono text-2xl font-extrabold text-danger">
            {{ formatTiyin(finance.summary.expense_tiyin) }}
          </div>
        </article>
        <article class="mp-surface p-5">
          <div class="text-sm font-bold text-ink-soft">Salary expense</div>
          <div class="mt-2 font-mono text-2xl font-extrabold text-danger">
            {{ formatTiyin(finance.summary.salary_expense_tiyin) }}
          </div>
        </article>
        <article class="mp-surface p-5">
          <div class="text-sm font-bold text-ink-soft">Net</div>
          <div class="mt-2 font-mono text-2xl font-extrabold text-ink">
            {{ formatTiyin(finance.summary.net_tiyin) }}
          </div>
        </article>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <section class="mp-surface overflow-hidden">
          <div class="border-b border-hairline px-5 py-4">
            <h2 class="font-serif text-xl font-semibold text-ink">Income split</h2>
          </div>
          <div class="divide-y divide-hairline">
            <div
              v-for="row in incomeBreakdown"
              :key="row.key"
              class="flex items-center justify-between gap-4 px-5 py-4 text-sm"
            >
              <span class="font-bold text-ink">{{ row.label }}</span>
              <span class="font-mono text-xs font-bold text-success">
                {{ formatTiyin(row.amount) }}
              </span>
            </div>
          </div>
        </section>

        <section class="mp-surface overflow-hidden">
          <div class="border-b border-hairline px-5 py-4">
            <h2 class="font-serif text-xl font-semibold text-ink">Expense categories</h2>
          </div>
          <div v-if="expenseBreakdown.length === 0" class="px-5 py-6 text-sm text-ink-soft">
            No recorded expenses in this period.
          </div>
          <div v-else class="divide-y divide-hairline">
            <div
              v-for="row in expenseBreakdown"
              :key="row.key"
              class="flex items-center justify-between gap-4 px-5 py-4 text-sm"
            >
              <span class="font-bold text-ink">{{ row.label }}</span>
              <span class="font-mono text-xs font-bold text-danger">
                {{ formatTiyin(row.amount) }}
              </span>
            </div>
          </div>
        </section>
      </div>

      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Branch breakdown</h2>
        </div>
        <div v-if="finance.summary.branches.length === 0" class="px-5 py-6 text-sm text-ink-soft">
          No ledger rows in this period.
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="bg-sunk text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-5 py-3">Branch</th>
                <th class="px-5 py-3">Income</th>
                <th class="px-5 py-3">Expenses</th>
                <th class="px-5 py-3">Net</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr v-for="row in finance.summary.branches" :key="row.branch_id ?? 'workshop'">
                <td class="px-5 py-3 font-bold text-ink">
                  {{
                    workshop.branches.find((branch) => branch.id === row.branch_id)?.name ??
                    'Workshop-wide'
                  }}
                </td>
                <td class="px-5 py-3 font-mono text-xs">{{ formatTiyin(row.income_tiyin) }}</td>
                <td class="px-5 py-3 font-mono text-xs">{{ formatTiyin(row.expense_tiyin) }}</td>
                <td class="px-5 py-3 font-mono text-xs">{{ formatTiyin(row.net_tiyin) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>
  </section>
</template>
