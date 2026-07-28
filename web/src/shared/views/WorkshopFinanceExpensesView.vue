<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { presetRange, type DateRangePreset } from '@/shared/app/dateRange'
import { traceLine, traceSuffix } from '@/shared/app/errorTrace'
import {
  exceedsOrderBalance,
  financeIncomeOrderLabel,
  financeLedgerTabFromPath,
  incomeSettlementView,
} from '@/shared/app/financeLedger'
import { sanitizeMoneyInput } from '@/shared/app/inputSanitizers'
import type { DropdownOption } from '@/shared/app/roleConfig'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import ActionMenu, { type ActionMenuItem } from '@/shared/components/ActionMenu.vue'
import AppModal from '@/shared/components/AppModal.vue'
import AppTabs from '@/shared/components/AppTabs.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import DateField from '@/shared/components/DateField.vue'
import FilterStatus from '@/shared/components/FilterStatus.vue'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'
import FilePicker from '@/shared/components/FilePicker.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import PayableOrderOption from '@/shared/components/PayableOrderOption.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import SegmentedControl from '@/shared/components/SegmentedControl.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatDate,
  formatDateInputValue,
  formatDateTime,
  formatTiyin,
  parseSomToTiyin,
} from '@/shared/formatters'
import {
  useFinanceStore,
  type Expense,
  type ExpenseCategory,
  type Income,
  type IncomeOrderRef,
  type IncomeType,
  type LedgerStatus,
  type MoneyMethod,
  type PayableOrder,
} from '@/shared/stores/finance'
import { useFilesStore } from '@/shared/stores/files'
import { useWorkshopStore } from '@/shared/stores/workshop'

const route = useRoute()
const router = useRouter()
const permissions = useWorkshopPermissions()
const toast = useToast()
const finance = useFinanceStore()
const files = useFilesStore()
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
const expenseModalOpen = ref(false)
const incomeModalOpen = ref(false)
const editingExpenseId = ref<string | null>(null)
const editingIncomeId = ref<string | null>(null)
const saving = ref(false)
const actionError = ref<string | null>(null)
const actionTraceId = ref<string | null>(null)
// The missing-order failure belongs on the field the operator must fix, not in
// a banner three hundred pixels below it.
const incomeOrderError = ref<string | null>(null)
const incomeOrderCombobox = ref<InstanceType<typeof SearchCombobox> | null>(null)
const voidTarget = ref<{ kind: 'expense' | 'income'; id: string } | null>(null)
const voidReason = ref('')
const initialRange = presetRange('month', now)
const datePreset = ref<DateRangePreset>('month')
const dateFrom = ref(initialRange.from ?? '')
const dateTo = ref(initialRange.to ?? '')
const expenseCategory = ref('all')
const incomeType = ref('all')
const statusFilter = ref<LedgerStatus | 'all'>('recorded')

// «Narrowed» means narrower than the page's own defaults — the current month,
// every category, recorded rows. Those defaults are the resting state, so they
// must not make the status line claim a filter is on (QAD-182).
const DEFAULT_STATUS: LedgerStatus | 'all' = 'recorded'
// With the status filter pinned to one value, every row's Holat cell says the
// same word — a column restating the filter above it (QAD-182).
const showStatusColumn = computed(() => statusFilter.value === 'all')
const narrowingFilters = computed(() => {
  const applied: string[] = []
  if (datePreset.value !== 'month') applied.push('date')
  if (activeTab.value === 'expense' && expenseCategory.value !== 'all') applied.push('category')
  if (activeTab.value === 'income' && incomeType.value !== 'all') applied.push('type')
  if (statusFilter.value !== DEFAULT_STATUS) applied.push('status')
  return applied
})

// The sum of exactly the rows on screen. A ledger that lists eight expenses and
// never states what they add up to is asking the accountant to do arithmetic
// the page already did (QAD-182).
const periodTotalTiyin = computed(() => {
  const rows = activeTab.value === 'expense' ? finance.expenses : finance.incomes
  return rows.reduce((sum, row) => sum + row.amount_tiyin, 0)
})

function resetLedgerFilters() {
  const range = presetRange('month', new Date())
  datePreset.value = 'month'
  dateFrom.value = range.from ?? ''
  dateTo.value = range.to ?? ''
  expenseCategory.value = 'all'
  incomeType.value = 'all'
  statusFilter.value = DEFAULT_STATUS
}

// Select-bound fields are `string | null` (FormSelect/SearchCombobox model type,
// same convention as the inventory modals); payloads coerce before sending.
// Branch comes from the topbar context — the forms only keep the owner's
// «Ustaxona darajasida» escape hatch for HQ-level (branchless) expenses.
// `mode` mirrors the income form's Turi toggle: money out is either against a
// supplier faktura or it is misc, exactly as money in is against an order or
// misc. In `invoice` mode the invoice owns supplier and branch.
// The toggle mirrors the income form; the default deliberately does not. Seven
// of the ten expense categories can never be a faktura payment (salary alone is
// booked by hand, monthly, per worker), and the invoice path has its own warm
// entry point — Ombor's «Saqlash va xarajat yozish» deep-links with
// `invoice_id` and forces `invoice` below, regardless of this default (as
// Qarzdorlik's «To'lov qilish» forces `other` with its `supplier_id`). Whoever
// reaches the cold «+ Xarajat» button is precisely the population that did not
// come from an invoice. The failure costs are asymmetric too: an invoice default
// dead-ends a filled-in misc expense at save time, while a misc default costs
// one click and loses nothing, since picking an invoice only adds.
const expenseForm = reactive({
  mode: 'other' as string,
  workshopLevel: false,
  category: 'other' as string | null,
  amount: '',
  incurredOn: today,
  vendor: '',
  supplierId: null as string | null,
  invoiceId: null as string | null,
  description: '',
  receiptFileId: null as string | null,
  receiptName: '',
})
const incomeForm = reactive({
  type: 'order_payment' as string | null,
  orderId: null as string | null,
  amount: '',
  method: 'cash' as string | null,
  receivedOn: today,
  note: '',
  receiptFileId: null as string | null,
  receiptName: '',
})
// Editing must never re-stamp a record onto the currently active branch — the
// original branch is preserved and sent back unchanged.
const editingExpenseBranchId = ref<string | null>(null)
// The `K-…` of the faktura an edited expense pays. It comes off the record
// itself, not the picker: the picker only carries invoices that still owe
// something, and paying one in full is exactly what drops it out of that list.
const editingExpenseInvoiceNo = ref<string | null>(null)
const editingIncomeBranchId = ref<string | null>(null)
// The income being edited already sits inside its order's `recorded` total, so
// the inline over-balance check adds it back — the same headroom the server's
// cap computes with `exclude_income_id`.
const editingIncomeAmountTiyin = ref(0)
// The picked row is kept out of `finance.payableOrders`: the next search
// replaces that list, and the selection must survive it.
const selectedPayableOrder = ref<PayableOrder | null>(null)
// The order of the income being edited, as that income's own row carries it.
// A settled order is no longer a picker candidate, so this is the only source.
const editingIncomeOrder = ref<IncomeOrderRef | null>(null)
const incomeOrderQuery = ref('')

