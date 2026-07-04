<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { financeLedgerTabFromPath, financeOrderReferenceLabel } from '@/shared/app/financeLedger'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import AppTabs from '@/shared/components/AppTabs.vue'
import FilePicker from '@/shared/components/FilePicker.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatDateInputValue, formatTiyin } from '@/shared/formatters'
import {
  useFinanceStore,
  type Expense,
  type ExpenseCategory,
  type Income,
  type IncomeType,
  type LedgerStatus,
  type MoneyMethod,
} from '@/shared/stores/finance'
import { useFilesStore } from '@/shared/stores/files'
import { useOrdersStore } from '@/shared/stores/orders'
import { useWorkshopStore } from '@/shared/stores/workshop'

const route = useRoute()
const permissions = useWorkshopPermissions()
const toast = useToast()
const finance = useFinanceStore()
const files = useFilesStore()
const orders = useOrdersStore()
const workshop = useWorkshopStore()
const now = new Date()
const today = formatDateInputValue(now)
const activeTab = ref<'expense' | 'income'>(financeLedgerTabFromPath(route.path))
const financeTabs: ChoiceOption[] = [
  { value: 'expense', label: 'Xarajatlar' },
  { value: 'income', label: 'Tushumlar' },
]
// One component serves both /finance/income and /finance/expenses; Vue Router reuses
// the instance, so the active tab must track the path rather than only the initial setup.
watch(
  () => route.path,
  (path) => {
    activeTab.value = financeLedgerTabFromPath(path)
  },
)
const formMode = ref<'expense' | 'income' | null>(null)
const editingExpenseId = ref<string | null>(null)
const editingIncomeId = ref<string | null>(null)
const saving = ref(false)
const actionError = ref<string | null>(null)
const actionTraceId = ref<string | null>(null)
const orderBalanceLoading = ref(false)
const orderBalanceError = ref<string | null>(null)
const orderBalanceTraceId = ref<string | null>(null)
const voidTarget = ref<{ kind: 'expense' | 'income'; id: string } | null>(null)
const voidReason = ref('')
const dateFrom = ref(formatDateInputValue(new Date(now.getFullYear(), now.getMonth(), 1)))
const dateTo = ref(today)
const filterBranchId = ref('all')
const expenseCategory = ref('all')
const incomeType = ref('all')
const statusFilter = ref<LedgerStatus | 'all'>('recorded')
const expenseFormPanel = ref<HTMLElement | null>(null)
const incomeFormPanel = ref<HTMLElement | null>(null)
const voidFormPanel = ref<HTMLElement | null>(null)
const lastFormTrigger = ref<HTMLElement | null>(null)
let orderBalanceRequestId = 0

const expenseForm = reactive({
  branchId: 'workshop',
  category: 'other' as ExpenseCategory,
  amount: '',
  incurredOn: today,
  vendor: '',
  description: '',
  receiptFileId: null as string | null,
  receiptName: '',
})
const incomeForm = reactive({
  type: 'order_payment' as IncomeType,
  branchId: 'workshop',
  orderId: '',
  amount: '',
  method: 'cash' as MoneyMethod,
  receivedOn: today,
  note: '',
  receiptFileId: null as string | null,
  receiptName: '',
})

const canManageFinance = computed(() => permissions.can(p.manageFinance))
const financeBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, [p.manageFinance]),
)
const branchOptions = computed(() => [
  ...(permissions.isOwner.value
    ? [
        {
          value: 'workshop',
          label: 'Ustaxona-keng',
          meta: 'filialsiz yozuv',
          status: 'active' as const,
        },
      ]
    : []),
  ...financeBranches.value.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  })),
])
const filterBranchOptions = computed(() => [
  {
    value: 'all',
    label: permissions.isOwner.value ? 'Hamma filiallar' : 'Mening filiallarim',
    meta: 'ruxsat doirasi',
    status: 'active' as const,
  },
  ...financeBranches.value.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  })),
])
const orderOptions = computed(() => [
  { value: '', label: 'Buyurtmani tanlang', meta: 'to`lov bog`lanadi', status: 'pending' as const },
  ...orders.workshopOrders
    .filter((order) => {
      if (order.status === 'cancelled') return false
      if (incomeForm.branchId === 'workshop') return true
      return order.branch_id === incomeForm.branchId
    })
    .map((order) => ({
      value: order.id,
      label: `${order.order_number} · ${order.contact_name}`,
      meta: formatTiyin(order.total_tiyin),
      status: order.status === 'completed' ? ('active' as const) : ('pending' as const),
    })),
])
const selectedIncomeOrderDetail = computed(() =>
  orders.currentOrder?.id === incomeForm.orderId ? orders.currentOrder : null,
)
const selectedIncomeSettlement = computed(() => selectedIncomeOrderDetail.value?.settlement ?? null)
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

