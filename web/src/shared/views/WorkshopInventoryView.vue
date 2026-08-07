<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { apiErrorCode, apiTraceId } from '@/shared/api/client'
import { INVENTORY_TX_PAGE_LIMIT } from '@/shared/app/constants'
import { presetRange, type DateRangePreset } from '@/shared/app/dateRange'
import { traceLine } from '@/shared/app/errorTrace'
import {
  sanitizeMoneyInput,
  sanitizeQuantityInput,
  sanitizeSignedQuantityInput,
} from '@/shared/app/inputSanitizers'
import { formatMm, isTape } from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { useRolePath } from '@/shared/app/paths'
import type { DropdownOption } from '@/shared/app/roleConfig'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { stockTransactionTypeLabel } from '@/shared/app/workshopUi'
import ActionMenu, { type ActionMenuItem } from '@/shared/components/ActionMenu.vue'
import AppIcon from '@/shared/components/AppIcon.vue'
import AppModal from '@/shared/components/AppModal.vue'
import AppTabs from '@/shared/components/AppTabs.vue'
import DateField from '@/shared/components/DateField.vue'
import FilterStatus from '@/shared/components/FilterStatus.vue'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { useFinanceStore } from '@/shared/stores/finance'
import {
  formatDate,
  formatDateInputValue,
  formatDateTime,
  formatStockQuantity,
  formatStockUnit,
  formatTiyin,
  parseDisplayQuantity,
  parseSomToTiyin,
} from '@/shared/formatters'
import {
  useWorkshopStore,
  type InvoicePaymentStatus,
  type StockItem,
  type StockLastPrice,
  type Supplier,
} from '@/shared/stores/workshop'

const { t } = useI18n()
const rolePath = useRolePath()
const permissions = useWorkshopPermissions()
const workshop = useWorkshopStore()
const finance = useFinanceStore()
const toast = useToast()
const route = useRoute()
const router = useRouter()
const today = formatDateInputValue(new Date())
const activeTab = ref<'stock' | 'invoices' | 'tx' | 'suppliers'>('stock')
const inventoryTabs = computed<ChoiceOption[]>(() => [
  { value: 'stock', label: t('inventory.tab.stock') },
  { value: 'invoices', label: t('inventory.tab.invoices') },
  { value: 'tx', label: t('inventory.tab.tx') },
  { value: 'suppliers', label: t('inventory.tab.suppliers') },
])
const search = ref('')
const lowOnly = ref(false)

// A branch with 30 materials told the operator it had none, because the empty
// state did not know a search was active (QAD-182). First-run and
// filtered-empty are different facts and get different copy.
const stockFiltered = computed(() => search.value.trim().length > 0 || lowOnly.value)
const txPreset = ref<DateRangePreset>('days30')
const initialTxRange = presetRange('days30')
const txDateFrom = ref(initialTxRange.from ?? '')
const txDateTo = ref(initialTxRange.to ?? '')
// Material filter doubles as the price-history view: one material's stock-in
// rows read as its purchase-price timeline.
const txMaterialId = ref('all')
const invoiceOpen = ref(false)
const adjustmentOpen = ref(false)
const movementSaving = ref(false)
const supplierSaving = ref(false)
const movementError = ref<string | null>(null)
const supplierError = ref<string | null>(null)
const invoiceSupplierError = ref<string | null>(null)
const invoiceLinesError = ref<string | null>(null)
const invoiceDiscountError = ref<string | null>(null)
const adjustmentMaterialError = ref<string | null>(null)
const editingSupplierId = ref<string | null>(null)
const supplierModalOpen = ref(false)
const stockLoadedKey = ref<string | null>(null)
const transactionsLoadedKey = ref<string | null>(null)
const invoicesLoadedKey = ref<string | null>(null)
const suppliersLoadedBranch = ref<string | null>(null)
const invoiceSearch = ref('')
const invoicePaymentFilter = ref<InvoicePaymentStatus | 'all'>('all')
const expandedInvoiceIds = ref<string[]>([])
let stockSearchTimer: number | undefined
let invoiceSearchTimer: number | undefined

// A faktura is entered as a header plus lines; the lines are local drafts until
// the whole document is saved in one request.
interface InvoiceLineDraft {
  key: number
  materialId: string | null
  quantity: string
  unitPrice: string
  // A typed price is never overwritten by a later last-price prefill.
  priceEdited: boolean
  lastPrice: StockLastPrice | null
  lastPriceLoaded: boolean
}

let lineKeySeed = 0
function blankLine(): InvoiceLineDraft {
  return {
    key: ++lineKeySeed,
    materialId: null,
    quantity: '',
    unitPrice: '',
    priceEdited: false,
    lastPrice: null,
    lastPriceLoaded: false,
  }
}

const invoiceForm = reactive({
  supplierId: null as string | null,
  inlineSupplierName: '',
  invoiceDate: today,
  discount: '',
  surcharge: '',
  note: '',
})
const invoiceLines = ref<InvoiceLineDraft[]>([blankLine()])
const adjustmentForm = reactive({
  materialId: null as string | null,
  // A signed quantity with a REQUIRED leading + or − ("-2" decreases, "+5"
  // increases) — the explicit prefix is the sign-safety mechanism.
  quantity: '',
  note: '',
})
const supplierForm = reactive({
  name: '',
  phone: '',
  note: '',
})

const canUseInventory = computed(() => permissions.can(p.manageInventory))
// Debt balances are manage_finance/owner territory (Qarzdorlik rules) — the
// column only renders for users who could open the Qarzdorlik page anyway.
const canSeeDebts = computed(() => permissions.isOwner.value || permissions.can(p.manageFinance))
const supplierBalanceById = computed(
  () =>
    new Map(
      (finance.supplierDebts?.rows ?? []).map((row) => [row.counterparty_id, row.balance_tiyin]),
    ),
)

function supplierBalanceChip(supplierId: string) {
  const balance = supplierBalanceById.value.get(supplierId) ?? 0
  if (balance > 0) {
    return {
      cls: 'pill p-ok',
      text: t('inventory.supplier.owesUs', { amount: formatTiyin(balance) }),
    }
  }
  if (balance < 0) {
    return {
      cls: 'pill p-bad',
      text: t('inventory.supplier.weOwe', { amount: formatTiyin(-balance) }),
    }
  }
  return { cls: '', text: '—' }
}
const accessibleBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, [p.manageInventory]),
)
// Branch is driven by the topbar context picker (AppShell); the page follows it
// and falls back to the first accessible branch until context is set.
const selectedBranchId = computed(() => {
  const context = workshop.selectedBranchContext
  if (context && accessibleBranches.value.some((branch) => branch.id === context)) return context
  return accessibleBranches.value[0]?.id ?? ''
})
const displayUnitByMaterialId = computed(
  () => new Map(workshop.stockItems.map((item) => [item.branch_material_id, item.display_unit])),
)
const stockOptions = computed(() =>
  workshop.stockItems.map((item) => ({
    value: item.branch_material_id,
    label: item.material.label,
    meta:
      item.on_hand < 0
        ? t('inventory.stock.optionShort', {
            quantity: formatStockQuantity(-item.on_hand, item.display_unit),
          })
        : t('inventory.stock.optionOnHand', {
            quantity: formatStockQuantity(item.on_hand, item.display_unit),
          }),
  })),
)
const txMaterialOptions = computed<DropdownOption[]>(() => [
  { value: 'all', label: t('inventory.tx.materialFilterAll') },
  ...workshop.stockItems.map((item) => ({
    value: item.branch_material_id,
    label: item.material.label,
  })),
])
const activeSupplierOptions = computed(() => [
  {
    value: 'inline',
    label: t('inventory.supplier.inlineOption'),
    meta: t('inventory.supplier.inlineOptionMeta'),
  },
  ...workshop.suppliers
    .filter((supplier) => supplier.status === 'active')
    .map((supplier) => ({
      value: supplier.id,
      label: supplier.name,
      meta: supplier.phone ?? t('inventory.supplier.activeMeta'),
    })),
])
const selectedAdjustmentItem = computed(() => stockItemByMaterial(adjustmentForm.materialId))
// The signed field is incomplete (not wrong) until the required prefix arrives —
// surface a muted nudge while typing; the danger copy is reserved for submit.
const adjustmentNeedsSign = computed(
  () => adjustmentForm.quantity.length > 0 && !/^[+-]/.test(adjustmentForm.quantity),
)

