<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { formatDate, formatDateInputValue, formatTiyin } from '@/shared/formatters'
import { useFinanceStore, type ExpenseCategory, type LedgerStatus } from '@/shared/stores/finance'
import { useWorkshopStore } from '@/shared/stores/workshop'

const finance = useFinanceStore()
const workshop = useWorkshopStore()
const saving = ref(false)
const actionError = ref<string | null>(null)
const voidTargetId = ref<string | null>(null)
const voidReason = ref('')
const now = new Date()
const today = formatDateInputValue(now)
const dateFrom = ref(formatDateInputValue(new Date(now.getFullYear(), now.getMonth(), 1)))
const dateTo = ref(today)
const filterBranchId = ref('all')
const categoryFilter = ref('all')
const statusFilter = ref('all')
const minAmount = ref('')
const maxAmount = ref('')
const form = reactive({
  branchId: 'workshop',
  category: 'other' as ExpenseCategory,
  amount: '',
  incurredOn: today,
  vendor: '',
  description: '',
})

const branchOptions = computed<ChoiceOption[]>(() => [
  { value: 'workshop', label: 'Workshop-wide', meta: 'no branch' },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
  })),
])
const filterBranchOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: 'All branches', meta: 'visible scope' },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
  })),
])
const categoryOptions: ChoiceOption[] = [
  { value: 'rent', label: 'Rent' },
  { value: 'utilities', label: 'Utilities' },
  { value: 'raw_materials', label: 'Raw materials' },
  { value: 'supplies', label: 'Supplies' },
  { value: 'transport', label: 'Transport' },
  { value: 'equipment', label: 'Equipment' },
  { value: 'marketing', label: 'Marketing' },
  { value: 'taxes_and_fees', label: 'Taxes and fees' },
  { value: 'salary', label: 'Salary' },
  { value: 'other', label: 'Other' },
]
const filterCategoryOptions: ChoiceOption[] = [
  { value: 'all', label: 'All categories' },
  ...categoryOptions,
]
const statusOptions: ChoiceOption[] = [
  { value: 'all', label: 'All statuses' },
  { value: 'recorded', label: 'Recorded' },
  { value: 'voided', label: 'Voided' },
]
const statusTone: Record<LedgerStatus, string> = {
  recorded: 'bg-success-soft text-success',
  voided: 'bg-danger-soft text-danger',
}

function amountFilter(value: string) {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? String(Math.round(parsed * 100)) : null
}

function branchName(branchId: string | null) {
  if (!branchId) return 'Workshop-wide'
  return workshop.branches.find((branch) => branch.id === branchId)?.name ?? 'Branch'
}

async function refresh() {
  await finance.loadExpenses({
    date_from: dateFrom.value,
    date_to: dateTo.value,
    branch_id: filterBranchId.value === 'all' ? null : filterBranchId.value,
    category: categoryFilter.value === 'all' ? null : (categoryFilter.value as ExpenseCategory),
    status: statusFilter.value === 'all' ? null : (statusFilter.value as LedgerStatus),
    min_amount_tiyin: amountFilter(minAmount.value),
    max_amount_tiyin: amountFilter(maxAmount.value),
  })
}

async function createExpense() {
  saving.value = true
  actionError.value = null
  try {
    await finance.createExpense({
      branch_id: form.branchId === 'workshop' ? null : form.branchId,
      category: form.category,
      amount_tiyin: Math.round(Number(form.amount) * 100),
      incurred_on: form.incurredOn,
      vendor: form.vendor || null,
      description: form.description,
    })
    form.amount = ''
    form.vendor = ''
    form.description = ''
    await refresh()
  } catch {
    actionError.value = 'expense_save_failed'
  } finally {
    saving.value = false
  }
}