// Type-time sanitization (PhoneInput precedent): an invalid character never
// sticks; parseSomToTiyin still owns whether the kept characters make sense.
watch(
  () => expenseForm.amount,
  (value) => {
    const clean = sanitizeMoneyInput(value)
    if (clean !== value) expenseForm.amount = clean
  },
)
watch(
  () => incomeForm.amount,
  (value) => {
    const clean = sanitizeMoneyInput(value)
    if (clean !== value) incomeForm.amount = clean
  },
)

const canManageFinance = computed(() => permissions.can(p.manageFinance))
const financeBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, [p.manageFinance]),
)
// Branch is driven by the topbar context picker (AppShell); the page follows it
// and falls back to the first accessible branch until context is set.
const selectedBranchId = computed(() => {
  const context = workshop.selectedBranchContext
  if (context && financeBranches.value.some((branch) => branch.id === context)) return context
  return financeBranches.value[0]?.id ?? ''
})
// The picker is server-filtered: the backend already scoped the rows to the
// branch and to "still owes money", and it searched fields the option text
// doesn't carry (the phone). Re-filtering here would hide its own matches.
const payableOrderOptions = computed<ChoiceOption[]>(() =>
  finance.payableOrders.map((order) => ({
    value: order.order_id,
    label: `${order.order_number} · ${order.contact_name}`,
    meta: formatTiyin(order.balance_tiyin),
  })),
)
const payableOrderById = computed<Record<string, PayableOrder>>(() =>
  Object.fromEntries(finance.payableOrders.map((order) => [order.order_id, order])),
)
// Optional supplier link on an expense — this is what makes it count as a
// payment in the supplier's debt fold. Inactive suppliers stay payable.
const supplierOptions = computed<ChoiceOption[]>(() =>
  workshop.suppliers.map((supplier) => ({
    value: supplier.id,
    label: supplier.name,
    meta: supplier.status === 'active' ? (supplier.phone ?? 'faol') : 'faol emas',
  })),
)

// A picked supplier fills the free-text vendor with its name unless the user
// already wrote something more specific.
watch(
  () => expenseForm.supplierId,
  (supplierId) => {
    if (!supplierId) return
    const supplier = workshop.suppliers.find((row) => row.id === supplierId)
    if (supplier && !expenseForm.vendor.trim()) expenseForm.vendor = supplier.name
  },
)

const expenseModes: ChoiceOption[] = [
  { value: 'invoice', label: "Kirim to'lovi" },
  { value: 'other', label: 'Boshqa xarajat' },
]
const isInvoicePayment = computed(() => expenseForm.mode === 'invoice')
const payableInvoiceOptions = computed<ChoiceOption[]>(() =>
  finance.payableInvoices.map((invoice) => ({
    value: invoice.id,
    label: `${invoice.invoice_no} · ${invoice.supplier_name ?? "ta'minotchisiz"}`,
    meta: `${formatDate(invoice.invoice_date)} · ${invoice.branch_name ?? '—'} · ${invoice.line_count} pozitsiya`,
  })),
)
const selectedInvoice = computed(
  () => finance.payableInvoices.find((row) => row.id === expenseForm.invoiceId) ?? null,
)
// The two fields the invoice takes over, spelled out so nothing is silently
// decided for the user. Category is deliberately NOT in this strip: the invoice
// only seeds it (`raw_materials`), and it stays editable above — claiming it
// came from the faktura next to a live dropdown would read as a lie.
const invoiceDerivedStrip = computed(() => {
  const invoice = selectedInvoice.value
  if (!invoice) return null
  return `${invoice.supplier_name ?? "ta'minotchisiz"} · ${invoice.branch_name ?? 'filialsiz'}`
})
// Overpayment is allowed on purpose — supplier prepayments are normal, and
// blocking them pushes staff into inventing workarounds. Warn, don't refuse.
const overpaysInvoice = computed(() => {
  const invoice = selectedInvoice.value
  if (!invoice || expenseAmountTiyin.value === null) return false
  return expenseAmountTiyin.value > invoice.outstanding_tiyin
})

