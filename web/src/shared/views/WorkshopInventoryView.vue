<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { INVENTORY_INVOICE_PAGE_LIMIT, INVENTORY_TX_PAGE_LIMIT } from '@/shared/app/constants'
import { presetRange, type DateRangePreset } from '@/shared/app/dateRange'
import { traceLine } from '@/shared/app/errorTrace'
import {
  decorTypeFilterGroups,
  decorTypeLabel,
  decorTypePillClass,
  formatDimensionsLabel,
} from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { useRolePath } from '@/shared/app/paths'
import type { DropdownOption } from '@/shared/app/roleConfig'
import {
  isScopeWidened,
  isStockFiltered,
  stockEmptyKind,
  stockListFilters,
  type StockScope,
} from '@/shared/app/stockScope'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { stockTransactionTypeLabel } from '@/shared/app/workshopUi'
import ActionMenu, { type ActionMenuItem } from '@/shared/components/ActionMenu.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import AppModal from '@/shared/components/AppModal.vue'
import AppTabs from '@/shared/components/AppTabs.vue'
import FilterStatus from '@/shared/components/FilterStatus.vue'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import type { DecorType } from '@/shared/stores/admin'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { useFinanceStore } from '@/shared/stores/finance'
import { formatDate, formatDateTime, formatStockQuantity, formatTiyin } from '@/shared/formatters'
import {
  useWorkshopStore,
  type InvoicePaymentStatus,
  type StockItem,
  type StockTransaction,
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
const INVENTORY_TABS = ['stock', 'invoices', 'tx', 'suppliers'] as const
type InventoryTab = (typeof INVENTORY_TABS)[number]

// `?tab=` is honoured the same way `?search=` is, so a link can name the tab it
// means. The arrival form is no longer a modal here — it is a page of its own
// (`/workshop/inventory/invoices/new`), so nothing has to be "opened" on mount.
function routeTab(): InventoryTab | null {
  const value = route.query.tab
  return typeof value === 'string' && (INVENTORY_TABS as readonly string[]).includes(value)
    ? (value as InventoryTab)
    : null
}

const activeTab = ref<InventoryTab>(routeTab() ?? 'stock')
const inventoryTabs = computed<ChoiceOption[]>(() => [
  { value: 'stock', label: t('inventory.tab.stock') },
  { value: 'invoices', label: t('inventory.tab.invoices') },
  { value: 'tx', label: t('inventory.tab.tx') },
  { value: 'suppliers', label: t('inventory.tab.suppliers') },
])
const search = ref('')
const lowOnly = ref(false)
// The Zaxira tab shows the warehouse, not the catalog: by default only rows
// that have actually moved. «Butun katalog» opens it up to every attached
// material — the state the tab used to be in permanently.
const wholeCatalog = ref(false)
// One shelf holds panels and tape, but "yetarli kromka bormi?" and "qaysi list
// tugab qolgan?" are different questions — the `type` filter is how the operator
// asks one of them at a time. It narrows the current scope rather than widening
// it: unlike search, it is browsing, not a lookup.
// The picked option's key is the first wire value behind its label; the label's
// other members ride along (see `decorTypeFilterGroups`), which is why the query
// is a list and the dropdown never prints «LDSP» twice.
const stockTur = ref<DecorType | 'all'>('all')
const stockTurGroups = computed(() => decorTypeFilterGroups())
const stockTurOptions = computed<DropdownOption[]>(() => [
  { value: 'all', label: t('inventory.stock.turAll') },
  ...stockTurGroups.value.map((group) => ({ value: group.types[0], label: group.label })),
])
const stockTurlar = computed<DecorType[]>(
  () => stockTurGroups.value.find((group) => group.types[0] === stockTur.value)?.types ?? [],
)

const stockScope = computed<StockScope>(() => ({
  search: search.value,
  lowOnly: lowOnly.value,
  wholeCatalog: wholeCatalog.value,
  types: stockTurlar.value,
}))
// A branch with 30 materials told the operator it had none, because the empty
// state did not know a search was active (QAD-182). First-run and
// filtered-empty are different facts and get different copy.
const stockFiltered = computed(() => isStockFiltered(stockScope.value))
// "The scope is forced": search and the low chip always widen to the whole
// catalog, so while either is on the «Butun katalog» chip has nothing left to
// decide and says so instead of pretending to toggle. The `type` filter is not
// in here — it narrows within the scope and leaves the chip its job.
const stockScopeForced = computed(() => isScopeWidened(stockScope.value))
// One control clears its own filter, so a single active filter needs no reset
// link; a combination is what leaves the operator hunting for what is still on.
const stockFilterCount = computed(
  () =>
    (search.value.trim() ? 1 : 0) + (lowOnly.value ? 1 : 0) + (stockTur.value !== 'all' ? 1 : 0),
)

function resetStockFilters() {
  search.value = ''
  lowOnly.value = false
  stockTur.value = 'all'
}
const stockEmptyState = computed(() =>
  stockEmptyKind(stockScope.value, workshop.stockPickerItems.length > 0),
)
const txPreset = ref<DateRangePreset>('days30')
const initialTxRange = presetRange('days30')
const txDateFrom = ref(initialTxRange.from ?? '')
const txDateTo = ref(initialTxRange.to ?? '')
// Material filter doubles as the price-history view: one material's stock-in
// rows read as its purchase-price timeline.
const txMaterialId = ref('all')
const supplierSaving = ref(false)
const supplierError = ref<string | null>(null)
const editingSupplierId = ref<string | null>(null)
const supplierModalOpen = ref(false)
const stockLoadedKey = ref<string | null>(null)
const transactionsLoadedKey = ref<string | null>(null)
const invoicesLoadedKey = ref<string | null>(null)
const suppliersLoadedBranch = ref<string | null>(null)
const invoiceSearch = ref('')
const invoicePaymentFilter = ref<InvoicePaymentStatus | 'all'>('all')
// Unlike the movements tab, the arrivals list opens on the whole archive: a
// faktura is looked up by number or supplier months after it was booked, and a
// 30-day default would answer "yo'q" to most of those searches.
const invoicePreset = ref<DateRangePreset>('all')
const invoiceDateFrom = ref('')
const invoiceDateTo = ref('')
const invoiceSupplierId = ref('all')
let stockSearchTimer: number | undefined
let invoiceSearchTimer: number | undefined

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
// Branch is driven by the topbar context picker (WorkshopShell); the page follows it
// and falls back to the first accessible branch until context is set.
const selectedBranchId = computed(() => {
  const context = workshop.selectedBranchContext
  if (context && accessibleBranches.value.some((branch) => branch.id === context)) return context
  return accessibleBranches.value[0]?.id ?? ''
})
/**
 * Every material the branch carries — the source for pickers and lookups.
 *
 * Not `workshop.stockItems`: that list is now the *table's*, scoped to rows
 * that have moved. A combobox fed from it would silently refuse the most
 * common arrival there is, the first one for a material nobody has stocked.
 * The table's rows stand in until the picker collection lands, so a modal
 * opened from a row menu can resolve its label before the fetch returns.
 */
const pickerItems = computed(() =>
  workshop.stockPickerItems.length > 0 ? workshop.stockPickerItems : workshop.stockItems,
)
const displayUnitByMaterialId = computed(
  () => new Map(pickerItems.value.map((item) => [item.branch_material_id, item.display_unit])),
)
const txMaterialOptions = computed<DropdownOption[]>(() => [
  { value: 'all', label: t('inventory.tx.materialFilterAll') },
  ...pickerItems.value.map((item) => ({
    value: item.branch_material_id,
    label: item.material.label,
  })),
])
const invoiceFiltered = computed(
  () =>
    Boolean(invoiceSearch.value.trim()) ||
    invoicePaymentFilter.value !== 'all' ||
    invoiceSupplierId.value !== 'all' ||
    Boolean(invoiceDateFrom.value) ||
    Boolean(invoiceDateTo.value),
)
const invoiceSupplierOptions = computed<DropdownOption[]>(() => [
  { value: 'all', label: t('inventory.invoices.supplierFilterAll') },
  ...workshop.suppliers.map((supplier) => ({ value: supplier.id, label: supplier.name })),
])
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

const activeListEmpty = computed(() => {
  if (activeTab.value === 'stock') return workshop.stockItems.length === 0
  if (activeTab.value === 'invoices') return workshop.supplierInvoices.length === 0
  if (activeTab.value === 'tx') return workshop.stockTransactions.length === 0
  return workshop.suppliers.length === 0
})

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
// A movement's pill reads its direction: arrivals green, everything that takes
// stock away red, corrections amber, restores neutral. A void reversal is a
// stock-out of an arrival that should not have been booked, so it sits with the
// other subtractions rather than borrowing the arrival's green.
function transactionTypePill(type: StockTransaction['type']) {
  if (type === 'stock_in') return 'pill p-ok'
  if (type === 'adjust') return 'pill p-warn'
  if (type === 'restore') return 'pill p-conf'
  return 'pill p-bad'
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
  const filters = stockListFilters(stockScope.value)
  return [
    selectedBranchId.value,
    filters.search,
    filters.low_stock ? 'low' : 'all',
    filters.moved_only ? 'moved' : 'catalog',
    filters.types?.join('+') ?? 'any',
  ].join(':')
}

function invoiceFilterKey() {
  return [
    selectedBranchId.value,
    invoiceSearch.value.trim(),
    invoicePaymentFilter.value,
    invoiceDateFrom.value || 'open',
    invoiceDateTo.value || 'open',
    invoiceSupplierId.value,
  ].join(':')
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
      const filters = stockListFilters(stockScope.value)
      await workshop.loadStock(branchId, filters)
      stockLoadedKey.value = stockKey
      // An empty moved scope has two possible causes with opposite advice —
      // nothing has moved yet, or the branch carries nothing at all. The
      // picker collection answers that, and only this case needs it.
      if (workshop.stockItems.length === 0 && filters.moved_only) await ensureStockPicker()
      return
    }
    if (activeTab.value === 'invoices') {
      await workshop.loadSupplierInvoices(branchId, {
        search: invoiceSearch.value.trim() || null,
        payment_status: invoicePaymentFilter.value === 'all' ? null : invoicePaymentFilter.value,
        supplier_id: invoiceSupplierId.value === 'all' ? null : invoiceSupplierId.value,
        date_from: invoiceDateFrom.value || null,
        date_to: invoiceDateTo.value || null,
        limit: INVENTORY_INVOICE_PAGE_LIMIT,
        offset,
      })
      if (offset === 0) invoicesLoadedKey.value = invoiceKey
      // The supplier filter needs the branch's suppliers, which otherwise only
      // load on their own tab.
      if (workshop.suppliers.length === 0) await workshop.loadSuppliers(branchId)
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

async function loadMoreInvoices() {
  if (!selectedBranchId.value) return
  activeTab.value = 'invoices'
  await refreshActiveInventoryTab({ force: true, offset: workshop.supplierInvoices.length })
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

/**
 * The arrival form opened from a stock row: the page seeds line 1 from
 * `?material=`, so the row-opened form still lands with that material picked,
 * its last price in flight and focus in the quantity field.
 */
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
  workshop.clearInventory()
  void refreshActiveInventoryTab({ force: true })
})

watch(activeTab, () => {
  void refreshActiveInventoryTab()
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

watch([search, lowOnly, wholeCatalog, stockTur], () => {
  window.clearTimeout(stockSearchTimer)
  stockSearchTimer = window.setTimeout(() => {
    if (activeTab.value === 'stock') void refreshActiveInventoryTab({ force: true })
  }, 250)
})

watch([invoiceDateFrom, invoiceDateTo, invoiceSupplierId], () => {
  if (activeTab.value !== 'invoices') return
  void refreshActiveInventoryTab()
})

watch([invoiceSearch, invoicePaymentFilter], () => {
  window.clearTimeout(invoiceSearchTimer)
  invoiceSearchTimer = window.setTimeout(() => {
    if (activeTab.value === 'invoices') void refreshActiveInventoryTab({ force: true })
  }, 250)
})

/**
 * The branch's whole material list, for anything that has to offer a choice.
 *
 * Idempotent per branch inside the store, so every caller can just ask: the
 * modals on open, the Tranzaksiyalar tab for its material filter, and the
 * stock table when a moved-scope load came back empty and the empty state has
 * to say which of the two emptinesses it is.
 */
async function ensureStockPicker() {
  if (!selectedBranchId.value) return
  await workshop.loadStockPicker(selectedBranchId.value).catch(() => undefined)
}

watch(activeTab, (tab) => {
  // The transactions tab needs the picker list for its material filter and for
  // the display unit each row's quantity is printed in. Kirimlar needs neither
  // any more — its form left for a page of its own.
  if (tab === 'tx') void ensureStockPicker()
})

onMounted(async () => {
  applyRouteSearch()
  await workshop.loadBranchContext().catch(() => undefined)
  await refreshActiveInventoryTab({ force: true })
  // A `?tab=` deep link opens straight on its tab, so the tab-change watcher
  // that primes the picker never fired for it.
  if (activeTab.value === 'tx') void ensureStockPicker()
  // `?material=` is a filter preset for the transactions tab — «Barcha
  // harakatlar» on the material page arrives with it — and is consumed rather
  // than kept, so a reload does not re-apply a filter the operator cleared.
  // The material itself is a page now, not a query on this one.
  const deepLinkedMaterial = route.query.material
  if (typeof deepLinkedMaterial !== 'string' || !deepLinkedMaterial) return
  if (activeTab.value !== 'tx') return
  txMaterialId.value = deepLinkedMaterial
  const query = { ...route.query }
  delete query.material
  await router.replace({ query })
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
        <!-- Panels and tape share a shelf but not a question — one `type` at a
             time is how the operator reads one of them. -->
        <ProjectDropdown
          v-if="activeTab === 'stock'"
          v-model="stockTur"
          :label="$t('inventory.stock.turLabel')"
          :options="stockTurOptions"
          top-label
        />
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
        <!-- The scope, not a filter: the table shows the warehouse, this opens
             it to the whole catalog. While a search or the low chip is on, the
             list is already the whole catalog — the chip says so rather than
             offering a press that changes nothing. -->
        <button
          v-if="activeTab === 'stock'"
          type="button"
          class="mp-filter-chip"
          :aria-pressed="wholeCatalog || stockScopeForced"
          :disabled="stockScopeForced"
          :title="stockScopeForced ? $t('inventory.stock.wholeCatalogForced') : undefined"
          @click="wholeCatalog = !wholeCatalog"
        >
          <span class="mp-filter-chip-dot" aria-hidden="true"></span>
          {{ $t('inventory.stock.wholeCatalog') }}
        </button>
        <!-- Narrower than the shared 340px: this box holds a `K-0007`, never a
             material name — the supplier moved to its own dropdown. -->
        <label v-if="activeTab === 'invoices'" class="mp-filter-input !max-w-[190px]">
          <span>{{ $t('inventory.invoices.searchLabel') }}</span>
          <input
            v-model="invoiceSearch"
            :placeholder="$t('inventory.invoices.searchPlaceholder')"
          />
        </label>
        <DateRangePicker
          v-if="activeTab === 'invoices'"
          v-model:preset="invoicePreset"
          v-model:date-from="invoiceDateFrom"
          v-model:date-to="invoiceDateTo"
        />
        <ProjectDropdown
          v-if="activeTab === 'invoices'"
          v-model="invoiceSupplierId"
          :label="$t('inventory.invoices.supplierFilterLabel')"
          :options="invoiceSupplierOptions"
          top-label
        />
        <ProjectDropdown
          v-if="activeTab === 'invoices'"
          v-model="invoicePaymentFilter"
          :label="$t('inventory.invoices.paymentFilterLabel')"
          :options="paymentStatusFilterOptions"
          top-label
        />
        <RouterLink
          v-if="activeTab === 'invoices'"
          :to="rolePath('/workshop/inventory/invoices/new')"
          class="mp-button mp-button-primary no-underline"
        >
          {{ $t('inventory.invoice.createAction') }}
        </RouterLink>
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
        :on-reset="stockFilterCount > 1 ? resetStockFilters : null"
      />

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
                <th class="nowrap w-px">{{ $t('inventory.stock.columnTur') }}</th>
                <th>{{ $t('inventory.stock.columnDekor') }}</th>
                <th class="right">{{ $t('inventory.stock.columnOnHand') }}</th>
                <th>{{ $t('inventory.stock.columnStatus') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in workshop.stockItems" :key="item.id" class="row-clickable">
                <!-- Substrate, decor and o'lcham as three columns rather than one
                     composed label: the shelf is read down a column («qaysi
                     kromkalar?», «shu dekorning qaysi o'lchamlari?»), and a single
                     `LDSP Egger H1137 · Kulrang eman · 2800×2070×18 mm` string
                     forced that reading onto one ragged line. -->
                <td class="nowrap">
                  <span :class="decorTypePillClass(item.type)">
                    <span class="pd"></span>{{ decorTypeLabel(item.type) }}
                  </span>
                </td>
                <td>
                  <div class="flex min-w-0 items-center gap-3">
                    <!-- The decor's own photo, with the hashed swatch only as a
                         fallback for a decor the platform never gave one. This row
                         used to draw the swatch unconditionally, so a real
                         uploaded image never reached the shelf. -->
                    <AuthFileImage
                      v-if="item.material.decor.image_file_id"
                      :file-id="item.material.decor.image_file_id"
                      :alt="item.material.decor.label"
                      class="size-9 shrink-0 rounded-md object-cover"
                    />
                    <span
                      v-else
                      class="sw size-9"
                      :class="materialSwatchClass(item.material.decor)"
                    ></span>
                    <span class="min-w-0">
                      <!-- The name is the row's control: the one thing anyone
                           comes to a stock row to do is read the material's
                           story (QAD-184's row-is-its-own-control pattern). -->
                      <RouterLink
                        :to="rolePath(`/workshop/inventory/materials/${item.branch_material_id}`)"
                        class="nm row-open row-open-text"
                        :aria-label="
                          $t('inventory.stock.openAria', { material: item.material.label })
                        "
                      >
                        {{ item.material.decor.label }}
                      </RouterLink>
                      <!-- The o'lcham sits under the decor rather than in a column
                           of its own: one shelf row is "this decor, in this size",
                           and stacking the two keeps the pair together while the
                           decor names stay a readable column. -->
                      <small class="block truncate text-ink-muted">
                        {{ formatDimensionsLabel(item.material.decor_format) }}
                        <!-- The platform retired the format: the shelf is still
                             real, but nobody will reorder it — said here so a low
                             balance does not read as "buy more". -->
                        <template v-if="item.material.decor_format.status === 'inactive'">
                          · {{ $t('inventory.stock.discontinued') }}
                        </template>
                      </small>
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
                  <!-- Three emptinesses, three answers: a filter that matched
                       nothing · a warehouse nobody has moved anything into ·
                       a branch carrying no materials at all. -->
                  <div class="st-empty !border-0 !py-8">
                    <template v-if="stockEmptyState === 'filtered'">
                      <h3>{{ $t('inventory.stock.emptyFilteredTitle') }}</h3>
                      <p>{{ $t('inventory.stock.emptyFilteredBody') }}</p>
                    </template>
                    <template v-else-if="stockEmptyState === 'moved'">
                      <h3>{{ $t('inventory.stock.emptyMovedTitle') }}</h3>
                      <p>{{ $t('inventory.stock.emptyMovedBody') }}</p>
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
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="invoice in workshop.supplierInvoices"
                :key="invoice.id"
                class="row-clickable"
              >
                <td class="nm">
                  <!-- The number is the row's control: it opens the document,
                       which is the only thing anyone comes to this row to do.
                       A real link, so middle-click and Cmd-click work. -->
                  <RouterLink
                    :to="rolePath(`/workshop/inventory/invoices/${invoice.id}`)"
                    class="row-open row-open-text"
                    :aria-label="$t('inventory.invoices.openAria', { invoice: invoice.invoice_no })"
                  >
                    {{ invoice.invoice_no }}
                  </RouterLink>
                </td>
                <td>{{ invoice.supplier_name ?? '—' }}</td>
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
                <!-- One number: with the document-level skidka gone from the
                     UI the total IS the line sum. -->
                <td class="amt">{{ formatTiyin(invoice.total_tiyin) }}</td>
                <td>
                  <span v-if="invoice.status === 'voided'" class="pill p-bad">
                    <span class="pd"></span>{{ $t('inventory.invoices.voided') }}
                  </span>
                  <template v-else>
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
                  </template>
                </td>
              </tr>
              <tr v-if="workshop.supplierInvoices.length === 0">
                <td colspan="6">
                  <div class="st-empty !border-0 !py-8">
                    <h3>
                      {{
                        invoiceFiltered
                          ? $t('inventory.invoices.emptyFilteredTitle')
                          : $t('inventory.invoices.emptyTitle')
                      }}
                    </h3>
                    <p>
                      {{
                        invoiceFiltered
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
        <div
          v-if="workshop.supplierInvoicesHasMore"
          class="flex justify-center border-t border-hairline p-4"
        >
          <button
            class="mp-button mp-button-outline min-h-10 px-4 text-sm"
            type="button"
            :disabled="workshop.inventoryLoading"
            @click="loadMoreInvoices"
          >
            {{
              workshop.inventoryLoading
                ? $t('inventory.invoices.loading')
                : $t('inventory.invoices.loadMore')
            }}
          </button>
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
                <th>{{ $t('inventory.tx.columnInvoice') }}</th>
                <th>{{ $t('inventory.tx.columnSupplier') }}</th>
                <th>{{ $t('inventory.tx.columnActor') }}</th>
                <th>{{ $t('inventory.tx.columnNote') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in workshop.stockTransactions" :key="tx.id">
                <td class="num text-ink-muted">{{ formatDateTime(tx.created_at) }}</td>
                <td>
                  <span :class="transactionTypePill(tx.type)">
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
                  <!-- A movement's document, named rather than numbered: the
                       ledger row links straight to the faktura page. -->
                  <RouterLink
                    v-if="tx.invoice_id && tx.invoice_no"
                    :to="rolePath(`/workshop/inventory/invoices/${tx.invoice_id}`)"
                    class="id no-underline"
                    :aria-label="$t('inventory.tx.openInvoiceAria', { invoice: tx.invoice_no })"
                  >
                    {{ tx.invoice_no }}
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
                <td colspan="12">
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