// Type-time sanitization (PhoneInput precedent) — invalid characters never stick.
watch(
  () => adjustmentForm.quantity,
  (value) => {
    const clean = sanitizeSignedQuantityInput(value)
    if (clean !== value) adjustmentForm.quantity = clean
  },
)
watch(
  invoiceLines,
  (lines) => {
    for (const line of lines) {
      const quantity = sanitizeQuantityInput(line.quantity)
      if (quantity !== line.quantity) line.quantity = quantity
      const price = sanitizeMoneyInput(line.unitPrice)
      if (price !== line.unitPrice) line.unitPrice = price
    }
  },
  { deep: true },
)
watch(
  () => invoiceForm.discount,
  (value) => {
    const clean = sanitizeMoneyInput(value)
    if (clean !== value) invoiceForm.discount = clean
  },
)
watch(
  () => invoiceForm.surcharge,
  (value) => {
    const clean = sanitizeMoneyInput(value)
    if (clean !== value) invoiceForm.surcharge = clean
  },
)

// The unit a line's price is entered per — one panel for panels, one metre for
// edges. Rendered as a persistent suffix inside the field, never as a
// placeholder: the difference between 18 so'm/m and 1 800 so'm/m is the whole
// cost base, and a hint that disappears when you type is not a label (QAD-182).
function linePriceUnit(line: InvoiceLineDraft) {
  const item = stockItemByMaterial(line.materialId)
  if (!item) return t('inventory.invoice.priceUnitSom')
  return isMetreUnit(item.display_unit)
    ? t('inventory.invoice.priceUnitMetre')
    : t('inventory.invoice.priceUnitSheet')
}

function lineQuantityUnit(line: InvoiceLineDraft) {
  const item = stockItemByMaterial(line.materialId)
  return item ? formatStockUnit(item.display_unit) : ''
}

function lineLastPriceHint(line: InvoiceLineDraft) {
  if (!line.materialId || !line.lastPriceLoaded) return null
  const price = line.lastPrice
  if (!price || price.unit_price_tiyin === null) return t('inventory.invoice.firstArrival')
  const parts = [t('inventory.invoice.lastPrice', { price: formatTiyin(price.unit_price_tiyin) })]
  if (price.recorded_at) parts.push(formatDate(price.recorded_at))
  if (price.supplier_name) parts.push(`«${price.supplier_name}»`)
  return parts.join(' · ')
}

function isMetreUnit(displayUnit: string) {
  return displayUnit === 'metre' || displayUnit === 'm'
}

// Live line total mirroring the server math exactly: panels multiply, edges take
// millimetres x per-metre price with floor division (the sale-side mirror).
function lineTotalTiyin(line: InvoiceLineDraft) {
  const item = stockItemByMaterial(line.materialId)
  const quantity = validLineQuantity(line, item)
  const price = parseSomToTiyin(line.unitPrice)
  if (!item || quantity === null || price === null) return null
  return isMetreUnit(item.display_unit) ? Math.floor((quantity * price) / 1000) : quantity * price
}

const invoiceSubtotalTiyin = computed(() =>
  invoiceLines.value.reduce((sum, line) => sum + (lineTotalTiyin(line) ?? 0), 0),
)
const invoiceDiscountTiyin = computed(() => parseSomToTiyin(invoiceForm.discount) ?? 0)
const invoiceSurchargeTiyin = computed(() => parseSomToTiyin(invoiceForm.surcharge) ?? 0)
const invoiceTotalTiyin = computed(
  () => invoiceSubtotalTiyin.value - invoiceDiscountTiyin.value + invoiceSurchargeTiyin.value,
)
const invoiceDiscountTooBig = computed(
  () => invoiceDiscountTiyin.value > invoiceSubtotalTiyin.value,
)

// A real (non-inline) selected supplier id, for supplier-specific prefill.
const invoiceRealSupplierId = computed(() =>
  invoiceForm.supplierId && invoiceForm.supplierId !== 'inline' ? invoiceForm.supplierId : null,
)

const lastPriceFetchTokens = new Map<number, number>()
async function refreshLineLastPrice(line: InvoiceLineDraft) {
  if (!selectedBranchId.value || !line.materialId) {
    line.lastPrice = null
    line.lastPriceLoaded = false
    return
  }
  const token = (lastPriceFetchTokens.get(line.key) ?? 0) + 1
  lastPriceFetchTokens.set(line.key, token)
  try {
    const fetched = await workshop.fetchMaterialLastPrice(
      selectedBranchId.value,
      line.materialId,
      invoiceRealSupplierId.value,
    )
    if (lastPriceFetchTokens.get(line.key) !== token) return
    line.lastPrice = fetched
    line.lastPriceLoaded = true
    // Prefill only into a field the user has not touched — a typed value always
    // wins. The emptiness check is what makes that race-proof: the fetch is in
    // flight while the price field is already reachable, and `priceEdited` only
    // flips on the first input event, so a fast typist could otherwise have the
    // prefill land on top of half-entered digits.
    if (!line.priceEdited && !line.unitPrice) {
      line.unitPrice =
        fetched.unit_price_tiyin !== null && fetched.unit_price_tiyin > 0
          ? String(Math.round(fetched.unit_price_tiyin / 100))
          : ''
    }
  } catch {
    if (lastPriceFetchTokens.get(line.key) !== token) return
    // Prefill is best-effort UX; a failed fetch must never block manual entry.
    line.lastPrice = null
    line.lastPriceLoaded = false
  }
}

function onLineMaterialChange(line: InvoiceLineDraft) {
  // A price belongs to a material — switching materials restarts the prefill.
  line.priceEdited = false
  line.unitPrice = ''
  line.lastPriceLoaded = false
  void refreshLineLastPrice(line)
}

function addInvoiceLine() {
  invoiceLines.value = [...invoiceLines.value, blankLine()]
}

function removeInvoiceLine(key: number) {
  const remaining = invoiceLines.value.filter((line) => line.key !== key)
  invoiceLines.value = remaining.length > 0 ? remaining : [blankLine()]
}

watch(invoiceRealSupplierId, () => {
  for (const line of invoiceLines.value) {
    if (line.materialId) void refreshLineLastPrice(line)
  }
})

const paymentStatusFilterOptions = computed<DropdownOption[]>(() => [
  { value: 'all', label: t('inventory.invoices.paymentAll') },
  { value: 'unpaid', label: t('inventory.invoices.unpaid'), dot: 'danger' },
  { value: 'partial', label: t('inventory.invoices.partial'), dot: 'warning' },
  { value: 'paid', label: t('inventory.invoices.paid'), dot: 'success' },
])

function paymentStatusPill(status: InvoicePaymentStatus) {
  if (status === 'paid') return { cls: 'pill p-ok', text: t('inventory.invoices.paid') }
  if (status === 'partial') return { cls: 'pill p-warn', text: t('inventory.invoices.partial') }
  return { cls: 'pill p-bad', text: t('inventory.invoices.unpaid') }
}

function isInvoiceExpanded(id: string) {
  return expandedInvoiceIds.value.includes(id)
}