// An invoice already implies raw materials; some shops book deliveries as
// supplies, so the default is a default, not a lock. Seeding only ever applies
// while writing a new expense — on an edit these same assignments would quietly
// rewrite a saved record's category, amount and description.
watch(
  () => expenseForm.invoiceId,
  (invoiceId) => {
    if (!invoiceId || editingExpenseId.value) return
    if (expenseForm.category === 'other') expenseForm.category = 'raw_materials'
    const invoice = finance.payableInvoices.find((row) => row.id === invoiceId)
    if (!invoice) return
    expenseForm.supplierId = invoice.supplier_id
    if (!expenseForm.description.trim()) {
      expenseForm.description = `${invoice.invoice_no} to'lovi`
    }
    if (!expenseForm.amount.trim()) expenseForm.amount = moneyInputValue(invoice.outstanding_tiyin)
  },
)
// Two sources, one shape, neither of them an order read. Creating: the picked
// picker row already carries the settlement. Editing: the income row carries
// its own order — the order it points at may long since have left the picker.
const selectedIncomeOrder = computed<IncomeOrderRef | PayableOrder | null>(() => {
  const editing = editingIncomeOrder.value
  if (editing && editing.order_id === incomeForm.orderId) return editing
  const picked = selectedPayableOrder.value
  if (picked && picked.order_id === incomeForm.orderId) return picked
  return null
})
// Shared by the filter dropdowns (compact skin ignores meta) and the modal
// FormSelects (meta renders as the option's hint line).
const categoryOptions: ChoiceOption[] = [
  { value: 'all', label: 'Hamma kategoriyalar', meta: 'filtr' },
  { value: 'rent', label: 'Ijara', meta: 'joy xarajati' },
  { value: 'utilities', label: 'Kommunal', meta: 'elektr/gaz/suv' },
  { value: 'raw_materials', label: 'Xom ashyo', meta: 'material xaridi' },
  { value: 'supplies', label: 'Aksessuar', meta: "mayda ta'minot" },
  { value: 'transport', label: 'Transport', meta: "yetkazish/yo'l" },
  { value: 'equipment', label: 'Texnika', meta: 'uskuna' },
  { value: 'marketing', label: 'Marketing', meta: 'reklama' },
  { value: 'taxes_and_fees', label: 'Soliqlar', meta: "majburiy to'lovlar" },
  { value: 'salary', label: 'Maosh', meta: "xodim to'lovi" },
  { value: 'other', label: 'Boshqalar', meta: 'tasniflanmagan' },
]
const createCategoryOptions = categoryOptions.filter((option) => option.value !== 'all')
const incomeTypeOptions: ChoiceOption[] = [
  { value: 'all', label: 'Hamma turlar', meta: 'filtr' },
  { value: 'order_payment', label: "Buyurtma to'lovi", meta: "buyurtmaga bog'langan" },
  { value: 'other', label: 'Boshqa tushum', meta: "qo'lda yozuv" },
]
const createIncomeTypeOptions = incomeTypeOptions.filter((option) => option.value !== 'all')
// One word per method. The three sit in a half-width segmented row, and
// «Bank / karta» ran past its segment at desktop width — a choice you can't
// read is not a visible choice. The card/terminal case lives in the meta line.
const methodOptions: ChoiceOption[] = [
  { value: 'cash', label: 'Naqd', meta: 'kassa' },
  { value: 'bank_transfer', label: 'Bank', meta: "o'tkazma yoki karta" },
  { value: 'other', label: 'Boshqa', meta: 'izohda yoziladi' },
]
const statusOptions: DropdownOption[] = [
  { value: 'recorded', label: 'Yozilgan', dot: 'success' },
  { value: 'voided', label: 'Bekor qilingan', dot: 'danger' },
  { value: 'all', label: 'Hammasi' },
]
const categoryLabel = Object.fromEntries(
  categoryOptions.map((option) => [option.value, option.label]),
)
const incomeTypeLabel = Object.fromEntries(
  incomeTypeOptions.map((option) => [option.value, option.label]),
)
const methodLabel = Object.fromEntries(methodOptions.map((option) => [option.value, option.label]))

watch(
  () => incomeForm.orderId,
  (orderId) => {
    if (!orderId) {
      selectedPayableOrder.value = null
      return
    }
    incomeOrderError.value = null
    if (incomeForm.type !== 'order_payment') return
    const picked = payableOrderById.value[orderId]
    if (!picked) return
    selectedPayableOrder.value = picked
    // Most counter payments settle the order outright, so the remaining
    // balance is the right default; the operator overtypes it for a part
    // payment.
    if (!editingIncomeId.value) incomeForm.amount = moneyInputValue(picked.balance_tiyin)
  },
)

watch(
  () => incomeForm.type,
  () => {
    incomeOrderError.value = null
  },
)

// The picker's candidates depend on the branch context and on the modal being
// an order payment at all — reload whenever any of those move.
watch([incomeModalOpen, selectedBranchId, () => incomeForm.type], () => {
  if (!incomeModalOpen.value || editingIncomeId.value) return
  if (incomeForm.type !== 'order_payment') return
  void loadPayableOrders()
})

function loadPayableOrders() {
  return finance.loadPayableOrders({
    branch_id: selectedBranchId.value || null,
    search: incomeOrderQuery.value || null,
  })
}

// Already debounced by the combobox — this is one request per pause, not per
// keystroke.
function onPayableOrderSearch(value: string) {
  incomeOrderQuery.value = value
  void loadPayableOrders()
}

// Names the record the void will hit — date · category/type · sum — so the
// confirmation identifies its target instead of a bare reason box.
// QAD-184: the row itself is the edit control, so it is clickable exactly where
// editing is allowed — a voided row, or a viewer without the permission, keeps
// the default cursor and no hover tint.
function canEditLedgerRow(status: LedgerStatus): boolean {
  return canManageFinance.value && status === 'recorded'
}

// Bekor qilish left the row for the ⋯ menu but keeps its word: a bare glyph is
// all that would stand between a mis-click and a voided money row.
const voidMenuItems: ActionMenuItem[] = [{ label: 'Bekor qilish', icon: 'ban', danger: true }]

// A tushum has no description column, so the type and the sum are what name the
// row for the control that acts on it.
function incomeRowLabel(income: Income): string {
  return `${incomeTypeLabel[income.type] ?? income.type} ${formatTiyin(income.amount_tiyin)}`
}

const voidTargetLabel = computed(() => {
  const target = voidTarget.value
  if (!target) return ''
  if (target.kind === 'expense') {
    const expense = finance.expenses.find((row) => row.id === target.id)
    if (!expense) return ''
    return `${formatDate(expense.incurred_on)} · ${categoryLabel[expense.category] ?? expense.category} · ${formatTiyin(expense.amount_tiyin)}`
  }
  const income = finance.incomes.find((row) => row.id === target.id)
  if (!income) return ''
  return `${formatDate(income.received_on)} · ${incomeTypeLabel[income.type] ?? income.type} · ${formatTiyin(income.amount_tiyin)}`
})

// Live-parsed amounts drive both the "= 12 500 000 so'm" preview under the
// input and the submit guard — an unparseable amount blocks the save instead
// of silently booking 0 (or a 1000x-smaller sum).
const AMOUNT_HINT = 'Summani tekshiring — masalan: 1 500 000'
const OVER_BALANCE_HINT = 'Qoldiqdan oshib ketdi'
const expenseAmountTiyin = computed(() => parseSomToTiyin(expenseForm.amount))
const incomeAmountTiyin = computed(() => parseSomToTiyin(incomeForm.amount))