async function confirmVoid() {
  if (!voidTargetId.value || !voidReason.value.trim()) return
  actionError.value = null
  try {
    await finance.voidExpense(voidTargetId.value, voidReason.value)
    voidTargetId.value = null
    voidReason.value = ''
    await refresh()
  } catch {
    actionError.value = 'expense_void_failed'
  }
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
        <h1 class="font-serif text-3xl font-semibold text-ink">Expenses</h1>
        <p class="mt-2 text-base text-ink-soft">Recorded money spent by the workshop.</p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="refresh">Refresh</button>
    </div>

    <section class="mp-surface p-5">
      <h2 class="font-serif text-xl font-semibold text-ink">Record expense</h2>
      <form class="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-6" @submit.prevent="createExpense">
        <FormSelect v-model="form.branchId" label="Branch" :options="branchOptions" />
        <FormSelect v-model="form.category" label="Category" :options="categoryOptions" />
        <label class="block text-sm font-bold text-ink" for="expense-amount">
          Amount UZS
          <input
            id="expense-amount"
            v-model="form.amount"
            class="mp-input mt-1"
            inputmode="numeric"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="expense-date">
          Incurred on
          <input
            id="expense-date"
            v-model="form.incurredOn"
            type="date"
            class="mp-input mt-1"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="expense-vendor">
          Vendor
          <input id="expense-vendor" v-model="form.vendor" class="mp-input mt-1" />
        </label>
        <label class="block text-sm font-bold text-ink" for="expense-description">
          Description
          <input
            id="expense-description"
            v-model="form.description"
            class="mp-input mt-1"
            required
          />
        </label>
        <button
          type="submit"
          class="mp-button mp-button-primary md:col-span-2 xl:col-span-6"
          :disabled="saving"
        >
          {{ saving ? 'Recording' : 'Record expense' }}
        </button>
      </form>
    </section>

    <section class="mp-surface p-4">
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-[180px_1fr_1fr_1fr_1fr_1fr_1fr_auto]">
        <FormSelect v-model="filterBranchId" label="Branch" :options="filterBranchOptions" />
        <FormSelect v-model="categoryFilter" label="Category" :options="filterCategoryOptions" />
        <FormSelect v-model="statusFilter" label="Status" :options="statusOptions" />
        <label class="block text-sm font-bold text-ink" for="expense-filter-from">
          Date from
          <input id="expense-filter-from" v-model="dateFrom" type="date" class="mp-input mt-1" />
        </label>
        <label class="block text-sm font-bold text-ink" for="expense-filter-to">
          Date to
          <input id="expense-filter-to" v-model="dateTo" type="date" class="mp-input mt-1" />
        </label>
        <label class="block text-sm font-bold text-ink" for="expense-filter-min">
          Min UZS
          <input
            id="expense-filter-min"
            v-model="minAmount"
            inputmode="numeric"
            class="mp-input mt-1"
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="expense-filter-max">
          Max UZS
          <input
            id="expense-filter-max"
            v-model="maxAmount"
            inputmode="numeric"
            class="mp-input mt-1"
          />
        </label>
        <button type="button" class="mp-button mp-button-primary self-end" @click="refresh">
          Apply
        </button>
      </div>
    </section>

    <section v-if="finance.loading" class="mp-surface p-5 text-sm font-bold text-ink-soft">
      Loading expenses
    </section>
    <section v-else-if="finance.error" class="mp-surface p-5 text-sm font-bold text-danger">
      Expenses could not be loaded.
    </section>
    <section v-else-if="finance.expenses.length === 0" class="mp-surface p-5 text-sm text-ink-soft">
      No expenses in this period.
    </section>
    <section v-else class="mp-surface overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full text-left text-sm">
          <thead class="bg-sunk text-xs uppercase text-ink-muted">
            <tr>
              <th class="px-5 py-3">Date</th>
              <th class="px-5 py-3">Category</th>
              <th class="px-5 py-3">Branch</th>
              <th class="px-5 py-3">Vendor</th>
              <th class="px-5 py-3">Amount</th>
              <th class="px-5 py-3">Status</th>
              <th class="px-5 py-3">Description</th>
              <th class="px-5 py-3">Action</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-hairline">
            <tr v-for="row in finance.expenses" :key="row.id">
              <td class="px-5 py-3">{{ formatDate(row.incurred_on) }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.category }}</td>
              <td class="px-5 py-3 text-ink-soft">{{ branchName(row.branch_id) }}</td>
              <td class="px-5 py-3 text-ink-soft">{{ row.vendor ?? 'No vendor' }}</td>
              <td class="px-5 py-3 font-mono text-xs font-bold">
                {{ formatTiyin(row.amount_tiyin) }}
              </td>
              <td class="px-5 py-3">
                <span class="mp-chip" :class="statusTone[row.status]">
                  <span class="mp-dot" aria-hidden="true"></span>
                  {{ row.status }}
                </span>
              </td>
              <td class="px-5 py-3 text-ink-soft">{{ row.description }}</td>
              <td class="px-5 py-3">
                <button
                  v-if="row.status === 'recorded'"
                  type="button"
                  class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                  @click="voidTargetId = row.id"
                >
                  Void
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <form
      v-if="voidTargetId"
      class="mp-surface grid gap-3 p-5 md:grid-cols-[1fr_auto_auto]"
      @submit.prevent="confirmVoid"
    >
      <label class="block text-sm font-bold text-ink" for="expense-void-reason">
        Void reason
        <input id="expense-void-reason" v-model="voidReason" class="mp-input mt-1" required />
      </label>
      <button type="submit" class="mp-button mp-button-primary self-end">Confirm void</button>
      <button
        type="button"
        class="mp-button mp-button-outline self-end"
        @click="voidTargetId = null"
      >
        Cancel
      </button>
    </form>

    <p v-if="actionError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
      Expense action could not be completed.
    </p>
  </section>
</template>