function toggleInvoice(id: string) {
  expandedInvoiceIds.value = isInvoiceExpanded(id)
    ? expandedInvoiceIds.value.filter((row) => row !== id)
    : [...expandedInvoiceIds.value, id]
}

const activeListEmpty = computed(() => {
  if (activeTab.value === 'stock') return workshop.stockItems.length === 0
  if (activeTab.value === 'invoices') return workshop.supplierInvoices.length === 0
  if (activeTab.value === 'tx') return workshop.stockTransactions.length === 0
  return workshop.suppliers.length === 0
})

function stockItemByMaterial(materialId: string | null): StockItem | null {
  return workshop.stockItems.find((item) => item.branch_material_id === materialId) ?? null
}

// A negative balance means production consumed material whose arrival was never
// recorded (QAD-150). It is not "low" — it is a bookkeeping gap that wants an
// arrival entered, so it gets the danger treatment and the backend sorts it to
// the top of the list.
function isNegative(item: StockItem) {
  return item.on_hand < 0
}

// The format line under the material's label: `2800×2070×18 mm` for a panel,
// `0.4×19 mm · kromka (metr)` for a tape. Reads the branch material's own format
// fields — there is no stored name, and `material.label` already carries identity.
function materialMeta(item: (typeof workshop.stockItems)[number]) {
  const thickness = formatMm(item.material.qalinlik_mm)
  if (isTape(item.tur)) {
    return t('inventory.stock.materialMetaTape', {
      thickness,
      width: item.material.kromka_eni_mm ?? 0,
    })
  }
  return t('inventory.stock.materialMetaPanel', {
    thickness,
    length: item.material.uzunlik_mm ?? 0,
    width: item.material.eni_mm ?? 0,
  })
}

function transactionDisplayUnit(materialId: string) {
  return displayUnitByMaterialId.value.get(materialId) ?? 'piece'
}

function formatTransactionQuantity(quantity: number, materialId: string) {
  const prefix = quantity > 0 ? '+' : ''
  return `${prefix}${formatStockQuantity(quantity, transactionDisplayUnit(materialId))}`
}

// Not copy: `System` and `User <id>` are operator diagnostics for a row with no
// human actor, and the transliterator would turn either into nonsense Cyrillic.
function transactionActorName(tx: (typeof workshop.stockTransactions)[number]) {
  if (tx.actor_name) return tx.actor_name
  if (tx.actor_user_id) return `User ${tx.actor_user_id.slice(0, 8)}`
  return 'System'
}

function transactionFilterKey() {
  return [
    selectedBranchId.value,
    txDateFrom.value || 'open',
    txDateTo.value || 'open',
    txMaterialId.value,
  ].join(':')
}

function stockFilterKey() {
  return [selectedBranchId.value, search.value.trim(), lowOnly.value ? 'low' : 'all'].join(':')
}

function invoiceFilterKey() {
  return [selectedBranchId.value, invoiceSearch.value.trim(), invoicePaymentFilter.value].join(':')
}

async function refreshActiveInventoryTab(options: { force?: boolean; offset?: number } = {}) {
  if (!selectedBranchId.value) return
  const branchId = selectedBranchId.value
  const offset = options.offset ?? 0
  const txKey = transactionFilterKey()
  const stockKey = stockFilterKey()
  const invoiceKey = invoiceFilterKey()
  if (!options.force && offset === 0) {
    if (activeTab.value === 'stock' && stockLoadedKey.value === stockKey) return
    if (activeTab.value === 'invoices' && invoicesLoadedKey.value === invoiceKey) return
    if (activeTab.value === 'tx' && transactionsLoadedKey.value === txKey) return
    if (activeTab.value === 'suppliers' && suppliersLoadedBranch.value === branchId) return
  }
  workshop.inventoryLoading = true
  workshop.inventoryError = null
  workshop.inventoryTraceId = null
  try {
    if (activeTab.value === 'stock') {
      await workshop.loadStock(branchId, {
        search: search.value.trim(),
        low_stock: lowOnly.value ? true : null,
      })
      stockLoadedKey.value = stockKey
      return
    }
    if (activeTab.value === 'invoices') {
      await workshop.loadSupplierInvoices(branchId, {
        search: invoiceSearch.value.trim() || null,
        payment_status: invoicePaymentFilter.value === 'all' ? null : invoicePaymentFilter.value,
      })
      invoicesLoadedKey.value = invoiceKey
      return
    }
    if (activeTab.value === 'tx') {
      await workshop.loadStockTransactions(branchId, {
        branch_material_id: txMaterialId.value === 'all' ? null : txMaterialId.value,
        date_from: txDateFrom.value || null,
        date_to: txDateTo.value || null,
        limit: INVENTORY_TX_PAGE_LIMIT,
        offset,
      })
      if (offset === 0) transactionsLoadedKey.value = txKey
      return
    }
    await workshop.loadSuppliers(branchId)
    suppliersLoadedBranch.value = branchId
    if (canSeeDebts.value) {
      await finance.loadSupplierDebts({ only_with_debt: false }).catch(() => undefined)
    }
  } catch (errorValue) {
    workshop.inventoryError = 'inventory_load_failed'
    workshop.inventoryTraceId = apiTraceId(errorValue)
  } finally {
    workshop.inventoryLoading = false
  }
}

async function loadMoreTransactions() {
  if (!selectedBranchId.value) return
  activeTab.value = 'tx'
  await refreshActiveInventoryTab({ force: true, offset: workshop.stockTransactions.length })
}

async function ensureSuppliersLoaded() {
  if (!selectedBranchId.value) return
  if (suppliersLoadedBranch.value === selectedBranchId.value) return
  try {
    await workshop.loadSuppliers(selectedBranchId.value)
    suppliersLoadedBranch.value = selectedBranchId.value
  } catch {
    supplierError.value = 'suppliers_load_failed'
  }
}

function validLineQuantity(line: InvoiceLineDraft, item: StockItem | null) {
  const quantity = parseDisplayQuantity(line.quantity, item?.display_unit ?? 'piece')
  return Number.isFinite(quantity) && quantity > 0 ? quantity : null
}

// Requires an explicit leading + or − and a positive magnitude; returns the
// SIGNED quantity in the stock unit, or null when either is missing.
function validAdjustmentQuantity(item: StockItem | null) {
  const raw = adjustmentForm.quantity
  const sign = raw.startsWith('+') ? 1 : raw.startsWith('-') ? -1 : 0
  if (sign === 0) return null
  const magnitude = parseDisplayQuantity(raw.slice(1), item?.display_unit ?? 'piece')
  return Number.isFinite(magnitude) && magnitude > 0 ? sign * magnitude : null
}