// The figures the form is measured against, in the frame the operator is in:
// while editing, this income's own amount comes back out of «Yozilgan» and
// into «Qoldiq», so the summary's Qoldiq *is* what the Qoldiq button fills.
// One number, one word — the ceiling below reads straight off it.
const incomeSettlement = computed(() =>
  incomeForm.type === 'order_payment'
    ? incomeSettlementView(
        selectedIncomeOrder.value,
        editingIncomeId.value ? editingIncomeAmountTiyin.value : null,
      )
    : null,
)
// The most an order payment may still take. Null when there is nothing to cap
// against (other income, or no order picked yet).
const incomeAmountCeilingTiyin = computed(() => incomeSettlement.value?.balance_tiyin ?? null)
const incomeAmountOverBalance = computed(() =>
  exceedsOrderBalance(incomeAmountTiyin.value, incomeAmountCeilingTiyin.value),
)
const showRemainingBalanceButton = computed(
  () => incomeAmountCeilingTiyin.value !== null && incomeAmountCeilingTiyin.value > 0,
)
// Caught here so the operator sees the problem beside the field they typed it
// in; the server's cap stays the authority, this only saves the round trip.
const incomeAmountError = computed(() => {
  if (incomeForm.amount.trim() && incomeAmountTiyin.value === null) return AMOUNT_HINT
  if (incomeAmountOverBalance.value) return OVER_BALANCE_HINT
  return null
})

function moneyInputValue(tiyin: number) {
  return String(Math.max(tiyin, 0) / 100)
}

function fillRemainingBalance() {
  const ceiling = incomeAmountCeilingTiyin.value
  if (ceiling === null) return
  incomeForm.amount = moneyInputValue(ceiling)
}