watch(
  () => incomeForm.branchId,
  () => {
    if (incomeForm.branchId === 'workshop' || !incomeForm.orderId) return
    const selectedOrder = orders.workshopOrders.find((order) => order.id === incomeForm.orderId)
    if (selectedOrder && selectedOrder.branch_id !== incomeForm.branchId) incomeForm.orderId = ''
  },
)

watch(
  () => incomeForm.orderId,
  (orderId) => {
    if (!orderId || incomeForm.type !== 'order_payment') return
    const selectedOrder = orders.workshopOrders.find((order) => order.id === orderId)
    if (selectedOrder) incomeForm.branchId = selectedOrder.branch_id
    void loadSelectedOrderBalance(orderId)
  },
)

watch(
  () => incomeForm.type,
  (type) => {
    if (type !== 'order_payment') {
      orderBalanceError.value = null
      orderBalanceTraceId.value = null
      return
    }
    if (incomeForm.orderId) void loadSelectedOrderBalance(incomeForm.orderId)
  },
)

function branchName(branchId: string | null) {
  if (!branchId) return 'ustaxona-keng'
  return workshop.branches.find((branch) => branch.id === branchId)?.name ?? 'Filial'
}

function incomeOrderLabel(orderId: string | null) {
  return financeOrderReferenceLabel(orderId, orders.workshopOrders, orders.currentOrder)
}

function amountTiyin(value: string) {
  const parsed = Number(value.replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed * 100) : 0
}

function moneyInputValue(tiyin: number) {
  return String(Math.max(tiyin, 0) / 100)
}

async function loadSelectedOrderBalance(orderId: string) {
  const requestId = ++orderBalanceRequestId
  orderBalanceLoading.value = true
  orderBalanceError.value = null
  orderBalanceTraceId.value = null
  await orders.loadWorkshopOrder(orderId)
  if (requestId !== orderBalanceRequestId || incomeForm.orderId !== orderId) return
  if (orders.error) {
    orderBalanceError.value = workshopErrorMessage(orders.error)
    orderBalanceTraceId.value = orders.traceId
  } else if (selectedIncomeSettlement.value && !editingIncomeId.value) {
    incomeForm.amount = moneyInputValue(selectedIncomeSettlement.value.balance_tiyin)
  }
  orderBalanceLoading.value = false
}

async function refresh() {
  const base = {
    date_from: dateFrom.value,
    date_to: dateTo.value,
    branch_id: filterBranchId.value === 'all' ? null : filterBranchId.value,
    status: statusFilter.value === 'all' ? null : statusFilter.value,
  }
  if (activeTab.value === 'expense') {
    await finance.loadExpenses({
      ...base,
      category: expenseCategory.value === 'all' ? null : (expenseCategory.value as ExpenseCategory),
    })
    return
  }
  await finance.loadIncome({
    ...base,
    type: incomeType.value === 'all' ? null : (incomeType.value as IncomeType),
  })
}

watch(activeTab, (next, previous) => {
  if (next === previous) return
  void refresh()
})

function resetExpenseForm() {
  editingExpenseId.value = null
  expenseForm.branchId = permissions.isOwner.value
    ? 'workshop'
    : (financeBranches.value[0]?.id ?? 'workshop')
  expenseForm.category = 'other'
  expenseForm.amount = ''
  expenseForm.incurredOn = today
  expenseForm.vendor = ''
  expenseForm.description = ''
  expenseForm.receiptFileId = null
  expenseForm.receiptName = ''
}

function resetIncomeForm() {
  editingIncomeId.value = null
  incomeForm.type = 'order_payment'
  incomeForm.branchId = permissions.isOwner.value
    ? 'workshop'
    : (financeBranches.value[0]?.id ?? 'workshop')
  incomeForm.orderId = ''
  incomeForm.amount = ''
  incomeForm.method = 'cash'
  incomeForm.receivedOn = today
  incomeForm.note = ''
  incomeForm.receiptFileId = null
  incomeForm.receiptName = ''
  orderBalanceRequestId += 1
  orderBalanceLoading.value = false
  orderBalanceError.value = null
  orderBalanceTraceId.value = null
}