// `withExpense` is what makes the invoice→expense link actually get used:
// without it staff record the payment separately and never attach it.
async function saveInvoice(withExpense = false) {
  if (!selectedBranchId.value) return
  movementSaving.value = true
  movementError.value = null
  invoiceSupplierError.value = null
  invoiceLinesError.value = null
  invoiceDiscountError.value = null

  if (!invoiceForm.supplierId) {
    invoiceSupplierError.value = t('inventory.invoice.supplierRequired')
    movementSaving.value = false
    return
  }
  if (invoiceForm.supplierId === 'inline' && !invoiceForm.inlineSupplierName.trim()) {
    invoiceSupplierError.value = t('inventory.invoice.inlineSupplierRequired')
    movementSaving.value = false
    return
  }
  const lines: Array<{
    branch_material_id: string
    quantity: number
    unit_price_tiyin: number
  }> = []
  for (const line of invoiceLines.value) {
    const item = stockItemByMaterial(line.materialId)
    const quantity = validLineQuantity(line, item)
    const unitPriceTiyin = parseSomToTiyin(line.unitPrice)
    if (!item || quantity === null || unitPriceTiyin === null) {
      invoiceLinesError.value = t('inventory.invoice.linesInvalid')
      movementSaving.value = false
      return
    }
    lines.push({
      branch_material_id: item.branch_material_id,
      quantity,
      unit_price_tiyin: unitPriceTiyin,
    })
  }
  if (invoiceDiscountTooBig.value) {
    invoiceDiscountError.value = t('inventory.invoice.discountTooBig')
    movementSaving.value = false
    return
  }

  try {
    const invoice = await workshop.createSupplierInvoice(selectedBranchId.value, {
      supplier_id: invoiceForm.supplierId === 'inline' ? null : invoiceForm.supplierId,
      supplier:
        invoiceForm.supplierId === 'inline'
          ? { name: invoiceForm.inlineSupplierName.trim() }
          : null,
      invoice_date: invoiceForm.invoiceDate || null,
      discount_tiyin: invoiceDiscountTiyin.value,
      surcharge_tiyin: invoiceSurchargeTiyin.value,
      note: invoiceForm.note || null,
      lines,
    })
    resetInvoiceForm()
    invoiceOpen.value = false
    invoicesLoadedKey.value = null
    toast.success(t('inventory.invoice.saved', { number: invoice.invoice_no }))
    if (withExpense) {
      await router.push(
        rolePath(`/workshop/finance/expenses?create=expense&invoice_id=${invoice.id}`),
      )
      return
    }
    if (activeTab.value === 'invoices') await refreshActiveInventoryTab({ force: true })
  } catch (errorValue) {
    // A material can hold a (negative) stock row while sitting outside the branch
    // catalog — production records what physically moved regardless (QAD-150).
    // An invoice line still needs the catalog entry, so name the actual next
    // step instead of the generic "kirim yozilmadi".
    movementError.value =
      apiErrorCode(errorValue) === 'branch_material_not_found'
        ? 'branch_material_not_found'
        : 'invoice_save_failed'
  } finally {
    movementSaving.value = false
  }
}

async function recordAdjustment() {
  if (!selectedBranchId.value) return
  movementSaving.value = true
  movementError.value = null
  adjustmentMaterialError.value = null
  const item = selectedAdjustmentItem.value
  const quantity = validAdjustmentQuantity(item)
  if (!item || quantity === null) {
    adjustmentMaterialError.value = t('inventory.adjustment.materialRequired')
    movementSaving.value = false
    return
  }
  try {
    await workshop.recordAdjustment(selectedBranchId.value, {
      branch_material_id: item.branch_material_id,
      quantity,
      note: adjustmentForm.note,
    })
    resetAdjustmentForm()
    adjustmentOpen.value = false
    toast.success(t('inventory.adjustment.saved'))
  } catch {
    movementError.value = 'adjustment_failed'
  } finally {
    movementSaving.value = false
  }
}

async function saveSupplier() {
  if (!selectedBranchId.value) return
  supplierSaving.value = true
  supplierError.value = null
  try {
    const payload = {
      name: supplierForm.name,
      phone: supplierForm.phone || null,
      note: supplierForm.note || null,
    }
    const wasEditing = Boolean(editingSupplierId.value)
    if (editingSupplierId.value) {
      await workshop.updateSupplier(selectedBranchId.value, editingSupplierId.value, payload)
    } else {
      await workshop.createSupplier(selectedBranchId.value, payload)
    }
    resetSupplierForm()
    supplierModalOpen.value = false
    toast.success(wasEditing ? t('inventory.supplier.saved') : t('inventory.supplier.added'))
  } catch {
    supplierError.value = 'supplier_save_failed'
  } finally {
    supplierSaving.value = false
  }
}

// The row itself edits (QAD-184), so the menu holds the one remaining action —
// still worded, never a bare glyph, because it changes who can be paid.
function supplierMenuItems(supplier: Supplier): ActionMenuItem[] {
  return [
    {
      label:
        supplier.status === 'active'
          ? t('inventory.supplier.block')
          : t('inventory.supplier.activate'),
      icon: supplier.status === 'active' ? 'ban' : 'check',
      disabled: supplierSaving.value,
    },
  ]
}

async function toggleSupplierStatus(supplier: Supplier) {
  if (!selectedBranchId.value) return
  supplierSaving.value = true
  supplierError.value = null
  try {
    await workshop.setSupplierStatus(
      selectedBranchId.value,
      supplier.id,
      supplier.status === 'active' ? 'inactive' : 'active',
    )
    toast.success(t('inventory.supplier.statusChanged'))
  } catch {
    supplierError.value = 'supplier_status_failed'
  } finally {
    supplierSaving.value = false
  }
}

function openCreateSupplier() {
  resetSupplierForm()
  supplierError.value = null
  supplierModalOpen.value = true
}

function editSupplier(supplier: Supplier) {
  editingSupplierId.value = supplier.id
  supplierForm.name = supplier.name
  supplierForm.phone = supplier.phone ?? ''
  supplierForm.note = supplier.note ?? ''
  supplierError.value = null
  supplierModalOpen.value = true
}

function closeSupplierModal() {
  supplierModalOpen.value = false
  resetSupplierForm()
}

function openInvoiceModal() {
  resetInvoiceForm()
  movementError.value = null
  invoiceOpen.value = true
  void ensureSuppliersLoaded()
}

function resetInvoiceForm() {
  invoiceForm.supplierId = null
  invoiceForm.inlineSupplierName = ''
  invoiceForm.invoiceDate = today
  invoiceForm.discount = ''
  invoiceForm.surcharge = ''
  invoiceForm.note = ''
  invoiceLines.value = [blankLine()]
  invoiceSupplierError.value = null
  invoiceLinesError.value = null
  invoiceDiscountError.value = null
}

function resetAdjustmentForm() {
  adjustmentForm.materialId = null
  adjustmentForm.quantity = ''
  adjustmentForm.note = ''
  adjustmentMaterialError.value = null
}

function resetSupplierForm() {
  editingSupplierId.value = null
  supplierForm.name = ''
  supplierForm.phone = ''
  supplierForm.note = ''
}

function routeSearchValue() {
  const value = route.query.search
  return typeof value === 'string' ? value : ''
}

function applyRouteSearch() {
  const value = routeSearchValue()
  if (value !== search.value) search.value = value
}

// The topbar owns the branch context; the page reloads whenever the resolved
// branch changes (context switch or the branch list arriving on mount).
watch(selectedBranchId, () => {
  stockLoadedKey.value = null
  transactionsLoadedKey.value = null
  invoicesLoadedKey.value = null
  suppliersLoadedBranch.value = null
  expandedInvoiceIds.value = []
  workshop.clearInventory()
  void refreshActiveInventoryTab({ force: true })
})

watch(activeTab, () => {
  void refreshActiveInventoryTab()
})

// Clear the adjustment form when the modal closes so a fresh open always starts
// empty rather than with the last entry's signed quantity.
watch(adjustmentOpen, (open) => {
  if (!open) resetAdjustmentForm()
})

watch(
  () => route.query.search,
  () => {
    applyRouteSearch()
  },
)

watch([txDateFrom, txDateTo, txMaterialId], () => {
  if (activeTab.value === 'tx') void refreshActiveInventoryTab({ force: true })
})

watch([search, lowOnly], () => {
  window.clearTimeout(stockSearchTimer)
  stockSearchTimer = window.setTimeout(() => {
    if (activeTab.value === 'stock') void refreshActiveInventoryTab({ force: true })
  }, 250)
})

watch([invoiceSearch, invoicePaymentFilter], () => {
  window.clearTimeout(invoiceSearchTimer)
  invoiceSearchTimer = window.setTimeout(() => {
    if (activeTab.value === 'invoices') void refreshActiveInventoryTab({ force: true })
  }, 250)
})

