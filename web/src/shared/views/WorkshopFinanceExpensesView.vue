<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { formatDate, formatDateInputValue, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import {
  useFinanceStore,
  type ExpenseCategory,
  type IncomeType,
  type LedgerStatus,
  type MoneyMethod,
} from '@/shared/stores/finance'
import { useOrdersStore } from '@/shared/stores/orders'
import { useWorkshopStore } from '@/shared/stores/workshop'

const route = useRoute()
const auth = useAuthStore()
const finance = useFinanceStore()
const orders = useOrdersStore()
const workshop = useWorkshopStore()
const now = new Date()
const today = formatDateInputValue(now)
const activeTab = ref<'expense' | 'income'>(route.path.endsWith('/income') ? 'income' : 'expense')
// One component serves both /finance/income and /finance/expenses; Vue Router reuses
// the instance, so the active tab must track the path rather than only the initial setup.
watch(
  () => route.path,
  (path) => {
    activeTab.value = path.endsWith('/income') ? 'income' : 'expense'
  },
)
const formMode = ref<'expense' | 'income' | null>(null)
const saving = ref(false)
const actionError = ref<string | null>(null)
const voidTarget = ref<{ kind: 'expense' | 'income'; id: string } | null>(null)
const voidReason = ref('')
const dateFrom = ref(formatDateInputValue(new Date(now.getFullYear(), now.getMonth(), 1)))
const dateTo = ref(today)
const filterBranchId = ref('all')
const expenseCategory = ref('all')
const incomeType = ref('all')
const statusFilter = ref<LedgerStatus | 'all'>('recorded')

const expenseForm = reactive({
  branchId: 'workshop',
  category: 'other' as ExpenseCategory,
  amount: '',
  incurredOn: today,
  vendor: '',
  description: '',
})
const incomeForm = reactive({
  type: 'order_payment' as IncomeType,
  branchId: 'workshop',
  orderId: '',
  amount: '',
  method: 'cash' as MoneyMethod,
  receivedOn: today,
  note: '',
})

const canManageFinance = computed(
  () =>
    auth.me?.is_owner === true ||
    (auth.me?.grants ?? []).some((grant) => grant.permission === 'manage_finance'),
)
const branchOptions = computed(() => [
  { value: 'workshop', label: 'Ustaxona-keng', meta: 'filialsiz yozuv', status: 'active' as const },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  })),
])
const filterBranchOptions = computed(() => [
  { value: 'all', label: 'Hamma filiallar', meta: 'ruxsat doirasi', status: 'active' as const },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  })),
])
const orderOptions = computed(() => [
  { value: '', label: 'Buyurtmani tanlang', meta: 'to`lov bog`lanadi', status: 'pending' as const },
  ...orders.workshopOrders
    .filter((order) => order.status !== 'cancelled')
    .map((order) => ({
      value: order.id,
      label: `${order.order_number} · ${order.contact_name}`,
      meta: formatTiyin(order.total_tiyin),
      status: order.status === 'completed' ? ('active' as const) : ('pending' as const),
    })),
])
const categoryOptions = [
  { value: 'all', label: 'Hamma kategoriyalar', meta: 'filtr', status: 'active' as const },
  { value: 'rent', label: 'Ijara', meta: 'joy xarajati', status: 'active' as const },
  { value: 'utilities', label: 'Kommunal', meta: 'elektr/gaz/suv', status: 'active' as const },
  {
    value: 'raw_materials',
    label: 'Xom ashyo',
    meta: 'material xaridi',
    status: 'active' as const,
  },
  { value: 'supplies', label: 'Aksessuar', meta: 'mayda ta`minot', status: 'active' as const },
  { value: 'transport', label: 'Transport', meta: 'yetkazish/yo`l', status: 'active' as const },
  { value: 'equipment', label: 'Texnika', meta: 'uskuna', status: 'active' as const },
  { value: 'marketing', label: 'Marketing', meta: 'reklama', status: 'active' as const },
  {
    value: 'taxes_and_fees',
    label: 'Soliqlar',
    meta: 'majburiy to`lovlar',
    status: 'active' as const,
  },
  { value: 'salary', label: 'Maosh', meta: 'xodim to`lovi', status: 'active' as const },
  { value: 'other', label: 'Boshqalar', meta: 'tasniflanmagan', status: 'active' as const },
]
const createCategoryOptions = categoryOptions.filter((option) => option.value !== 'all')
const incomeTypeOptions = [
  { value: 'all', label: 'Hamma turlar', meta: 'filtr', status: 'active' as const },
  {
    value: 'order_payment',
    label: "Buyurtma to'lovi",
    meta: 'buyurtmaga bog`langan',
    status: 'active' as const,
  },
  { value: 'other', label: 'Boshqa tushum', meta: 'qo`lda yozuv', status: 'active' as const },
]
const createIncomeTypeOptions = incomeTypeOptions.filter((option) => option.value !== 'all')
const methodOptions = [
  { value: 'cash', label: 'Naqd', meta: 'kassa', status: 'active' as const },
  { value: 'bank_transfer', label: 'Bank / karta', meta: 'o`tkazma', status: 'active' as const },
  { value: 'other', label: 'Boshqa', meta: 'izohda yoziladi', status: 'active' as const },
]
const statusOptions = [
  { value: 'recorded', label: 'Yozilgan', meta: 'hisobotga kiradi', status: 'active' as const },
  {
    value: 'voided',
    label: 'Bekor qilingan',
    meta: 'hisobotdan chiqqan',
    status: 'blocked' as const,
  },
  { value: 'all', label: 'Hammasi', meta: 'barcha holatlar', status: 'pending' as const },
]
const categoryLabel = Object.fromEntries(
  categoryOptions.map((option) => [option.value, option.label]),
)
const incomeTypeLabel = Object.fromEntries(
  incomeTypeOptions.map((option) => [option.value, option.label]),
)
const methodLabel = Object.fromEntries(methodOptions.map((option) => [option.value, option.label]))