function rememberTrigger(event?: Event) {
  const target = event?.currentTarget
  lastFormTrigger.value = target instanceof HTMLElement ? target : null
}

async function focusFirstField(panel: () => HTMLElement | null) {
  await nextTick()
  const current = panel()
  current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  const field = current?.querySelector<HTMLElement>(
    'input:not([disabled]), textarea:not([disabled]), button:not([disabled]), [role="combobox"]:not([aria-disabled="true"])',
  )
  field?.focus({ preventScroll: true })
}

function restoreLastTrigger() {
  void nextTick(() => lastFormTrigger.value?.focus())
}

function openCreateExpense(event?: Event) {
  rememberTrigger(event)
  resetExpenseForm()
  activeTab.value = 'expense'
  const opening = formMode.value !== 'expense'
  formMode.value = opening ? 'expense' : null
  if (opening) void focusFirstField(() => expenseFormPanel.value)
  else restoreLastTrigger()
}

function openCreateIncome(event?: Event) {
  rememberTrigger(event)
  resetIncomeForm()
  activeTab.value = 'income'
  const opening = formMode.value !== 'income'
  formMode.value = opening ? 'income' : null
  if (opening) void focusFirstField(() => incomeFormPanel.value)
  else restoreLastTrigger()
}

function editExpense(expense: Expense, event?: Event) {
  rememberTrigger(event)
  activeTab.value = 'expense'
  formMode.value = 'expense'
  editingExpenseId.value = expense.id
  expenseForm.branchId = expense.branch_id ?? 'workshop'
  expenseForm.category = expense.category
  expenseForm.amount = String(expense.amount_tiyin / 100)
  expenseForm.incurredOn = expense.incurred_on
  expenseForm.vendor = expense.vendor ?? ''
  expenseForm.description = expense.description
  expenseForm.receiptFileId = expense.receipt_file_id
  expenseForm.receiptName = expense.receipt_file_id ? 'Biriktirilgan chek' : ''
  void focusFirstField(() => expenseFormPanel.value)
}

function editIncome(income: Income, event?: Event) {
  rememberTrigger(event)
  activeTab.value = 'income'
  formMode.value = 'income'
  editingIncomeId.value = income.id
  incomeForm.type = income.type
  incomeForm.branchId = income.branch_id ?? 'workshop'
  incomeForm.orderId = income.order_id ?? ''
  incomeForm.amount = String(income.amount_tiyin / 100)
  incomeForm.method = income.method
  incomeForm.receivedOn = income.received_on
  incomeForm.note = income.note ?? ''
  incomeForm.receiptFileId = income.receipt_file_id
  incomeForm.receiptName = income.receipt_file_id ? 'Biriktirilgan chek' : ''
  if (income.order_id) void loadSelectedOrderBalance(income.order_id)
  void focusFirstField(() => incomeFormPanel.value)
}

function closeForm() {
  formMode.value = null
  editingExpenseId.value = null
  editingIncomeId.value = null
  restoreLastTrigger()
}

function openVoidForm(kind: 'expense' | 'income', id: string, event?: Event) {
  rememberTrigger(event)
  voidTarget.value = { kind, id }
  voidReason.value = ''
  void focusFirstField(() => voidFormPanel.value)
}

function closeVoidForm() {
  voidTarget.value = null
  voidReason.value = ''
  restoreLastTrigger()
}

function applyExpensePresetFromRoute() {
  if (route.query.preset !== 'salary') return
  const workerName = typeof route.query.worker === 'string' ? route.query.worker : ''
  activeTab.value = 'expense'
  resetExpenseForm()
  formMode.value = 'expense'
  expenseForm.category = 'salary'
  expenseForm.vendor = workerName
  expenseForm.description = workerName ? `Maosh: ${workerName}` : 'Maosh'
}