// Materials feed the invoice line pickers, suppliers feed its header — both
// live on the stock/supplier endpoints, so the Kirimlar tab loads them too.
watch(activeTab, (tab) => {
  if (tab !== 'invoices' || !selectedBranchId.value) return
  if (workshop.stockItems.length === 0) void workshop.loadStock(selectedBranchId.value)
  void ensureSuppliersLoaded()
})

onMounted(async () => {
  applyRouteSearch()
  await workshop.loadBranchContext().catch(() => undefined)
  await refreshActiveInventoryTab({ force: true })
})

onBeforeUnmount(() => {
  window.clearTimeout(stockSearchTimer)
  window.clearTimeout(invoiceSearchTimer)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>{{ $t('inventory.page.title') }}</h1>
      </div>
    </div>

    <div v-if="!canUseInventory" class="st-empty">
      <h3>{{ $t('inventory.page.noPermissionTitle') }}</h3>
      <p>{{ $t('inventory.page.noPermissionBody') }}</p>
    </div>

    <div v-else-if="accessibleBranches.length === 0" class="st-empty">
      <h3>{{ $t('inventory.page.noBranchTitle') }}</h3>
      <p>{{ $t('inventory.page.noBranchBody') }}</p>
    </div>

    <template v-else>
      <AppTabs
        v-model="activeTab"
        id-prefix="workshop-inventory"
        :label="$t('inventory.page.tabsLabel')"
        :tabs="inventoryTabs"
      />

      <div v-if="activeTab !== 'suppliers'" class="mp-filters">
        <label v-if="activeTab === 'stock'" class="mp-filter-input">
          <span>{{ $t('inventory.stock.searchLabel') }}</span>
          <input v-model="search" :placeholder="$t('inventory.stock.searchPlaceholder')" />
        </label>
        <button
          v-if="activeTab === 'stock'"
          type="button"
          class="mp-filter-chip"
          :aria-pressed="lowOnly"
          @click="lowOnly = !lowOnly"
        >
          <span class="mp-filter-chip-dot" aria-hidden="true"></span>
          {{ $t('inventory.stock.lowOnly') }}
        </button>
        <label v-if="activeTab === 'invoices'" class="mp-filter-input">
          <span>{{ $t('inventory.invoices.searchLabel') }}</span>
          <input
            v-model="invoiceSearch"
            :placeholder="$t('inventory.invoices.searchPlaceholder')"
          />
        </label>
        <ProjectDropdown
          v-if="activeTab === 'invoices'"
          v-model="invoicePaymentFilter"
          :label="$t('inventory.invoices.paymentFilterLabel')"
          :options="paymentStatusFilterOptions"
          top-label
        />
        <button
          v-if="activeTab === 'invoices'"
          type="button"
          class="mp-button mp-button-primary"
          @click="openInvoiceModal"
        >
          {{ $t('inventory.invoice.createAction') }}
        </button>
        <DateRangePicker
          v-if="activeTab === 'tx'"
          v-model:preset="txPreset"
          v-model:date-from="txDateFrom"
          v-model:date-to="txDateTo"
        />
        <ProjectDropdown
          v-if="activeTab === 'tx'"
          v-model="txMaterialId"
          :label="$t('inventory.tx.materialFilterLabel')"
          :options="txMaterialOptions"
          top-label
        />
      </div>

      <FilterStatus
        v-if="activeTab === 'stock'"
        :active="stockFiltered"
        :loading="workshop.loading"
        :count="workshop.stockItems.length"
        noun="material"
        :on-reset="
          search.trim() && lowOnly
            ? () => {
                search = ''
                lowOnly = false
              }
            : null
        "
      />

      <div v-if="activeTab === 'stock'" class="mb-4 grid grid-cols-2 gap-2">
        <button type="button" class="mp-button mp-button-primary" @click="openInvoiceModal">
          {{ $t('inventory.invoice.title') }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="adjustmentOpen = true">
          {{ $t('inventory.stock.adjustAction') }}
        </button>
      </div>

      <AppModal
        :open="invoiceOpen"
        :title="$t('inventory.invoice.title')"
        max-width="max-w-3xl"
        @close="invoiceOpen = false"
      >
        <form class="grid gap-4" @submit.prevent="saveInvoice(false)">
          <!-- Header: who delivered, when, and the number the document will get. -->
          <div class="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
            <FormSelect
              v-model="invoiceForm.supplierId"
              :label="$t('inventory.invoice.supplier')"
              :options="activeSupplierOptions"
              :error="invoiceSupplierError"
              @focusin="ensureSuppliersLoaded"
            />
            <label class="field">
              <span>{{ $t('inventory.invoice.date') }}</span>
              <!-- The last native date input in the app (QAD-182). It rendered
                   in the browser's OS locale, so the same faktura read
                   28/07/2026 here and 07/28/2026 on an en-US machine. -->
              <DateField v-model="invoiceForm.invoiceDate" :max="today" required />
            </label>
            <div class="field">
              <span>{{ $t('inventory.invoice.number') }}</span>
              <span
                class="flex min-h-10 items-center rounded-md border border-hairline bg-sunk px-3 font-mono text-sm font-bold text-ink-muted"
              >
                {{ $t('inventory.invoice.numberAuto') }}
              </span>
            </div>
          </div>
          <label v-if="invoiceForm.supplierId === 'inline'" class="field !mb-0">
            <span>{{ $t('inventory.invoice.inlineSupplierName') }}</span>
            <input v-model="invoiceForm.inlineSupplierName" class="mp-input" required />
          </label>

          <div class="grid gap-2">
            <div class="table-wrap">
              <table class="tbl">
                <thead>
                  <tr>
                    <th>{{ $t('inventory.invoice.columnMaterial') }}</th>
                    <th class="right">{{ $t('inventory.invoice.columnQuantity') }}</th>
                    <th class="right">{{ $t('inventory.invoice.columnPrice') }}</th>
                    <th class="right">{{ $t('inventory.invoice.columnAmount') }}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="line in invoiceLines" :key="line.key">
                    <td class="min-w-52">
                      <!-- The column header carries the label on screen; the
                           bound one stays for screen readers. -->
                      <SearchCombobox
                        v-model="line.materialId"
                        :label="$t('inventory.invoice.columnMaterial')"
                        label-class="sr-only"
                        :options="stockOptions"
                        compact
                        @update:model-value="onLineMaterialChange(line)"
                      />
                    </td>
                    <td class="min-w-28">
                      <span class="mp-unit-field">
                        <input
                          v-model="line.quantity"
                          class="mp-input text-right"
                          inputmode="decimal"
                          :aria-label="
                            $t('inventory.invoice.quantityAria', { unit: lineQuantityUnit(line) })
                          "
                          placeholder="0"
                        />
                        <span class="mp-unit-suffix" aria-hidden="true">{{
                          lineQuantityUnit(line)
                        }}</span>
                      </span>
                    </td>
                    <td class="min-w-32">
                      <span class="mp-unit-field">
                        <input
                          v-model="line.unitPrice"
                          class="mp-input text-right"
                          inputmode="decimal"
                          :aria-label="
                            $t('inventory.invoice.priceAria', { unit: linePriceUnit(line) })
                          "
                          placeholder="0"
                          @input="line.priceEdited = true"
                        />
                        <span class="mp-unit-suffix" aria-hidden="true">{{
                          linePriceUnit(line)
                        }}</span>
                      </span>
                      <small
                        v-if="lineLastPriceHint(line)"
                        class="block text-[11px] text-ink-muted"
                      >
                        {{ lineLastPriceHint(line) }}
                      </small>
                    </td>
                    <td class="amt">
                      {{
                        lineTotalTiyin(line) !== null ? formatTiyin(lineTotalTiyin(line) ?? 0) : '—'
                      }}
                    </td>
                    <td class="right">
                      <button
                        type="button"
                        class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                        :aria-label="$t('inventory.invoice.removeLineAria')"
                        @click="removeInvoiceLine(line.key)"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div>
              <button
                type="button"
                class="mp-button mp-button-outline min-h-9 px-3 text-sm"
                @click="addInvoiceLine"
              >
                {{ $t('inventory.invoice.addLine') }}
              </button>
            </div>
            <small v-if="invoiceLinesError" class="mp-field-error">{{ invoiceLinesError }}</small>
          </div>

          <div class="grid gap-3 md:grid-cols-2">
            <!-- `self-start`: a one-line note must not stretch to the height of
                 the totals block sitting beside it. -->
            <label class="field !mb-0 self-start">
              <span>{{ $t('inventory.invoice.noteLabel') }}</span>
              <input
                v-model="invoiceForm.note"
                class="mp-input"
                :placeholder="$t('inventory.invoice.notePlaceholder')"
              />
            </label>
            <div class="grid gap-2 rounded-md border border-hairline bg-sunk p-3 text-sm">
              <div class="flex items-center justify-between">
                <span class="text-ink-soft">{{ $t('inventory.invoice.subtotal') }}</span>
                <span class="num font-bold">{{ formatTiyin(invoiceSubtotalTiyin) }}</span>
              </div>
              <label class="flex items-center justify-between gap-3">
                <span class="text-ink-soft">{{ $t('inventory.invoice.discount') }}</span>
                <input
                  v-model="invoiceForm.discount"
                  class="mp-input max-w-40 text-right"
                  inputmode="numeric"
                  placeholder="0"
                />
              </label>
              <label class="flex items-center justify-between gap-3">
                <span class="text-ink-soft">{{ $t('inventory.invoice.surcharge') }}</span>
                <input
                  v-model="invoiceForm.surcharge"
                  class="mp-input max-w-40 text-right"
                  inputmode="numeric"
                  placeholder="0"
                />
              </label>
              <small v-if="invoiceDiscountError" class="mp-field-error">
                {{ invoiceDiscountError }}
              </small>
              <div
                class="flex items-center justify-between border-t border-hairline-strong pt-2 font-bold"
              >
                <span>{{ $t('inventory.invoice.total') }}</span>
                <span class="num">{{ formatTiyin(invoiceTotalTiyin) }}</span>
              </div>
            </div>
          </div>

          <p
            v-if="movementError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            {{
              movementError === 'branch_material_not_found'
                ? $t('inventory.error.branch_material_not_found')
                : $t('inventory.error.invoice_save_failed')
            }}
          </p>
          <div class="flex flex-wrap items-center gap-2">
            <button type="submit" class="mp-button mp-button-primary" :disabled="movementSaving">
              {{ movementSaving ? $t('inventory.action.saving') : $t('inventory.action.save') }}
            </button>
            <button
              v-if="canSeeDebts"
              type="button"
              class="mp-button mp-button-outline"
              :disabled="movementSaving"
              @click="saveInvoice(true)"
            >
              {{ $t('inventory.invoice.saveWithExpense') }}
            </button>
            <button type="button" class="mp-button mp-button-outline" @click="invoiceOpen = false">
              {{ $t('inventory.action.cancel') }}
            </button>
          </div>
        </form>
      </AppModal>

      <AppModal
        :open="adjustmentOpen"
        :title="$t('inventory.adjustment.title')"
        @close="adjustmentOpen = false"
      >
        <form class="grid gap-3" @submit.prevent="recordAdjustment">
          <SearchCombobox
            v-model="adjustmentForm.materialId"
            :label="$t('inventory.adjustment.material')"
            :options="stockOptions"
            :error="adjustmentMaterialError"
          />
          <label class="field">
            <span>{{
              selectedAdjustmentItem
                ? $t('inventory.adjustment.quantityWithUnit', {
                    unit: formatStockUnit(selectedAdjustmentItem.display_unit),
                  })
                : $t('inventory.adjustment.quantity')
            }}</span>
            <!-- Signed quantity: "-2" decreases, "+5" increases — the prefix is
                 required, so inputmode stays text (numeric keypads lack +/−). -->
            <input
              v-model="adjustmentForm.quantity"
              class="mp-input"
              :placeholder="$t('inventory.adjustment.quantityPlaceholder')"
              required
            />
            <small v-if="adjustmentNeedsSign" class="text-ink-muted">
              {{ $t('inventory.adjustment.signHint') }}
            </small>
          </label>
          <label class="field">
            <span>{{ $t('inventory.adjustment.noteLabel') }}</span>
            <input v-model="adjustmentForm.note" class="mp-input" required />
          </label>
          <p
            v-if="movementError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            {{ $t('inventory.error.adjustment_failed') }}
          </p>
          <button type="submit" class="mp-button mp-button-primary" :disabled="movementSaving">
            {{ movementSaving ? $t('inventory.action.saving') : $t('inventory.action.save') }}
          </button>
        </form>
      </AppModal>

      <div v-if="workshop.inventoryLoading && activeListEmpty" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </div>

      <div v-else-if="workshop.inventoryError && activeListEmpty" class="st-error">
        <h3>{{ $t('inventory.load.failedTitle') }}</h3>
        <p>{{ traceLine(workshop.inventoryTraceId) }}</p>
      </div>

      <section v-else-if="activeTab === 'stock'" class="card">
        <div v-if="workshop.inventoryError" class="banner danger m-4">
          <div class="grow">
            {{ $t('inventory.load.stockBanner') }} · {{ traceLine(workshop.inventoryTraceId) }}
          </div>
        </div>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>{{ $t('inventory.stock.columnMaterial') }}</th>
                <th class="right">{{ $t('inventory.stock.columnOnHand') }}</th>
                <th class="right">{{ $t('inventory.stock.columnMin') }}</th>
                <th>{{ $t('inventory.stock.columnStatus') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in workshop.stockItems" :key="item.id">
                <td>
                  <div class="flex min-w-0 items-center gap-3">
                    <span class="sw" :class="materialSwatchClass(item.material.dekor)"></span>
                    <span class="min-w-0">
                      <span class="nm">{{ item.material.label }}</span>
                      <small class="block truncate text-ink-muted">{{ materialMeta(item) }}</small>
                    </span>
                  </div>
                </td>
                <td
                  class="amt"
                  :class="
                    isNegative(item) ? 'danger-text' : item.is_low_stock ? 'warn-text' : undefined
                  "
                >
                  {{ formatStockQuantity(item.on_hand, item.display_unit) }}
                  <small
                    v-if="isNegative(item) || item.is_low_stock"
                    class="block text-[11px] font-extrabold"
                  >
                    {{
                      isNegative(item)
                        ? $t('inventory.stock.noteNegative')
                        : $t('inventory.stock.noteLow')
                    }}
                  </small>
                </td>
                <td class="amt muted">
                  {{ formatStockQuantity(item.min_stock, item.display_unit) }}
                </td>
                <td>
                  <span
                    :class="
                      isNegative(item)
                        ? 'pill p-bad'
                        : item.is_low_stock
                          ? 'pill p-warn'
                          : 'pill p-ok'
                    "
                  >
                    <span class="pd"></span
                    >{{
                      isNegative(item)
                        ? $t('inventory.stock.pillNegative')
                        : item.is_low_stock
                          ? $t('inventory.stock.pillLow')
                          : $t('inventory.stock.pillEnough')
                    }}
                  </span>
                </td>
              </tr>
              <tr v-if="workshop.stockItems.length === 0">
                <td colspan="4">
                  <div class="st-empty !border-0 !py-8">
                    <template v-if="stockFiltered">
                      <h3>{{ $t('inventory.stock.emptyFilteredTitle') }}</h3>
                      <p>{{ $t('inventory.stock.emptyFilteredBody') }}</p>
                    </template>
                    <template v-else>
                      <h3>{{ $t('inventory.stock.emptyTitle') }}</h3>
                      <p>{{ $t('inventory.stock.emptyBody') }}</p>
                    </template>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section
        v-else-if="activeTab === 'invoices'"
        id="workshop-inventory-invoices-panel"
        class="card"
        role="tabpanel"
        aria-labelledby="workshop-inventory-invoices-tab"
        tabindex="0"
      >
        <div v-if="workshop.inventoryError" class="banner danger m-4">
          <div class="grow">
            {{ $t('inventory.load.invoicesBanner') }} · {{ traceLine(workshop.inventoryTraceId) }}
          </div>
        </div>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>{{ $t('inventory.invoices.columnNumber') }}</th>
                <th>{{ $t('inventory.invoices.columnSupplier') }}</th>
                <th>{{ $t('inventory.invoices.columnDate') }}</th>
                <th class="right">{{ $t('inventory.invoices.columnLines') }}</th>
                <th class="right">{{ $t('inventory.invoices.columnTotal') }}</th>
                <th>{{ $t('inventory.invoices.columnPayment') }}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="invoice in workshop.supplierInvoices" :key="invoice.id">
                <tr class="row-clickable">
                  <td class="nm font-mono">{{ invoice.invoice_no }}</td>
                  <td>
                    {{ invoice.supplier_name ?? '—' }}
                    <small v-if="invoice.note" class="block truncate text-ink-muted">
                      {{ invoice.note }}
                    </small>
                  </td>
                  <td class="num text-ink-muted">{{ formatDate(invoice.invoice_date) }}</td>
                  <td class="num right">
                    {{
                      $t(
                        'inventory.invoices.lineCount',
                        { n: invoice.line_count },
                        invoice.line_count,
                      )
                    }}
                  </td>
                  <td class="amt">
                    {{ formatTiyin(invoice.total_tiyin) }}
                    <small
                      v-if="invoice.discount_tiyin > 0 || invoice.surcharge_tiyin > 0"
                      class="block text-[11px] text-ink-muted"
                    >
                      <template v-if="invoice.discount_tiyin > 0">
                        {{
                          $t('inventory.invoices.discountLine', {
                            amount: formatTiyin(invoice.discount_tiyin),
                          })
                        }}
                      </template>
                      <template v-if="invoice.surcharge_tiyin > 0">
                        {{
                          $t('inventory.invoices.surchargeLine', {
                            amount: formatTiyin(invoice.surcharge_tiyin),
                          })
                        }}
                      </template>
                    </small>
                  </td>
                  <td>
                    <span :class="paymentStatusPill(invoice.payment_status).cls">
                      <span class="pd"></span>{{ paymentStatusPill(invoice.payment_status).text }}
                    </span>
                    <small
                      v-if="invoice.outstanding_tiyin > 0 && invoice.paid_tiyin > 0"
                      class="block text-[11px] text-ink-muted"
                    >
                      {{
                        $t('inventory.invoices.outstanding', {
                          amount: formatTiyin(invoice.outstanding_tiyin),
                        })
                      }}
                    </small>
                  </td>
                  <td class="right">
                    <!-- The chevron is the whole row's control (QAD-184): it
                         stretches over the row and states the row it expands,
                         while `aria-expanded` carries open/closed. -->
                    <button
                      type="button"
                      class="mp-row-icon row-open"
                      :aria-label="
                        $t('inventory.invoices.expandAria', { invoice: invoice.invoice_no })
                      "
                      :aria-expanded="isInvoiceExpanded(invoice.id)"
                      :aria-controls="`invoice-lines-${invoice.id}`"
                      @click="toggleInvoice(invoice.id)"
                    >
                      <AppIcon
                        name="chevron-down"
                        :class="isInvoiceExpanded(invoice.id) ? 'rotate-180' : ''"
                      />
                    </button>
                  </td>
                </tr>
                <tr v-if="isInvoiceExpanded(invoice.id)" :id="`invoice-lines-${invoice.id}`">
                  <td colspan="7" class="bg-sunk">
                    <table class="tbl">
                      <thead>
                        <tr>
                          <th>{{ $t('inventory.invoice.columnMaterial') }}</th>
                          <th class="right">{{ $t('inventory.invoice.columnQuantity') }}</th>
                          <th class="right">{{ $t('inventory.invoice.columnPrice') }}</th>
                          <th class="right">{{ $t('inventory.invoice.columnAmount') }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="line in invoice.lines" :key="line.transaction_id">
                          <td class="nm">{{ line.material_name }}</td>
                          <td class="amt">
                            {{ formatStockQuantity(line.quantity, line.display_unit) }}
                          </td>
                          <td class="amt">
                            {{
                              line.unit_price_tiyin !== null
                                ? formatTiyin(line.unit_price_tiyin)
                                : '—'
                            }}
                          </td>
                          <td class="amt">
                            {{
                              line.total_price_tiyin !== null
                                ? formatTiyin(line.total_price_tiyin)
                                : '—'
                            }}
                          </td>
                        </tr>
                        <tr>
                          <td colspan="3" class="right text-ink-soft">
                            {{ $t('inventory.invoice.subtotal') }}
                          </td>
                          <td class="amt">{{ formatTiyin(invoice.subtotal_tiyin) }}</td>
                        </tr>
                        <tr v-if="invoice.discount_tiyin > 0">
                          <td colspan="3" class="right text-ink-soft">
                            {{ $t('inventory.invoice.discount') }}
                          </td>
                          <td class="amt danger-text">
                            −{{ formatTiyin(invoice.discount_tiyin) }}
                          </td>
                        </tr>
                        <tr v-if="invoice.surcharge_tiyin > 0">
                          <td colspan="3" class="right text-ink-soft">
                            {{ $t('inventory.invoice.surcharge') }}
                          </td>
                          <td class="amt">+{{ formatTiyin(invoice.surcharge_tiyin) }}</td>
                        </tr>
                        <tr>
                          <td colspan="3" class="right font-bold">
                            {{ $t('inventory.invoice.total') }}
                          </td>
                          <td class="amt font-bold">{{ formatTiyin(invoice.total_tiyin) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </td>
                </tr>
              </template>
              <tr v-if="workshop.supplierInvoices.length === 0">
                <td colspan="7">
                  <div class="st-empty !border-0 !py-8">
                    <h3>
                      {{
                        invoiceSearch.trim() || invoicePaymentFilter !== 'all'
                          ? $t('inventory.invoices.emptyFilteredTitle')
                          : $t('inventory.invoices.emptyTitle')
                      }}
                    </h3>
                    <p>
                      {{
                        invoiceSearch.trim() || invoicePaymentFilter !== 'all'
                          ? $t('inventory.invoices.emptyFilteredBody')
                          : $t('inventory.invoices.emptyBody')
                      }}
                    </p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section
        v-else-if="activeTab === 'tx'"
        id="workshop-inventory-tx-panel"
        class="card"
        role="tabpanel"
        aria-labelledby="workshop-inventory-tx-tab"
        tabindex="0"
      >
        <div v-if="workshop.inventoryError" class="banner danger m-4">
          <div class="grow">
            {{ $t('inventory.load.txBanner') }} · {{ traceLine(workshop.inventoryTraceId) }}
          </div>
        </div>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>{{ $t('inventory.tx.columnTime') }}</th>
                <th>{{ $t('inventory.tx.columnType') }}</th>
                <th>{{ $t('inventory.tx.columnMaterial') }}</th>
                <th class="right">{{ $t('inventory.tx.columnQuantity') }}</th>
                <th>{{ $t('inventory.tx.columnBalance') }}</th>
                <th class="right">{{ $t('inventory.tx.columnPrice') }}</th>
                <th class="right">{{ $t('inventory.tx.columnAmount') }}</th>
                <th>{{ $t('inventory.tx.columnOrder') }}</th>
                <th>{{ $t('inventory.tx.columnSupplier') }}</th>
                <th>{{ $t('inventory.tx.columnActor') }}</th>
                <th>{{ $t('inventory.tx.columnNote') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in workshop.stockTransactions" :key="tx.id">
                <td class="num text-ink-muted">{{ formatDateTime(tx.created_at) }}</td>
                <td>
                  <span
                    :class="
                      tx.type === 'stock_in'
                        ? 'pill p-ok'
                        : tx.type === 'adjust'
                          ? 'pill p-warn'
                          : tx.type === 'restore'
                            ? 'pill p-conf'
                            : 'pill p-bad'
                    "
                  >
                    <span class="pd"></span>{{ stockTransactionTypeLabel(tx.type) }}
                  </span>
                </td>
                <td class="nm">{{ tx.material_name }}</td>
                <td class="amt" :class="tx.quantity >= 0 ? 'success-text' : 'danger-text'">
                  {{ formatTransactionQuantity(tx.quantity, tx.branch_material_id) }}
                </td>
                <td class="num muted">
                  {{
                    formatStockQuantity(
                      tx.balance_after,
                      transactionDisplayUnit(tx.branch_material_id),
                    )
                  }}
                </td>
                <td class="amt">
                  {{ tx.unit_price_tiyin !== null ? formatTiyin(tx.unit_price_tiyin) : '—' }}
                </td>
                <td class="amt">
                  {{ tx.total_price_tiyin !== null ? formatTiyin(tx.total_price_tiyin) : '—' }}
                </td>
                <td>
                  <RouterLink
                    v-if="tx.order_id"
                    :to="rolePath(`/workshop/orders/${tx.order_id}`)"
                    class="id no-underline"
                  >
                    {{ tx.order_id.slice(0, 8) }}
                  </RouterLink>
                  <span v-else class="muted">—</span>
                </td>
                <td>
                  <small class="text-ink-soft">{{ tx.supplier_name ?? '—' }}</small>
                </td>
                <td>
                  <small class="text-ink-soft">{{ transactionActorName(tx) }}</small>
                </td>
                <td>
                  <small class="text-ink-soft">{{ tx.note ?? '—' }}</small>
                </td>
              </tr>
              <tr v-if="workshop.stockTransactions.length === 0">
                <td colspan="11">
                  <div class="st-empty !border-0 !py-8">
                    <h3>{{ $t('inventory.tx.emptyTitle') }}</h3>
                    <p>{{ $t('inventory.tx.emptyBody') }}</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div
          v-if="workshop.stockTransactionsHasMore"
          class="flex justify-center border-t border-hairline p-4"
        >
          <button
            class="mp-button mp-button-outline min-h-10 px-4 text-sm"
            type="button"
            :disabled="workshop.inventoryLoading"
            @click="loadMoreTransactions"
          >
            {{
              workshop.inventoryLoading ? $t('inventory.tx.loading') : $t('inventory.tx.loadMore')
            }}
          </button>
        </div>
      </section>

      <section
        v-else
        id="workshop-inventory-suppliers-panel"
        role="tabpanel"
        aria-labelledby="workshop-inventory-suppliers-tab"
        tabindex="0"
      >
        <div class="mp-filters">
          <button type="button" class="mp-button mp-button-primary" @click="openCreateSupplier">
            {{ $t('inventory.supplier.createAction') }}
          </button>
        </div>

        <AppModal
          :open="supplierModalOpen"
          :title="
            editingSupplierId
              ? $t('inventory.supplier.editTitle')
              : $t('inventory.supplier.createTitle')
          "
          @close="closeSupplierModal"
        >
          <form class="grid gap-3" @submit.prevent="saveSupplier">
            <label class="field">
              <span>{{ $t('inventory.supplier.nameLabel') }}</span>
              <input v-model="supplierForm.name" class="mp-input" required />
            </label>
            <label class="field">
              <span>{{ $t('inventory.supplier.phoneLabel') }}</span>
              <PhoneInput v-model="supplierForm.phone" />
            </label>
            <label class="field">
              <span>{{ $t('inventory.supplier.noteLabel') }}</span>
              <input v-model="supplierForm.note" class="mp-input" />
            </label>
            <p
              v-if="supplierError"
              class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              {{ $t('inventory.error.supplier_save_failed') }}
            </p>
            <div class="flex items-center gap-2">
              <button type="submit" class="mp-button mp-button-primary" :disabled="supplierSaving">
                {{
                  supplierSaving
                    ? $t('inventory.action.saving')
                    : editingSupplierId
                      ? $t('inventory.action.save')
                      : $t('inventory.action.add')
                }}
              </button>
              <button type="button" class="mp-button mp-button-outline" @click="closeSupplierModal">
                {{ $t('inventory.action.cancel') }}
              </button>
            </div>
          </form>
        </AppModal>

        <section class="card">
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>{{ $t('inventory.supplier.columnName') }}</th>
                  <th>{{ $t('inventory.supplier.columnPhone') }}</th>
                  <th>{{ $t('inventory.supplier.columnNote') }}</th>
                  <th v-if="canSeeDebts" class="right">
                    {{ $t('inventory.supplier.columnDebt') }}
                  </th>
                  <th>{{ $t('inventory.supplier.columnStatus') }}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="supplier in workshop.suppliers" :key="supplier.id" class="row-clickable">
                  <td class="nm">
                    <!-- The name runs the row's primary action — edit (QAD-184);
                         blocking lives in the ⋯ menu, with its word intact. -->
                    <button
                      type="button"
                      class="row-open row-open-text"
                      :aria-label="$t('inventory.supplier.editAria', { name: supplier.name })"
                      :disabled="supplierSaving"
                      @click="editSupplier(supplier)"
                    >
                      {{ supplier.name }}
                    </button>
                  </td>
                  <td class="num">{{ supplier.phone ?? '—' }}</td>
                  <td>{{ supplier.note ?? '—' }}</td>
                  <td v-if="canSeeDebts" class="right">
                    <span
                      v-if="supplierBalanceChip(supplier.id).cls"
                      :class="supplierBalanceChip(supplier.id).cls"
                    >
                      <span class="pd"></span>{{ supplierBalanceChip(supplier.id).text }}
                    </span>
                    <span v-else class="text-ink-muted">—</span>
                  </td>
                  <td>
                    <span :class="supplier.status === 'active' ? 'pill p-ok' : 'pill p-dn'">
                      <span class="pd"></span
                      >{{
                        supplier.status === 'active'
                          ? $t('inventory.supplier.statusActive')
                          : $t('inventory.supplier.statusInactive')
                      }}
                    </span>
                  </td>
                  <td class="right">
                    <ActionMenu
                      :items="supplierMenuItems(supplier)"
                      :label="$t('inventory.supplier.menuAria', { name: supplier.name })"
                      @select="toggleSupplierStatus(supplier)"
                    />
                  </td>
                </tr>
                <tr v-if="workshop.suppliers.length === 0">
                  <td :colspan="canSeeDebts ? 6 : 5">
                    <div class="st-empty !border-0 !py-8">
                      <h3>{{ $t('inventory.supplier.emptyTitle') }}</h3>
                      <p>{{ $t('inventory.supplier.emptyBody') }}</p>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </template>
  </section>
</template>