async function refresh() {
  const base = {
    date_from: dateFrom.value,
    date_to: dateTo.value,
    branch_id: selectedBranchId.value || null,
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

// Filters auto-apply (the explicit "Qo'llash" button is gone). Debounced so a
// preset-driven from+to change or fast dropdown edits collapse into one fetch.
// activeTab is intentionally excluded — its own watcher above already refreshes.
let filterTimer: number | undefined
watch([dateFrom, dateTo, selectedBranchId, expenseCategory, incomeType, statusFilter], () => {
  window.clearTimeout(filterTimer)
  filterTimer = window.setTimeout(() => void refresh(), 250)
})

function resetExpenseForm() {
  editingExpenseId.value = null
  editingExpenseBranchId.value = null
  editingExpenseInvoiceNo.value = null
  expenseForm.mode = 'other'
  expenseForm.workshopLevel = false
  expenseForm.category = 'other'
  expenseForm.amount = ''
  expenseForm.incurredOn = today
  expenseForm.vendor = ''
  expenseForm.supplierId = null
  expenseForm.invoiceId = null
  expenseForm.description = ''
  expenseForm.receiptFileId = null
  expenseForm.receiptName = ''
}

function resetIncomeForm() {
  editingIncomeId.value = null
  editingIncomeBranchId.value = null
  editingIncomeAmountTiyin.value = 0
  editingIncomeOrder.value = null
  selectedPayableOrder.value = null
  incomeOrderQuery.value = ''
  incomeOrderError.value = null
  incomeForm.type = 'order_payment'
  incomeForm.orderId = null
  incomeForm.amount = ''
  incomeForm.method = 'cash'
  incomeForm.receivedOn = today
  incomeForm.note = ''
  incomeForm.receiptFileId = null
  incomeForm.receiptName = ''
}

// The modals own focus (useFocusTrap moves focus in, restores it on close) — no
// manual scroll-into-view / trigger-tracking machinery needed.
function clearActionError() {
  actionError.value = null
  actionTraceId.value = null
}

function openCreateExpense() {
  resetExpenseForm()
  clearActionError()
  expenseModalOpen.value = true
  void finance.loadPayableInvoices()
}

function openCreateIncome() {
  resetIncomeForm()
  clearActionError()
  incomeModalOpen.value = true
}

function editExpense(expense: Expense) {
  editingExpenseId.value = expense.id
  editingExpenseBranchId.value = expense.branch_id
  // The invoice link is fixed once written — an edit tunes the money, never
  // which faktura the money paid.
  expenseForm.mode = expense.invoice_id ? 'invoice' : 'other'
  expenseForm.invoiceId = expense.invoice_id
  editingExpenseInvoiceNo.value = expense.invoice_no
  expenseForm.workshopLevel = expense.branch_id === null
  expenseForm.category = expense.category
  expenseForm.amount = String(expense.amount_tiyin / 100)
  expenseForm.incurredOn = expense.incurred_on
  expenseForm.supplierId = expense.supplier_id
  expenseForm.vendor = expense.vendor ?? ''
  expenseForm.description = expense.description
  expenseForm.receiptFileId = expense.receipt_file_id
  expenseForm.receiptName = expense.receipt_file_id ? 'Biriktirilgan chek' : ''
  clearActionError()
  expenseModalOpen.value = true
}

function editIncome(income: Income) {
  editingIncomeId.value = income.id
  editingIncomeBranchId.value = income.branch_id
  editingIncomeAmountTiyin.value = income.amount_tiyin
  editingIncomeOrder.value = income.order
  selectedPayableOrder.value = null
  incomeOrderQuery.value = ''
  incomeOrderError.value = null
  incomeForm.type = income.type
  incomeForm.orderId = income.order_id ?? null
  incomeForm.amount = String(income.amount_tiyin / 100)
  incomeForm.method = income.method
  incomeForm.receivedOn = income.received_on
  incomeForm.note = income.note ?? ''
  incomeForm.receiptFileId = income.receipt_file_id
  incomeForm.receiptName = income.receipt_file_id ? 'Biriktirilgan chek' : ''
  clearActionError()
  incomeModalOpen.value = true
}

function closeExpenseModal() {
  expenseModalOpen.value = false
  editingExpenseId.value = null
}

function closeIncomeModal() {
  incomeModalOpen.value = false
  editingIncomeId.value = null
}

function openVoidForm(kind: 'expense' | 'income', id: string) {
  voidTarget.value = { kind, id }
  voidReason.value = ''
  clearActionError()
}

function closeVoidForm() {
  voidTarget.value = null
  voidReason.value = ''
}

async function saveExpense() {
  if (!canManageFinance.value) return
  if (expenseAmountTiyin.value === null) {
    actionError.value = AMOUNT_HINT
    actionTraceId.value = null
    return
  }
  if (isInvoicePayment.value && !editingExpenseId.value && !expenseForm.invoiceId) {
    actionError.value = "Kirimni tanlang yoki «Boshqa xarajat»ga o'ting."
    actionTraceId.value = null
    return
  }
  saving.value = true
  actionError.value = null
  actionTraceId.value = null
  try {
    // Create stamps the topbar context branch; edit keeps the record's own
    // branch. The owner's workshop-level checkbox overrides either to null.
    // An invoice payment overrides both — the server takes branch and supplier
    // from the invoice, so they are left out of the payload entirely.
    const invoicePayment = isInvoicePayment.value && Boolean(expenseForm.invoiceId)
    const common = {
      category: (expenseForm.category ?? 'other') as ExpenseCategory,
      amount_tiyin: expenseAmountTiyin.value,
      incurred_on: expenseForm.incurredOn,
      vendor: expenseForm.vendor || null,
      description: expenseForm.description,
      receipt_file_id: expenseForm.receiptFileId,
    }
    // Branch and supplier are sent only when the form owns them. On a faktura
    // payment the invoice does, and echoing our own copy back would be the one
    // way the two could drift apart.
    const owned = invoicePayment
      ? {}
      : {
          branch_id: expenseForm.workshopLevel
            ? null
            : editingExpenseId.value
              ? (editingExpenseBranchId.value ?? selectedBranchId.value ?? null)
              : selectedBranchId.value || null,
          supplier_id: expenseForm.supplierId,
        }
    const wasEditing = Boolean(editingExpenseId.value)
    if (editingExpenseId.value) {
      await finance.updateExpense(editingExpenseId.value, { ...common, ...owned })
    } else {
      await finance.createExpense({
        ...common,
        ...owned,
        ...(invoicePayment ? { invoice_id: expenseForm.invoiceId } : {}),
      })
    }
    closeExpenseModal()
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
  if (incomeAmountTiyin.value === null) {
    actionError.value = AMOUNT_HINT
    actionTraceId.value = null
    return
  }
  if (incomeAmountOverBalance.value) {
    actionError.value = OVER_BALANCE_HINT
    actionTraceId.value = null
    return
  }
  // Errored on the combobox itself, which then takes focus — the same
  // treatment the amount field gets. A banner at the foot of the form is too
  // far from the control that has to change.
  if (incomeForm.type === 'order_payment' && !incomeForm.orderId) {
    incomeOrderError.value = workshopErrorMessage('order_required')
    incomeOrderCombobox.value?.focus()
    return
  }
  saving.value = true
  actionError.value = null
  actionTraceId.value = null
  try {
    // Order payments derive their branch from the order server-side; other
    // income stamps the topbar context on create and keeps its branch on edit.
    const payload = {
      type: (incomeForm.type ?? 'other') as IncomeType,
      branch_id:
        incomeForm.type === 'order_payment'
          ? null
          : editingIncomeId.value
            ? editingIncomeBranchId.value
            : selectedBranchId.value || null,
      order_id: incomeForm.type === 'order_payment' ? incomeForm.orderId : null,
      amount_tiyin: incomeAmountTiyin.value,
      method: (incomeForm.method ?? 'cash') as MoneyMethod,
      received_on: incomeForm.receivedOn,
      note: incomeForm.note || null,
      receipt_file_id: incomeForm.receiptFileId,
    }
    const wasEditing = Boolean(editingIncomeId.value)
    if (editingIncomeId.value) {
      await finance.updateIncome(editingIncomeId.value, {
        branch_id: incomeForm.type === 'order_payment' ? undefined : payload.branch_id,
        amount_tiyin: payload.amount_tiyin,
        method: payload.method,
        received_on: payload.received_on,
        note: payload.note,
        receipt_file_id: payload.receipt_file_id,
      })
    } else {
      await finance.createIncome(payload)
    }
    closeIncomeModal()
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
  if (!canManageFinance.value) return
  if (selectedBranchId.value) {
    void workshop.loadSuppliers(selectedBranchId.value).catch(() => undefined)
  }
  // The ledger needs no order list: every income carries its own order label
  // and settlement, so no page of orders can be too short to name a row.
  await refresh()
  // Two deep-links land here with the modal pre-filled: Qarzdorlik's «To'lov
  // qilish» (counterparty picked) and Ombor's «Saqlash va xarajat yozish»
  // (invoice picked). The query is consumed once and cleared.
  if (route.query.create === 'expense') {
    openCreateExpense()
    const supplierId = route.query.supplier_id
    const invoiceId = route.query.invoice_id
    if (typeof invoiceId === 'string') {
      // The picker list must be in before the id can resolve to a row.
      await finance.loadPayableInvoices()
      expenseForm.mode = 'invoice'
      expenseForm.invoiceId = invoiceId
    } else if (typeof supplierId === 'string') {
      expenseForm.mode = 'other'
      expenseForm.supplierId = supplierId
    }
    void router.replace({ path: route.path })
  } else if (route.query.create === 'income') {
    openCreateIncome()
    void router.replace({ path: route.path })
  }
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Tushum va xarajat</h1>
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

      <AppModal
        :open="expenseModalOpen"
        :title="editingExpenseId ? 'Xarajatni tahrirlash' : 'Xarajat yozish'"
        max-width="max-w-2xl"
        @close="closeExpenseModal"
      >
        <form class="grid gap-3 md:grid-cols-2" @submit.prevent="saveExpense">
          <SegmentedControl
            v-if="!editingExpenseId"
            v-model="expenseForm.mode"
            label="Turi"
            :options="expenseModes"
          />
          <label v-else class="field">
            <span>Turi</span>
            <input
              class="mp-input"
              :value="expenseForm.invoiceId ? `Kirim to'lovi` : 'Boshqa xarajat'"
              disabled
            />
          </label>

          <!-- Kirim to'lovi: the invoice decides supplier, branch, and what is
               still owed; the form only asks for money, date, and category. -->
          <template v-if="isInvoicePayment">
            <SearchCombobox
              v-if="!editingExpenseId"
              v-model="expenseForm.invoiceId"
              label="Kirim (faktura)"
              :options="payableInvoiceOptions"
              placeholder="K-0007 yoki ta'minotchi"
              no-results-text="To'lanmagan kirim topilmadi"
              clearable
            />
            <label v-else class="field">
              <span>Kirim (faktura)</span>
              <input
                class="mp-input"
                :value="editingExpenseInvoiceNo ?? selectedInvoice?.invoice_no ?? '—'"
                disabled
              />
            </label>
            <div
              v-if="selectedInvoice"
              class="rounded-md border border-hairline bg-sunk p-3 text-sm md:col-span-2"
            >
              <div class="grid gap-2 md:grid-cols-[1fr_auto] md:items-center">
                <div class="grid gap-1">
                  <b class="text-base text-danger">
                    Qoldiq: {{ formatTiyin(selectedInvoice.outstanding_tiyin) }}
                  </b>
                  <span class="text-ink-muted">
                    Jami {{ formatTiyin(selectedInvoice.total_tiyin) }} · to'langan
                    {{ formatTiyin(selectedInvoice.paid_tiyin) }}
                  </span>
                </div>
                <button
                  type="button"
                  class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                  @click="expenseForm.amount = moneyInputValue(selectedInvoice.outstanding_tiyin)"
                >
                  Qoldiq
                </button>
              </div>
            </div>
            <p
              v-if="invoiceDerivedStrip"
              class="rounded-md border border-hairline px-3 py-2 text-sm text-ink-soft md:col-span-2"
            >
              Ta'minotchi va filial kirimdan olinadi — {{ invoiceDerivedStrip }}
            </p>
          </template>

          <FormSelect
            v-model="expenseForm.category"
            label="Kategoriya"
            :options="createCategoryOptions"
          />
          <label
            v-if="permissions.isOwner.value && !isInvoicePayment"
            class="flex min-h-10 cursor-pointer items-center gap-2 self-end pb-1 text-sm font-bold text-ink-soft"
          >
            <input
              v-model="expenseForm.workshopLevel"
              type="checkbox"
              class="size-4 accent-accent"
            />
            <span>Ustaxona darajasida (filialsiz)</span>
          </label>
          <label class="field md:col-span-2">
            <span>Tavsif</span>
            <input
              v-model="expenseForm.description"
              class="mp-input"
              placeholder="Masalan: Bahodir T. · 19 panel"
              required
            />
          </label>
          <SearchCombobox
            v-if="!isInvoicePayment"
            v-model="expenseForm.supplierId"
            label="Ta'minotchi (qarz uchun)"
            :options="supplierOptions"
            placeholder="ixtiyoriy — qarzga bog'lash"
            clearable
          />
          <label v-if="!isInvoicePayment" class="field">
            <span>Ta'minotchi</span>
            <input
              v-model="expenseForm.vendor"
              class="mp-input"
              placeholder="Masalan: Oq Mramor MChJ"
            />
          </label>
          <label class="field">
            <span>Summa (so'm)</span>
            <input v-model="expenseForm.amount" class="mp-input" inputmode="numeric" required />
            <small v-if="expenseAmountTiyin !== null" class="text-ink-muted">
              = {{ formatTiyin(expenseAmountTiyin) }}
            </small>
            <small v-else-if="expenseForm.amount.trim()" class="mp-field-error">
              {{ AMOUNT_HINT }}
            </small>
            <!-- Allowed, not blocked: an advance is a real thing that happens. -->
            <small v-if="overpaysInvoice" class="font-bold text-warning">
              Summa kirim qoldig'idan oshadi — avans sifatida yoziladi
            </small>
          </label>
          <label class="field">
            <span>Sana</span>
            <DateField v-model="expenseForm.incurredOn" :max="today" required />
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
          <p
            v-if="actionError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger md:col-span-2"
          >
            {{ actionError }}{{ traceSuffix(actionTraceId) }}
          </p>
          <div class="flex items-center gap-2 md:col-span-2">
            <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
              {{ saving ? 'Saqlanmoqda' : editingExpenseId ? 'Saqlash' : 'Yozish' }}
            </button>
            <button type="button" class="mp-button mp-button-outline" @click="closeExpenseModal">
              Bekor
            </button>
          </div>
        </form>
      </AppModal>

      <AppModal
        :open="incomeModalOpen"
        :title="editingIncomeId ? 'Tushumni tahrirlash' : 'Tushum yozish'"
        max-width="max-w-2xl"
        @close="closeIncomeModal"
      >
        <form class="grid gap-3 md:grid-cols-2" @submit.prevent="saveIncome">
          <SegmentedControl
            v-if="!editingIncomeId"
            v-model="incomeForm.type"
            label="Turi"
            :options="createIncomeTypeOptions"
          />
          <label v-else class="field">
            <span>Turi</span>
            <input
              class="mp-input"
              :value="(incomeForm.type && incomeTypeLabel[incomeForm.type]) || incomeForm.type"
              disabled
            />
          </label>
          <SegmentedControl v-model="incomeForm.method" label="Usul" :options="methodOptions" />
          <SearchCombobox
            v-if="incomeForm.type === 'order_payment' && !editingIncomeId"
            ref="incomeOrderCombobox"
            v-model="incomeForm.orderId"
            class="md:col-span-2"
            label="Buyurtma"
            :options="payableOrderOptions"
            :error="incomeOrderError"
            :loading="finance.payableOrdersLoading"
            :search-debounce-ms="250"
            server-filtered
            placeholder="Raqam, ism yoki telefon"
            no-results-text="Qoldig'i bor buyurtma topilmadi"
            hint="Faqat qoldig'i bor buyurtmalar · raqam, ism yoki telefon bo'yicha qidiring"
            clearable
            @search="onPayableOrderSearch"
          >
            <template #option="{ option }">
              <PayableOrderOption :order="payableOrderById[option.value]" />
            </template>
          </SearchCombobox>
          <label v-else-if="incomeForm.type === 'order_payment'" class="field md:col-span-2">
            <span>Buyurtma</span>
            <input
              class="mp-input"
              :value="financeIncomeOrderLabel(incomeForm.orderId, editingIncomeOrder)"
              disabled
            />
          </label>
          <!-- The picker row already showed the balance, so the old three-line
               panel would repeat it. One line under the selection is enough to
               confirm the figures the payment is being measured against.
               While editing, this income is lifted out of «Yozilgan» so that
               «Qoldiq» is the headroom this row actually has — the same number
               the Qoldiq button fills. -->
          <div
            v-if="incomeForm.type === 'order_payment' && incomeForm.orderId"
            class="md:col-span-2"
            aria-live="polite"
          >
            <p
              v-if="incomeSettlement"
              class="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-hairline bg-sunk px-3 py-2 text-[12px] text-ink-soft"
            >
              <span>
                Jami
                <b class="ml-1 font-mono text-ink">
                  {{ formatTiyin(incomeSettlement.total_tiyin) }}
                </b>
              </span>
              <span aria-hidden="true">·</span>
              <span>
                {{ editingIncomeId ? 'Boshqa yozuvlar' : 'Yozilgan' }}
                <b class="ml-1 font-mono text-ink">
                  {{ formatTiyin(incomeSettlement.recorded_tiyin) }}
                </b>
              </span>
              <span aria-hidden="true">·</span>
              <span>
                Qoldiq
                <b class="ml-1 font-mono text-danger">
                  {{ formatTiyin(incomeSettlement.balance_tiyin) }}
                </b>
              </span>
            </p>
            <p v-else class="text-[12px] font-bold text-ink-soft">Qoldiq ma'lumoti topilmadi.</p>
          </div>
          <label class="field">
            <span>Summa (to'liq yoki qisman)</span>
            <div class="relative">
              <!-- Explicit name: the wrapping <label> now also contains the
                   Qoldiq button, whose text would otherwise be folded into this
                   input's accessible name. -->
              <input
                v-model="incomeForm.amount"
                class="mp-input"
                :class="[
                  incomeAmountError ? 'border-danger' : '',
                  showRemainingBalanceButton ? 'pr-16' : '',
                ]"
                :aria-invalid="incomeAmountError ? 'true' : undefined"
                aria-label="Summa (to'liq yoki qisman)"
                inputmode="numeric"
                required
              />
              <!-- The fill-the-balance action belongs on the field it fills. -->
              <button
                v-if="showRemainingBalanceButton"
                type="button"
                class="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-sm px-2 py-1 text-[11px] font-bold text-accent transition hover:bg-accent-soft"
                @click="fillRemainingBalance"
              >
                Qoldiq
              </button>
            </div>
            <small v-if="incomeAmountError" class="mp-field-error">{{ incomeAmountError }}</small>
            <small v-else-if="incomeAmountTiyin !== null" class="text-ink-muted">
              = {{ formatTiyin(incomeAmountTiyin) }}
            </small>
          </label>
          <label class="field">
            <span>Qabul sanasi</span>
            <DateField v-model="incomeForm.receivedOn" :max="today" required />
          </label>
          <label class="field md:col-span-2">
            <span>Izoh</span>
            <input
              v-model="incomeForm.note"
              class="mp-input"
              placeholder="Masalan: Kapital bank, kassa 2"
            />
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
          <p
            v-if="actionError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger md:col-span-2"
          >
            {{ actionError }}{{ traceSuffix(actionTraceId) }}
          </p>
          <div class="flex items-center gap-2 md:col-span-2">
            <button
              type="submit"
              class="mp-button mp-button-primary"
              :disabled="saving || incomeAmountOverBalance"
            >
              {{ saving ? 'Saqlanmoqda' : editingIncomeId ? 'Saqlash' : 'Yozish' }}
            </button>
            <button type="button" class="mp-button mp-button-outline" @click="closeIncomeModal">
              Bekor
            </button>
          </div>
        </form>
      </AppModal>

      <div class="mp-filters">
        <DateRangePicker
          v-model:preset="datePreset"
          v-model:date-from="dateFrom"
          v-model:date-to="dateTo"
        />
        <ProjectDropdown
          v-if="activeTab === 'expense'"
          v-model="expenseCategory"
          label="Kategoriya"
          :options="categoryOptions"
          top-label
        />
        <ProjectDropdown
          v-else
          v-model="incomeType"
          label="Tur"
          :options="incomeTypeOptions"
          top-label
        />
        <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" top-label />
        <button
          v-if="activeTab === 'expense'"
          type="button"
          class="mp-button mp-button-primary"
          @click="openCreateExpense"
        >
          + Xarajat
        </button>
        <button v-else type="button" class="mp-button mp-button-primary" @click="openCreateIncome">
          + Tushum
        </button>
      </div>

      <FilterStatus
        :active="narrowingFilters.length > 0"
        :loading="finance.loading"
        :count="activeTab === 'expense' ? finance.expenses.length : finance.incomes.length"
        :noun="activeTab === 'expense' ? 'xarajat' : 'tushum'"
        :total="formatTiyin(periodTotalTiyin)"
        :on-reset="narrowingFilters.length > 1 ? resetLedgerFilters : null"
      />

      <section v-if="finance.loading" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="finance.error" class="st-error">
        <h3>Yozuvlarni yuklab bo'lmadi</h3>
        <p>{{ traceLine(finance.traceId) }}</p>
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
                <th>Ta'minotchi</th>
                <th class="right">Summa</th>
                <th v-if="showStatusColumn">Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="expense in finance.expenses"
                :key="expense.id"
                :class="{
                  muted: expense.status === 'voided',
                  // Only an editable row is clickable — a voided one, or a
                  // viewer without the permission, keeps the default cursor.
                  'row-clickable': canEditLedgerRow(expense.status),
                }"
              >
                <td class="num text-ink-muted">
                  {{ formatDate(expense.incurred_on) }}
                  <small class="block whitespace-nowrap font-sans text-[11px]">
                    Kiritildi: {{ formatDateTime(expense.created_at) }}
                  </small>
                </td>
                <td>
                  {{ categoryLabel[expense.category] ?? expense.category }}
                  <small v-if="!expense.branch_id" class="block text-[11px] text-ink-muted">
                    Barcha filiallar
                  </small>
                </td>
                <td class="nm">
                  <!-- The description runs the row's primary action — edit
                       (QAD-184); bekor qilish moved into the ⋯ menu. -->
                  <button
                    v-if="canEditLedgerRow(expense.status)"
                    type="button"
                    class="row-open row-open-text"
                    :aria-label="`${expense.description} — tahrirlash`"
                    @click="editExpense(expense)"
                  >
                    {{ expense.description }}
                  </button>
                  <template v-else>{{ expense.description }}</template>
                  <small v-if="expense.voided_reason">bekor: {{ expense.voided_reason }}</small>
                  <small v-if="expense.receipt_file_id" class="block text-[11px] text-ink-muted">
                    Chek biriktirilgan
                  </small>
                </td>
                <td>
                  <small class="text-ink-soft">{{ expense.vendor ?? '—' }}</small>
                  <!-- Which faktura the money paid — the link the whole ticket
                       exists to make visible. -->
                  <small
                    v-if="expense.invoice_no"
                    class="block font-mono text-[11px] text-ink-muted"
                  >
                    {{ expense.invoice_no }}
                  </small>
                </td>
                <td class="amt">{{ formatTiyin(expense.amount_tiyin) }}</td>
                <td v-if="showStatusColumn">
                  <span :class="expense.status === 'recorded' ? 'pill p-ok' : 'pill p-dn'">
                    <span class="pd"></span
                    >{{ expense.status === 'recorded' ? 'Yozilgan' : 'Bekor qilingan' }}
                  </span>
                </td>
                <td class="right">
                  <ActionMenu
                    v-if="canEditLedgerRow(expense.status)"
                    :items="voidMenuItems"
                    :label="`${expense.description} amallari`"
                    @select="openVoidForm('expense', expense.id)"
                  />
                </td>
              </tr>
              <tr v-if="finance.expenses.length === 0">
                <td :colspan="showStatusColumn ? 6 : 5">
                  <div class="st-empty !border-0 !py-8">
                    <h3 v-if="narrowingFilters.length">Filtrga mos xarajat topilmadi</h3>
                    <h3 v-else>Bu davrda xarajat yo'q</h3>
                    <p v-if="narrowingFilters.length">Filtrni o'zgartiring yoki tozalang.</p>
                  </div>
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
                <th>Izoh</th>
                <th class="right">Summa</th>
                <th v-if="showStatusColumn">Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="income in finance.incomes"
                :key="income.id"
                :class="{
                  muted: income.status === 'voided',
                  'row-clickable': canEditLedgerRow(income.status),
                }"
              >
                <td class="num text-ink-muted">
                  {{ formatDate(income.received_on) }}
                  <small class="block whitespace-nowrap font-sans text-[11px]">
                    Kiritildi: {{ formatDateTime(income.created_at) }}
                  </small>
                </td>
                <td>
                  <!-- The type runs the row's primary action — edit (QAD-184);
                       bekor qilish moved into the ⋯ menu. -->
                  <button
                    v-if="canEditLedgerRow(income.status)"
                    type="button"
                    class="row-open row-open-text"
                    :aria-label="`${incomeRowLabel(income)} — tahrirlash`"
                    @click="editIncome(income)"
                  >
                    {{ incomeTypeLabel[income.type] ?? income.type }}
                  </button>
                  <template v-else>{{ incomeTypeLabel[income.type] ?? income.type }}</template>
                  <small v-if="!income.branch_id" class="block text-[11px] text-ink-muted">
                    Barcha filiallar
                  </small>
                </td>
                <td>{{ financeIncomeOrderLabel(income.order_id, income.order) }}</td>
                <td>
                  <small class="text-ink-soft">{{
                    methodLabel[income.method] ?? income.method
                  }}</small>
                </td>
                <td>
                  <small class="text-ink-soft">{{
                    income.note ?? income.voided_reason ?? '—'
                  }}</small>
                  <!-- A whole column for a boolean that is empty on most rows
                       pushed Summa off a phone screen (QAD-182); the receipt
                       says so beside the note it belongs to. -->
                  <small v-if="income.receipt_file_id" class="block text-[11px] text-ink-muted">
                    Chek biriktirilgan
                  </small>
                </td>
                <td class="amt success-text">{{ formatTiyin(income.amount_tiyin) }}</td>
                <td v-if="showStatusColumn">
                  <span :class="income.status === 'recorded' ? 'pill p-ok' : 'pill p-dn'">
                    <span class="pd"></span
                    >{{ income.status === 'recorded' ? 'Yozilgan' : 'Bekor qilingan' }}
                  </span>
                </td>
                <td class="right">
                  <ActionMenu
                    v-if="canEditLedgerRow(income.status)"
                    :items="voidMenuItems"
                    :label="`${incomeRowLabel(income)} amallari`"
                    @select="openVoidForm('income', income.id)"
                  />
                </td>
              </tr>
              <tr v-if="finance.incomes.length === 0">
                <td :colspan="showStatusColumn ? 7 : 6">
                  <div class="st-empty !border-0 !py-8">
                    <h3 v-if="narrowingFilters.length">Filtrga mos tushum topilmadi</h3>
                    <h3 v-else>Bu davrda tushum yo'q</h3>
                    <p v-if="narrowingFilters.length">Filtrni o'zgartiring yoki tozalang.</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <ConfirmDialog
        :open="voidTarget !== null"
        title="Yozuvni bekor qilish"
        message="Bekor qilingan yozuv hisobotlarda va buyurtma to'lovlarida hisobga olinmaydi. Sababni yozing."
        confirm-label="Bekor qilish"
        cancel-label="Yopish"
        busy-label="Bekor qilinmoqda"
        danger
        :busy="saving"
        :confirm-disabled="voidReason.trim().length === 0"
        @cancel="closeVoidForm"
        @confirm="confirmVoid"
      >
        <!-- Names the record the void will hit (date · category/type · sum). -->
        <p v-if="voidTargetLabel" class="mb-3 text-sm font-bold text-ink">{{ voidTargetLabel }}</p>
        <label class="field !mb-0">
          <span>Bekor qilish sababi</span>
          <input v-model="voidReason" class="mp-input" required />
        </label>
        <p v-if="actionError" class="mt-2 text-sm font-bold text-danger">
          {{ actionError }}{{ traceSuffix(actionTraceId) }}
        </p>
      </ConfirmDialog>
    </template>
  </section>
</template>