async function saveExpense() {
  if (!canManageFinance.value) return
  saving.value = true
  actionError.value = null
  actionTraceId.value = null
  try {
    const payload = {
      branch_id: expenseForm.branchId === 'workshop' ? null : expenseForm.branchId,
      category: expenseForm.category,
      amount_tiyin: amountTiyin(expenseForm.amount),
      incurred_on: expenseForm.incurredOn,
      vendor: expenseForm.vendor || null,
      description: expenseForm.description,
      receipt_file_id: expenseForm.receiptFileId,
    }
    const wasEditing = Boolean(editingExpenseId.value)
    if (editingExpenseId.value) await finance.updateExpense(editingExpenseId.value, payload)
    else await finance.createExpense(payload)
    closeForm()
    await refresh()
    toast.success(wasEditing ? 'Xarajat saqlandi.' : 'Xarajat yozildi.')
  } catch {
    actionError.value = workshopErrorMessage(finance.actionError ?? 'expense_save_failed')
    actionTraceId.value = finance.actionTraceId
  } finally {
    saving.value = false
  }
}

async function saveIncome() {
  if (!canManageFinance.value) return
  saving.value = true
  actionError.value = null
  actionTraceId.value = null
  try {
    const payload = {
      type: incomeForm.type,
      branch_id: incomeForm.branchId === 'workshop' ? null : incomeForm.branchId,
      order_id: incomeForm.type === 'order_payment' ? incomeForm.orderId || null : null,
      amount_tiyin: amountTiyin(incomeForm.amount),
      method: incomeForm.method,
      received_on: incomeForm.receivedOn,
      note: incomeForm.note || null,
      receipt_file_id: incomeForm.receiptFileId,
    }
    const wasEditing = Boolean(editingIncomeId.value)
    if (editingIncomeId.value) {
      await finance.updateIncome(editingIncomeId.value, {
        branch_id:
          incomeForm.type === 'order_payment'
            ? undefined
            : incomeForm.branchId === 'workshop'
              ? null
              : incomeForm.branchId,
        amount_tiyin: payload.amount_tiyin,
        method: payload.method,
        received_on: payload.received_on,
        note: payload.note,
        receipt_file_id: payload.receipt_file_id,
      })
    } else {
      await finance.createIncome(payload)
    }
    closeForm()
    await refresh()
    toast.success(wasEditing ? 'Tushum saqlandi.' : 'Tushum yozildi.')
  } catch {
    actionError.value = workshopErrorMessage(finance.actionError ?? 'income_save_failed')
    actionTraceId.value = finance.actionTraceId
  } finally {
    saving.value = false
  }
}

async function uploadExpenseReceipt(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  actionError.value = null
  actionTraceId.value = null
  try {
    const uploaded = await files.upload(file)
    expenseForm.receiptFileId = uploaded.id
    expenseForm.receiptName = uploaded.original_name
    toast.success('Chek biriktirildi.')
  } catch {
    actionError.value = workshopErrorMessage(files.error ?? 'file_upload_failed')
    actionTraceId.value = files.traceId
  }
}

async function uploadIncomeReceipt(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  actionError.value = null
  actionTraceId.value = null
  try {
    const uploaded = await files.upload(file)
    incomeForm.receiptFileId = uploaded.id
    incomeForm.receiptName = uploaded.original_name
    toast.success('Chek biriktirildi.')
  } catch {
    actionError.value = workshopErrorMessage(files.error ?? 'file_upload_failed')
    actionTraceId.value = files.traceId
  }
}

function removeExpenseReceipt() {
  expenseForm.receiptFileId = null
  expenseForm.receiptName = ''
}

function removeIncomeReceipt() {
  incomeForm.receiptFileId = null
  incomeForm.receiptName = ''
}