function branchName(branchId: string | null) {
  if (!branchId) return 'ustaxona-keng'
  return workshop.branches.find((branch) => branch.id === branchId)?.name ?? 'Filial'
}

function amountTiyin(value: string) {
  const parsed = Number(value.replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed * 100) : 0
}

async function refresh() {
  const base = {
    date_from: dateFrom.value,
    date_to: dateTo.value,
    branch_id: filterBranchId.value === 'all' ? null : filterBranchId.value,
    status: statusFilter.value === 'all' ? null : statusFilter.value,
  }
  await finance.loadExpenses({
    ...base,
    category: expenseCategory.value === 'all' ? null : (expenseCategory.value as ExpenseCategory),
  })
  await finance.loadIncome({
    ...base,
    type: incomeType.value === 'all' ? null : (incomeType.value as IncomeType),
  })
}

async function createExpense() {
  if (!canManageFinance.value) return
  saving.value = true
  actionError.value = null
  try {
    await finance.createExpense({
      branch_id: expenseForm.branchId === 'workshop' ? null : expenseForm.branchId,
      category: expenseForm.category,
      amount_tiyin: amountTiyin(expenseForm.amount),
      incurred_on: expenseForm.incurredOn,
      vendor: expenseForm.vendor || null,
      description: expenseForm.description,
    })
    expenseForm.amount = ''
    expenseForm.vendor = ''
    expenseForm.description = ''
    formMode.value = null
    await refresh()
  } catch {
    actionError.value = 'expense_save_failed'
  } finally {
    saving.value = false
  }
}

async function createIncome() {
  if (!canManageFinance.value) return
  saving.value = true
  actionError.value = null
  try {
    await finance.createIncome({
      type: incomeForm.type,
      branch_id: incomeForm.branchId === 'workshop' ? null : incomeForm.branchId,
      order_id: incomeForm.type === 'order_payment' ? incomeForm.orderId || null : null,
      amount_tiyin: amountTiyin(incomeForm.amount),
      method: incomeForm.method,
      received_on: incomeForm.receivedOn,
      note: incomeForm.note || null,
    })
    incomeForm.amount = ''
    incomeForm.note = ''
    incomeForm.orderId = ''
    formMode.value = null
    await refresh()
  } catch {
    actionError.value = 'income_save_failed'
  } finally {
    saving.value = false
  }
}