async function confirmVoid() {
  if (!voidTarget.value || !voidReason.value.trim() || !canManageFinance.value) return
  actionError.value = null
  actionTraceId.value = null
  saving.value = true
  try {
    if (voidTarget.value.kind === 'expense')
      await finance.voidExpense(voidTarget.value.id, voidReason.value)
    else await finance.voidIncome(voidTarget.value.id, voidReason.value)
    closeVoidForm()
    await refresh()
    toast.success('Yozuv bekor qilindi.')
  } catch {
    actionError.value = workshopErrorMessage(finance.actionError ?? 'ledger_void_failed')
    actionTraceId.value = finance.actionTraceId
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  const firstBranchId = financeBranches.value[0]?.id
  if (!permissions.isOwner.value && firstBranchId) {
    expenseForm.branchId = firstBranchId
    incomeForm.branchId = firstBranchId
  }
  applyExpensePresetFromRoute()
  if (formMode.value === 'expense') void focusFirstField(() => expenseFormPanel.value)
  if (!canManageFinance.value) return
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
      </div>
      <div class="tools">
        <button
          v-if="canManageFinance"
          type="button"
          class="mp-button mp-button-outline"
          @click="openCreateIncome($event)"
        >
          Tushum
        </button>
        <button
          v-if="canManageFinance"
          type="button"
          class="mp-button mp-button-primary"
          @click="openCreateExpense($event)"
        >
          Xarajat
        </button>
      </div>
    </div>

    <section v-if="!canManageFinance" class="st-empty">
      <h3>Tushum va xarajat yozuvlariga ruxsatingiz yo'q</h3>
      <p>Bu bo'limda yozuv kiritish yoki tuzatish uchun moliya boshqaruvi ruxsati kerak.</p>
    </section>

    <template v-else>
      <AppTabs
        v-model="activeTab"
        id-prefix="workshop-finance-ledger"
        label="Moliya yozuvlari"
        :tabs="financeTabs"
      />

      <section v-if="formMode === 'expense'" ref="expenseFormPanel" class="card mb-4">
        <div class="card-h">
          <h2>{{ editingExpenseId ? 'Xarajatni tahrirlash' : 'Xarajat yozish' }}</h2>
        </div>
        <form class="card-b grid gap-3 md:grid-cols-2 xl:grid-cols-4" @submit.prevent="saveExpense">
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
            <input
              v-model="expenseForm.incurredOn"
              type="date"
              class="mp-input"
              :max="today"
              required
            />
          </label>
          <label class="field md:col-span-2">
            <span>Chek</span>
            <FilePicker
              accept="image/png,image/jpeg,image/webp,application/pdf"
              :uploading="files.uploading"
              :selected-name="expenseForm.receiptName"
              removable
              @change="uploadExpenseReceipt"
              @remove="removeExpenseReceipt"
            />
          </label>
          <div class="flex items-end gap-2 md:col-span-2">
            <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
              {{ saving ? 'Saqlanmoqda' : editingExpenseId ? 'Saqlash' : 'Yozish' }}
            </button>
            <button type="button" class="mp-button mp-button-outline" @click="closeForm">
              Bekor
            </button>
          </div>
        </form>
      </section>

      <section v-if="formMode === 'income'" ref="incomeFormPanel" class="card mb-4">
        <div class="card-h">
          <h2>{{ editingIncomeId ? 'Tushumni tahrirlash' : 'Tushum yozish' }}</h2>
        </div>
        <form class="card-b grid gap-3 md:grid-cols-2 xl:grid-cols-4" @submit.prevent="saveIncome">
          <ProjectDropdown
            v-if="!editingIncomeId"
            v-model="incomeForm.type"
            label="Turi"
            :options="createIncomeTypeOptions"
          />
          <label v-else class="field">
            <span>Turi</span>
            <input
              class="mp-input"
              :value="incomeTypeLabel[incomeForm.type] ?? incomeForm.type"
              disabled
            />
          </label>
          <ProjectDropdown
            v-if="incomeForm.type === 'order_payment' && !editingIncomeId"
            v-model="incomeForm.orderId"
            label="Buyurtma"
            :options="orderOptions"
          />
          <label v-else-if="incomeForm.type === 'order_payment'" class="field">
            <span>Buyurtma</span>
            <input class="mp-input" :value="incomeOrderLabel(incomeForm.orderId)" disabled />
          </label>
          <div
            v-if="incomeForm.type === 'order_payment' && incomeForm.orderId"
            class="rounded-md border border-hairline bg-sunk p-3 text-sm md:col-span-2"
          >
            <p v-if="orderBalanceLoading" class="font-bold text-ink-soft">Qoldiq yuklanmoqda...</p>
            <p v-else-if="orderBalanceError" class="font-bold text-danger">
              {{ orderBalanceError }} · trace_id: {{ orderBalanceTraceId ?? 'unavailable' }}
            </p>
            <div v-else-if="selectedIncomeSettlement" class="grid gap-2 md:grid-cols-[1fr_auto]">
              <div class="grid gap-1 text-ink-soft">
                <span>Jami: {{ formatTiyin(selectedIncomeSettlement.total_tiyin) }}</span>
                <span>Yozilgan: {{ formatTiyin(selectedIncomeSettlement.recorded_tiyin) }}</span>
                <b class="text-ink"
                  >Qoldiq: {{ formatTiyin(selectedIncomeSettlement.balance_tiyin) }}</b
                >
              </div>
              <button
                type="button"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                @click="incomeForm.amount = moneyInputValue(selectedIncomeSettlement.balance_tiyin)"
              >
                Qoldiqni kiritish
              </button>
            </div>
            <p v-else class="font-bold text-ink-soft">Qoldiq ma'lumoti topilmadi.</p>
          </div>
          <label class="field">
            <span>Summa (to'liq yoki qisman)</span>
            <input v-model="incomeForm.amount" class="mp-input" inputmode="numeric" required />
          </label>
          <ProjectDropdown v-model="incomeForm.method" label="Usul" :options="methodOptions" />
          <ProjectDropdown v-model="incomeForm.branchId" label="Filial" :options="branchOptions" />
          <label class="field">
            <span>Qabul sanasi</span>
            <input
              v-model="incomeForm.receivedOn"
              type="date"
              class="mp-input"
              :max="today"
              required
            />
          </label>
          <label class="field md:col-span-2">
            <span>Izoh</span>
            <input v-model="incomeForm.note" class="mp-input" placeholder="kassa yoki bank izohi" />
          </label>
          <label class="field md:col-span-2">
            <span>Chek</span>
            <FilePicker
              accept="image/png,image/jpeg,image/webp,application/pdf"
              :uploading="files.uploading"
              :selected-name="incomeForm.receiptName"
              removable
              @change="uploadIncomeReceipt"
              @remove="removeIncomeReceipt"
            />
          </label>
          <div class="flex items-end gap-2 md:col-span-2">
            <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
              {{ saving ? 'Saqlanmoqda' : editingIncomeId ? 'Saqlash' : 'Yozish' }}
            </button>
            <button type="button" class="mp-button mp-button-outline" @click="closeForm">
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

      <section
        v-else-if="activeTab === 'expense'"
        id="workshop-finance-ledger-expense-panel"
        class="card"
        role="tabpanel"
        aria-labelledby="workshop-finance-ledger-expense-tab"
        tabindex="0"
      >
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Sana</th>
                <th>Kategoriya</th>
                <th>Tavsif</th>
                <th>Filial</th>
                <th>Yetkazib beruvchi</th>
                <th>Chek</th>
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
                <td>
                  <span v-if="expense.receipt_file_id" class="pill p-ok">
                    <span class="pd"></span>Bor
                  </span>
                  <span v-else class="text-ink-muted">—</span>
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
                    class="mp-button mp-button-outline mr-2 min-h-8 px-2 text-xs"
                    @click="editExpense(expense, $event)"
                  >
                    Tahrir
                  </button>
                  <button
                    v-if="canManageFinance && expense.status === 'recorded'"
                    type="button"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                    @click="openVoidForm('expense', expense.id, $event)"
                  >
                    Bekor qilish
                  </button>
                </td>
              </tr>
              <tr v-if="finance.expenses.length === 0">
                <td colspan="9">
                  <div class="st-empty !border-0 !py-8"><h3>Bu davrda xarajat yo'q</h3></div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section
        v-else
        id="workshop-finance-ledger-income-panel"
        class="card"
        role="tabpanel"
        aria-labelledby="workshop-finance-ledger-income-tab"
        tabindex="0"
      >
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
                <th>Chek</th>
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
                <td>{{ incomeOrderLabel(income.order_id) }}</td>
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
                <td>
                  <span v-if="income.receipt_file_id" class="pill p-ok">
                    <span class="pd"></span>Bor
                  </span>
                  <span v-else class="text-ink-muted">—</span>
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
                    class="mp-button mp-button-outline mr-2 min-h-8 px-2 text-xs"
                    @click="editIncome(income, $event)"
                  >
                    Tahrir
                  </button>
                  <button
                    v-if="canManageFinance && income.status === 'recorded'"
                    type="button"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                    @click="openVoidForm('income', income.id, $event)"
                  >
                    Bekor qilish
                  </button>
                </td>
              </tr>
              <tr v-if="finance.incomes.length === 0">
                <td colspan="10">
                  <div class="st-empty !border-0 !py-8"><h3>Bu davrda tushum yo'q</h3></div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <form
        v-if="voidTarget"
        ref="voidFormPanel"
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
        <button type="button" class="mp-button mp-button-outline self-end" @click="closeVoidForm">
          Bekor
        </button>
      </form>

      <div v-if="actionError" class="banner danger mt-4">
        <div class="grow">{{ actionError }} · trace_id: {{ actionTraceId ?? 'unavailable' }}</div>
      </div>
    </template>
  </section>
</template>