async function confirmVoid() {
  if (!voidTarget.value || !voidReason.value.trim() || !canManageFinance.value) return
  actionError.value = null
  try {
    if (voidTarget.value.kind === 'expense')
      await finance.voidExpense(voidTarget.value.id, voidReason.value)
    else await finance.voidIncome(voidTarget.value.id, voidReason.value)
    voidTarget.value = null
    voidReason.value = ''
    await refresh()
  } catch {
    actionError.value = 'ledger_void_failed'
  }
}

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  await Promise.all([
    orders.loadWorkshopOrders({ status: 'active' }).catch(() => undefined),
    refresh(),
  ])
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Tushum va xarajat</h1>
        <p class="sub">
          Buyurtma to'lovlari, boshqa tushumlar va ustaxona xarajatlari (maosh ham shu yerda).
        </p>
      </div>
      <div class="tools">
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          @click="refresh"
        >
          Yangilash
        </button>
        <button
          v-if="canManageFinance"
          type="button"
          class="mp-button mp-button-outline"
          @click="formMode = formMode === 'income' ? null : 'income'"
        >
          Tushum
        </button>
        <button
          v-if="canManageFinance"
          type="button"
          class="mp-button mp-button-primary"
          @click="formMode = formMode === 'expense' ? null : 'expense'"
        >
          Xarajat
        </button>
      </div>
    </div>

    <div class="tabs">
      <button
        class="tab"
        :class="{ on: activeTab === 'expense' }"
        type="button"
        @click="activeTab = 'expense'"
      >
        Xarajatlar
      </button>
      <button
        class="tab"
        :class="{ on: activeTab === 'income' }"
        type="button"
        @click="activeTab = 'income'"
      >
        Tushumlar
      </button>
    </div>

    <section v-if="formMode === 'expense'" class="card mb-4">
      <div class="card-h"><h2>Xarajat yozish</h2></div>
      <form class="card-b grid gap-3 md:grid-cols-2 xl:grid-cols-4" @submit.prevent="createExpense">
        <ProjectDropdown
          v-model="expenseForm.category"
          label="Kategoriya"
          :options="createCategoryOptions"
        />
        <ProjectDropdown v-model="expenseForm.branchId" label="Filial" :options="branchOptions" />
        <label class="field">
          <span>Tavsif</span>
          <input
            v-model="expenseForm.description"
            class="mp-input"
            placeholder="Masalan: Bahodir T. · 19 panel"
            required
          />
        </label>
        <label class="field">
          <span>Yetkazib beruvchi</span>
          <input v-model="expenseForm.vendor" class="mp-input" placeholder="ixtiyoriy" />
        </label>
        <label class="field">
          <span>Summa (so'm)</span>
          <input v-model="expenseForm.amount" class="mp-input" inputmode="numeric" required />
        </label>
        <label class="field">
          <span>Sana</span>
          <input v-model="expenseForm.incurredOn" type="date" class="mp-input" required />
        </label>
        <div class="flex items-end gap-2 md:col-span-2">
          <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
            {{ saving ? 'Yozilmoqda' : 'Yozish' }}
          </button>
          <button type="button" class="mp-button mp-button-outline" @click="formMode = null">
            Bekor
          </button>
        </div>
      </form>
    </section>

    <section v-if="formMode === 'income'" class="card mb-4">
      <div class="card-h"><h2>Tushum yozish</h2></div>
      <form class="card-b grid gap-3 md:grid-cols-2 xl:grid-cols-4" @submit.prevent="createIncome">
        <ProjectDropdown
          v-model="incomeForm.type"
          label="Turi"
          :options="createIncomeTypeOptions"
        />
        <ProjectDropdown
          v-if="incomeForm.type === 'order_payment'"
          v-model="incomeForm.orderId"
          label="Buyurtma"
          :options="orderOptions"
        />
        <label class="field">
          <span>Summa (to'liq yoki qisman)</span>
          <input v-model="incomeForm.amount" class="mp-input" inputmode="numeric" required />
        </label>
        <ProjectDropdown v-model="incomeForm.method" label="Usul" :options="methodOptions" />
        <ProjectDropdown v-model="incomeForm.branchId" label="Filial" :options="branchOptions" />
        <label class="field">
          <span>Qabul sanasi</span>
          <input v-model="incomeForm.receivedOn" type="date" class="mp-input" required />
        </label>
        <label class="field md:col-span-2">
          <span>Izoh</span>
          <input v-model="incomeForm.note" class="mp-input" placeholder="kassa yoki bank izohi" />
        </label>
        <div class="flex items-end gap-2 md:col-span-2">
          <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
            {{ saving ? 'Yozilmoqda' : 'Yozish' }}
          </button>
          <button type="button" class="mp-button mp-button-outline" @click="formMode = null">
            Bekor
          </button>
        </div>
      </form>
    </section>

    <div class="filters">
      <label class="field">
        <span>Sana boshidan</span>
        <input v-model="dateFrom" type="date" class="mp-input" />
      </label>
      <label class="field">
        <span>Sana oxiri</span>
        <input v-model="dateTo" type="date" class="mp-input" />
      </label>
      <ProjectDropdown
        v-if="activeTab === 'expense'"
        v-model="expenseCategory"
        label="Kategoriya"
        :options="categoryOptions"
      />
      <ProjectDropdown v-else v-model="incomeType" label="Tur" :options="incomeTypeOptions" />
      <ProjectDropdown v-model="filterBranchId" label="Filial" :options="filterBranchOptions" />
      <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" />
      <button type="button" class="mp-button mp-button-primary self-end" @click="refresh">
        Qo'llash
      </button>
    </div>

    <section v-if="finance.loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="finance.error" class="st-error">
      <h3>Yozuvlarni yuklab bo'lmadi</h3>
      <p>trace_id: {{ finance.traceId ?? 'unavailable' }}</p>
    </section>

    <section v-else-if="activeTab === 'expense'" class="card">
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>Sana</th>
              <th>Kategoriya</th>
              <th>Tavsif</th>
              <th>Filial</th>
              <th>Yetkazib beruvchi</th>
              <th class="right">Summa</th>
              <th>Holat</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="expense in finance.expenses"
              :key="expense.id"
              :class="{ muted: expense.status === 'voided' }"
            >
              <td class="num text-ink-muted">{{ formatDate(expense.incurred_on) }}</td>
              <td>{{ categoryLabel[expense.category] ?? expense.category }}</td>
              <td class="nm">
                {{ expense.description }}
                <small v-if="expense.voided_reason">bekor: {{ expense.voided_reason }}</small>
              </td>
              <td>{{ branchName(expense.branch_id) }}</td>
              <td>
                <small class="text-ink-soft">{{ expense.vendor ?? '—' }}</small>
              </td>
              <td class="amt">{{ formatTiyin(expense.amount_tiyin) }}</td>
              <td>
                <span :class="expense.status === 'recorded' ? 'pill p-ok' : 'pill p-dn'">
                  <span class="pd"></span
                  >{{ expense.status === 'recorded' ? 'Yozilgan' : 'Bekor qilingan' }}
                </span>
              </td>
              <td class="right">
                <button
                  v-if="canManageFinance && expense.status === 'recorded'"
                  type="button"
                  class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  @click="voidTarget = { kind: 'expense', id: expense.id }"
                >
                  Bekor qilish
                </button>
              </td>
            </tr>
            <tr v-if="finance.expenses.length === 0">
              <td colspan="8">
                <div class="st-empty !border-0 !py-8"><h3>Bu davrda xarajat yo'q</h3></div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-else class="card">
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>Sana</th>
              <th>Turi</th>
              <th>Buyurtma</th>
              <th>Usul</th>
              <th>Filial</th>
              <th>Izoh</th>
              <th class="right">Summa</th>
              <th>Holat</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="income in finance.incomes"
              :key="income.id"
              :class="{ muted: income.status === 'voided' }"
            >
              <td class="num text-ink-muted">{{ formatDate(income.received_on) }}</td>
              <td>{{ incomeTypeLabel[income.type] ?? income.type }}</td>
              <td class="id">{{ income.order_id ?? '—' }}</td>
              <td>
                <small class="text-ink-soft">{{
                  methodLabel[income.method] ?? income.method
                }}</small>
              </td>
              <td>{{ branchName(income.branch_id) }}</td>
              <td>
                <small class="text-ink-soft">{{
                  income.note ?? income.voided_reason ?? '—'
                }}</small>
              </td>
              <td class="amt success-text">{{ formatTiyin(income.amount_tiyin) }}</td>
              <td>
                <span :class="income.status === 'recorded' ? 'pill p-ok' : 'pill p-dn'">
                  <span class="pd"></span
                  >{{ income.status === 'recorded' ? 'Yozilgan' : 'Bekor qilingan' }}
                </span>
              </td>
              <td class="right">
                <button
                  v-if="canManageFinance && income.status === 'recorded'"
                  type="button"
                  class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  @click="voidTarget = { kind: 'income', id: income.id }"
                >
                  Bekor qilish
                </button>
              </td>
            </tr>
            <tr v-if="finance.incomes.length === 0">
              <td colspan="9">
                <div class="st-empty !border-0 !py-8"><h3>Bu davrda tushum yo'q</h3></div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <form
      v-if="voidTarget"
      class="card mt-4 grid gap-3 p-5 md:grid-cols-[1fr_auto_auto]"
      @submit.prevent="confirmVoid"
    >
      <label class="field !mb-0">
        <span>Bekor qilish sababi</span>
        <input v-model="voidReason" class="mp-input" required />
      </label>
      <button type="submit" class="mp-button bg-danger text-white self-end" :disabled="saving">
        Tasdiqlash
      </button>
      <button type="button" class="mp-button mp-button-outline self-end" @click="voidTarget = null">
        Bekor
      </button>
    </form>

    <div v-if="actionError" class="banner danger mt-4">
      <div class="grow">{{ actionError }}</div>
    </div>
  </section>
</template>
