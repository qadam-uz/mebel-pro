<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { INVENTORY_TX_PAGE_LIMIT } from '@/shared/app/constants'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { useRolePath } from '@/shared/app/paths'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { branchOptions } from '@/shared/app/workshopUi'
import AppTabs from '@/shared/components/AppTabs.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatStockQuantity, parseDisplayQuantity } from '@/shared/formatters'
import { useFilesStore } from '@/shared/stores/files'
import { useWorkshopStore, type StockItem, type Supplier } from '@/shared/stores/workshop'

const rolePath = useRolePath()
const permissions = useWorkshopPermissions()
const workshop = useWorkshopStore()
const files = useFilesStore()
const toast = useToast()
const route = useRoute()
const activeTab = ref<'stock' | 'tx' | 'suppliers'>('stock')
const inventoryTabs: ChoiceOption[] = [
  { value: 'stock', label: 'Joriy ombor' },
  { value: 'tx', label: 'Tranzaksiyalar' },
  { value: 'suppliers', label: 'Yetkazib beruvchilar' },
]
const selectedBranchId = ref('')
const search = ref('')
const lowOnly = ref(false)
const txDateFrom = ref(dateOffsetIso(-30))
const txDateTo = ref(dateOffsetIso(0))
const movementSaving = ref(false)
const supplierSaving = ref(false)
const movementError = ref<string | null>(null)
const supplierError = ref<string | null>(null)
const stockInMaterialError = ref<string | null>(null)
const stockInSupplierError = ref<string | null>(null)
const stockInReceiptError = ref<string | null>(null)
const adjustmentMaterialError = ref<string | null>(null)
const editingSupplierId = ref<string | null>(null)
const stockLoadedKey = ref<string | null>(null)
const transactionsLoadedKey = ref<string | null>(null)
const suppliersLoadedBranch = ref<string | null>(null)
let stockSearchTimer: number | undefined

const stockInForm = reactive({
  materialId: null as string | null,
  quantity: '',
  supplierId: null as string | null,
  inlineSupplierName: '',
  receiptFileId: '',
  note: '',
})
const adjustmentForm = reactive({
  materialId: null as string | null,
  quantity: '',
  note: '',
})
const supplierForm = reactive({
  name: '',
  phone: '',
  note: '',
})

const canUseInventory = computed(() => permissions.can(p.manageInventory))
const accessibleBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, [p.manageInventory]),
)
const branchFilterOptions = computed(() =>
  branchOptions(
    accessibleBranches.value,
    permissions.isOwner.value ? 'Barcha filiallar' : 'Mening filiallarim',
  ),
)
const selectedBranch = computed(
  () => accessibleBranches.value.find((branch) => branch.id === selectedBranchId.value) ?? null,
)
const displayUnitByMaterialId = computed(
  () => new Map(workshop.stockItems.map((item) => [item.material_id, item.display_unit])),
)
const stockOptions = computed(() =>
  workshop.stockItems.map((item) => ({
    value: item.material_id,
    label: item.material.name,
    meta: `${formatStockQuantity(item.on_hand, item.display_unit)} mavjud`,
  })),
)
const activeSupplierOptions = computed(() => [
  { value: 'inline', label: 'Yangi yetkazib beruvchi', meta: 'kirim bilan yaratiladi' },
  ...workshop.suppliers
    .filter((supplier) => supplier.status === 'active')
    .map((supplier) => ({
      value: supplier.id,
      label: supplier.name,
      meta: supplier.phone ?? 'faol',
    })),
])
const selectedStockInItem = computed(() => stockItemByMaterial(stockInForm.materialId))
const selectedAdjustmentItem = computed(() => stockItemByMaterial(adjustmentForm.materialId))
const activeListEmpty = computed(() => {
  if (activeTab.value === 'stock') return workshop.stockItems.length === 0
  if (activeTab.value === 'tx') return workshop.stockTransactions.length === 0
  return workshop.suppliers.length === 0
})

function dateOffsetIso(offsetDays: number) {
  const value = new Date()
  value.setDate(value.getDate() + offsetDays)
  return value.toISOString().slice(0, 10)
}

function applyContextBranch() {
  const contextBranchId = workshop.selectedBranchContext
  if (!contextBranchId) return
  if (!accessibleBranches.value.some((branch) => branch.id === contextBranchId)) return
  selectedBranchId.value = contextBranchId
}

function stockItemByMaterial(materialId: string | null): StockItem | null {
  return workshop.stockItems.find((item) => item.material_id === materialId) ?? null
}

function materialMeta(item: (typeof workshop.stockItems)[number]) {
  if (item.kind === 'edge') return `${item.material.thickness_mm} mm · krom (metr)`
  return `${item.material.thickness_mm} mm · ${item.material.panel_length_mm}x${item.material.panel_width_mm}`
}

function transactionDisplayUnit(materialId: string) {
  return displayUnitByMaterialId.value.get(materialId) ?? 'piece'
}

function formatTransactionQuantity(quantity: number, materialId: string) {
  const prefix = quantity > 0 ? '+' : ''
  return `${prefix}${formatStockQuantity(quantity, transactionDisplayUnit(materialId))}`
}

function transactionActorName(tx: (typeof workshop.stockTransactions)[number]) {
  if (tx.actor_name) return tx.actor_name
  if (tx.actor_user_id) return `User ${tx.actor_user_id.slice(0, 8)}`
  return 'System'
}

function transactionFilterKey() {
  return [selectedBranchId.value, txDateFrom.value || 'open', txDateTo.value || 'open'].join(':')
}

function stockFilterKey() {
  return [selectedBranchId.value, search.value.trim(), lowOnly.value ? 'low' : 'all'].join(':')
}

async function refreshActiveInventoryTab(options: { force?: boolean; offset?: number } = {}) {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
  const branchId = selectedBranchId.value
  const offset = options.offset ?? 0
  const txKey = transactionFilterKey()
  const stockKey = stockFilterKey()
  if (!options.force && offset === 0) {
    if (activeTab.value === 'stock' && stockLoadedKey.value === stockKey) return
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
    if (activeTab.value === 'tx') {
      await workshop.loadStockTransactions(branchId, {
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
  } catch (errorValue) {
    workshop.inventoryError = 'inventory_load_failed'
    workshop.inventoryTraceId = apiTraceId(errorValue)
  } finally {
    workshop.inventoryLoading = false
  }
}

async function loadMoreTransactions() {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
  activeTab.value = 'tx'
  await refreshActiveInventoryTab({ force: true, offset: workshop.stockTransactions.length })
}

async function ensureSuppliersLoaded() {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
  if (suppliersLoadedBranch.value === selectedBranchId.value) return
  try {
    await workshop.loadSuppliers(selectedBranchId.value)
    suppliersLoadedBranch.value = selectedBranchId.value
  } catch {
    supplierError.value = 'suppliers_load_failed'
  }
}

function validStockInQuantity(item: StockItem | null) {
  const quantity = parseDisplayQuantity(stockInForm.quantity, item?.display_unit ?? 'piece')
  return Number.isFinite(quantity) && quantity > 0 ? quantity : null
}

function validAdjustmentQuantity(item: StockItem | null) {
  const quantity = parseDisplayQuantity(adjustmentForm.quantity, item?.display_unit ?? 'piece')
  return Number.isFinite(quantity) && quantity !== 0 ? quantity : null
}

async function recordStockIn() {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
  movementSaving.value = true
  movementError.value = null
  stockInMaterialError.value = null
  stockInSupplierError.value = null
  const item = selectedStockInItem.value
  const quantity = validStockInQuantity(item)
  if (!item || quantity === null) {
    stockInMaterialError.value = "Material va musbat miqdorni to'g'ri kiriting."
    movementSaving.value = false
    return
  }
  if (stockInForm.supplierId === 'inline' && !stockInForm.inlineSupplierName.trim()) {
    stockInSupplierError.value = 'Yangi yetkazib beruvchi nomini kiriting.'
    movementSaving.value = false
    return
  }
  try {
    await workshop.recordStockIn(selectedBranchId.value, {
      material_id: item.material_id,
      quantity,
      supplier_id:
        stockInForm.supplierId && stockInForm.supplierId !== 'inline'
          ? stockInForm.supplierId
          : null,
      supplier:
        stockInForm.supplierId === 'inline'
          ? { name: stockInForm.inlineSupplierName.trim() }
          : null,
      receipt_file_id: stockInForm.receiptFileId || null,
      note: stockInForm.note || null,
    })
    resetStockInForm()
    toast.success('Kirim yozildi.')
  } catch {
    movementError.value = 'stock_in_failed'
  } finally {
    movementSaving.value = false
  }
}

async function recordAdjustment() {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
  movementSaving.value = true
  movementError.value = null
  adjustmentMaterialError.value = null
  const item = selectedAdjustmentItem.value
  const quantity = validAdjustmentQuantity(item)
  if (!item || quantity === null) {
    adjustmentMaterialError.value = "Material va nol bo'lmagan miqdorni to'g'ri kiriting."
    movementSaving.value = false
    return
  }
  try {
    await workshop.recordAdjustment(selectedBranchId.value, {
      material_id: item.material_id,
      quantity,
      note: adjustmentForm.note,
    })
    resetAdjustmentForm()
    toast.success('Ombor tuzatishi yozildi.')
  } catch {
    movementError.value = 'adjustment_failed'
  } finally {
    movementSaving.value = false
  }
}

async function saveSupplier() {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
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
    toast.success(wasEditing ? 'Yetkazib beruvchi saqlandi.' : "Yetkazib beruvchi qo'shildi.")
  } catch {
    supplierError.value = 'supplier_save_failed'
  } finally {
    supplierSaving.value = false
  }
}

async function toggleSupplierStatus(supplier: Supplier) {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
  supplierSaving.value = true
  supplierError.value = null
  try {
    await workshop.setSupplierStatus(
      selectedBranchId.value,
      supplier.id,
      supplier.status === 'active' ? 'inactive' : 'active',
    )
    toast.success("Yetkazib beruvchi holati o'zgartirildi.")
  } catch {
    supplierError.value = 'supplier_status_failed'
  } finally {
    supplierSaving.value = false
  }
}

async function onReceiptFile(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement) || !target.files?.[0]) return
  stockInReceiptError.value = null
  try {
    const uploaded = await files.upload(target.files[0])
    stockInForm.receiptFileId = uploaded.id
    toast.success('Chek biriktirildi.')
  } catch {
    stockInReceiptError.value = 'Chek yuklanmadi. Qayta urinib ko`ring.'
  }
  target.value = ''
}

function editSupplier(supplier: Supplier) {
  activeTab.value = 'suppliers'
  editingSupplierId.value = supplier.id
  supplierForm.name = supplier.name
  supplierForm.phone = supplier.phone ?? ''
  supplierForm.note = supplier.note ?? ''
}

function resetStockInForm() {
  stockInForm.materialId = null
  stockInForm.quantity = ''
  stockInForm.supplierId = null
  stockInForm.inlineSupplierName = ''
  stockInForm.receiptFileId = ''
  stockInForm.note = ''
  stockInMaterialError.value = null
  stockInSupplierError.value = null
  stockInReceiptError.value = null
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

watch(selectedBranchId, () => {
  if (selectedBranchId.value && selectedBranchId.value !== 'all') {
    workshop.setSelectedBranchContext(selectedBranchId.value)
  }
  stockLoadedKey.value = null
  transactionsLoadedKey.value = null
  suppliersLoadedBranch.value = null
  workshop.clearInventory()
  void refreshActiveInventoryTab({ force: true })
})

watch(activeTab, () => {
  void refreshActiveInventoryTab()
})

watch(
  () => workshop.selectedBranchContext,
  () => {
    applyContextBranch()
  },
)

watch(
  () => route.query.search,
  () => {
    applyRouteSearch()
  },
)

watch([txDateFrom, txDateTo], () => {
  if (activeTab.value === 'tx') void refreshActiveInventoryTab({ force: true })
})

watch([search, lowOnly], () => {
  window.clearTimeout(stockSearchTimer)
  stockSearchTimer = window.setTimeout(() => {
    if (activeTab.value === 'stock') void refreshActiveInventoryTab({ force: true })
  }, 250)
})

onMounted(async () => {
  applyRouteSearch()
  await workshop.loadBranchContext().catch(() => undefined)
  selectedBranchId.value = accessibleBranches.value[0]?.id ?? ''
  applyContextBranch()
  await refreshActiveInventoryTab({ force: true })
})

onBeforeUnmount(() => {
  window.clearTimeout(stockSearchTimer)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Ombor</h1>
        <p class="sub">Filiallarda mavjud panellar va krom materiallari.</p>
      </div>
      <div class="tools">
        <RouterLink
          v-if="selectedBranch"
          :to="rolePath(`/workshop/branches/${selectedBranch.id}`)"
          class="mp-button mp-button-primary"
        >
          Filial omborini ochish
        </RouterLink>
      </div>
    </div>

    <div v-if="!canUseInventory" class="st-empty">
      <h3>Ombor bo'limiga ruxsatingiz yo'q</h3>
      <p>Ustaxona egasiga murojaat qiling.</p>
    </div>

    <div v-else-if="accessibleBranches.length === 0" class="st-empty">
      <h3>Filial biriktirilmagan</h3>
      <p>Filial biriktirilgach, ombor qoldiqlari shu yerda ko'rinadi.</p>
    </div>

    <template v-else>
      <AppTabs
        v-model="activeTab"
        id-prefix="workshop-inventory"
        label="Ombor bo'limlari"
        :tabs="inventoryTabs"
      />

      <div class="filters">
        <label class="grid gap-1">
          <span class="filter-label">Qidirish</span>
          <input v-model="search" class="mp-input min-w-64" placeholder="Material qidirish..." />
        </label>
        <ProjectDropdown v-model="selectedBranchId" label="Filial" :options="branchFilterOptions" />
        <label
          v-if="activeTab === 'stock'"
          class="flex min-h-10 items-center gap-2 text-sm font-bold text-ink"
        >
          <input v-model="lowOnly" type="checkbox" class="size-4 accent-[var(--color-accent)]" />
          Faqat past zaxiralar
        </label>
        <label v-if="activeTab === 'tx'" class="grid gap-1">
          <span class="filter-label">Boshlanish</span>
          <input v-model="txDateFrom" class="mp-input" type="date" />
        </label>
        <label v-if="activeTab === 'tx'" class="grid gap-1">
          <span class="filter-label">Tugash</span>
          <input v-model="txDateTo" class="mp-input" type="date" />
        </label>
      </div>

      <div
        v-if="activeTab === 'stock'"
        id="workshop-inventory-stock-panel"
        class="mb-4 grid gap-4 xl:grid-cols-2"
        role="tabpanel"
        aria-labelledby="workshop-inventory-stock-tab"
        tabindex="0"
      >
        <section class="card p-4">
          <h2 class="mb-3 text-base font-extrabold text-ink">Kirim yozish</h2>
          <form class="grid gap-3" @submit.prevent="recordStockIn">
            <SearchCombobox
              v-model="stockInForm.materialId"
              label="Material"
              :options="stockOptions"
              :error="stockInMaterialError"
            />
            <label class="field">
              <span>Miqdor {{ selectedStockInItem?.display_unit ?? '' }}</span>
              <input v-model="stockInForm.quantity" class="mp-input" inputmode="decimal" required />
            </label>
            <FormSelect
              v-model="stockInForm.supplierId"
              label="Yetkazib beruvchi"
              :options="activeSupplierOptions"
              :error="stockInSupplierError"
              @focusin="ensureSuppliersLoaded"
            />
            <label v-if="stockInForm.supplierId === 'inline'" class="field">
              <span>Yangi yetkazib beruvchi nomi</span>
              <input v-model="stockInForm.inlineSupplierName" class="mp-input" required />
            </label>
            <label class="field">
              <span>Chek</span>
              <input
                type="file"
                class="mp-input"
                accept="image/png,image/jpeg,image/webp,application/pdf"
                :disabled="files.uploading"
                @change="onReceiptFile"
              />
              <small v-if="stockInForm.receiptFileId" class="text-ink-soft">
                chek {{ stockInForm.receiptFileId.slice(0, 8) }}
              </small>
              <small v-if="stockInReceiptError" class="font-bold text-danger">
                {{ stockInReceiptError }}
              </small>
            </label>
            <label class="field">
              <span>Izoh</span>
              <input v-model="stockInForm.note" class="mp-input" />
            </label>
            <button type="submit" class="mp-button mp-button-primary" :disabled="movementSaving">
              {{ movementSaving ? 'Yozilmoqda' : 'Kirim yozish' }}
            </button>
          </form>
        </section>

        <section class="card p-4">
          <h2 class="mb-3 text-base font-extrabold text-ink">Tuzatish yozish</h2>
          <form class="grid gap-3" @submit.prevent="recordAdjustment">
            <SearchCombobox
              v-model="adjustmentForm.materialId"
              label="Material"
              :options="stockOptions"
              :error="adjustmentMaterialError"
            />
            <label class="field">
              <span>Belgili miqdor {{ selectedAdjustmentItem?.display_unit ?? '' }}</span>
              <input
                v-model="adjustmentForm.quantity"
                class="mp-input"
                inputmode="decimal"
                required
              />
            </label>
            <label class="field">
              <span>Izoh</span>
              <input v-model="adjustmentForm.note" class="mp-input" required />
            </label>
            <button type="submit" class="mp-button mp-button-primary" :disabled="movementSaving">
              {{ movementSaving ? 'Yozilmoqda' : 'Tuzatish yozish' }}
            </button>
          </form>
        </section>
      </div>

      <div v-if="movementError" class="banner danger mb-4">
        <div class="grow">Ombor harakati yozilmadi.</div>
      </div>

      <div v-if="workshop.inventoryLoading && activeListEmpty" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </div>

      <div v-else-if="workshop.inventoryError && activeListEmpty" class="st-error">
        <h3>Ma'lumotni yuklab bo'lmadi</h3>
        <p>trace_id: {{ workshop.inventoryTraceId ?? 'unavailable' }}</p>
      </div>

      <section v-else-if="activeTab === 'stock'" class="card">
        <div v-if="workshop.inventoryError" class="banner danger m-4">
          <div class="grow">
            Ma'lumotni yuklashda xato · trace_id:
            {{ workshop.inventoryTraceId ?? 'unavailable' }}
          </div>
        </div>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Material</th>
                <th>Filial</th>
                <th class="right">Mavjud</th>
                <th class="right">Min</th>
                <th>Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in workshop.stockItems" :key="item.id">
                <td>
                  <div class="flex min-w-0 items-center gap-3">
                    <span class="sw" :class="materialSwatchClass(item.material)"></span>
                    <span class="min-w-0">
                      <span class="nm">{{ item.material.name }}</span>
                      <small class="block truncate text-ink-muted">{{ materialMeta(item) }}</small>
                    </span>
                  </div>
                </td>
                <td>{{ selectedBranch?.name ?? '—' }}</td>
                <td class="amt" :class="{ 'warn-text': item.is_low_stock }">
                  {{ formatStockQuantity(item.on_hand, item.display_unit) }}
                  <small v-if="item.is_low_stock" class="block text-[11px] font-extrabold">
                    Past zaxira
                  </small>
                </td>
                <td class="amt muted">
                  {{ formatStockQuantity(item.min_stock, item.display_unit) }}
                </td>
                <td>
                  <span :class="item.is_low_stock ? 'pill p-warn' : 'pill p-ok'">
                    <span class="pd"></span>{{ item.is_low_stock ? 'Past' : 'OK' }}
                  </span>
                </td>
                <td class="right">
                  <RouterLink
                    v-if="selectedBranch"
                    :to="rolePath(`/workshop/branches/${selectedBranch.id}`)"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  >
                    Ombor kartasi
                  </RouterLink>
                </td>
              </tr>
              <tr v-if="workshop.stockItems.length === 0">
                <td colspan="6">
                  <div class="st-empty !border-0 !py-8">
                    <h3>Bu filialga material qo'shilmagan</h3>
                    <p>Katalogdan material qo'shing.</p>
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
            Tranzaksiyalarni yuklashda xato · trace_id:
            {{ workshop.inventoryTraceId ?? 'unavailable' }}
          </div>
        </div>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Vaqt</th>
                <th>Filial</th>
                <th>Turi</th>
                <th>Material</th>
                <th class="right">Miqdor</th>
                <th>Keyin</th>
                <th>Buyurtma</th>
                <th>Yetkazib beruvchi</th>
                <th>Kim qildi</th>
                <th>Izoh</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in workshop.stockTransactions" :key="tx.id">
                <td class="num text-ink-muted">{{ formatDate(tx.created_at) }}</td>
                <td>{{ selectedBranch?.name ?? '—' }}</td>
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
                    <span class="pd"></span>{{ tx.type }}
                  </span>
                </td>
                <td class="nm">{{ tx.material_name }}</td>
                <td class="amt" :class="tx.quantity >= 0 ? 'success-text' : 'danger-text'">
                  {{ formatTransactionQuantity(tx.quantity, tx.material_id) }}
                </td>
                <td class="num muted">
                  {{
                    formatStockQuantity(tx.balance_after, transactionDisplayUnit(tx.material_id))
                  }}
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
                <td colspan="10">
                  <div class="st-empty !border-0 !py-8"><h3>Tranzaksiya yo'q</h3></div>
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
            {{ workshop.inventoryLoading ? 'Yuklanmoqda' : "Yana ko'rsatish" }}
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
        <section class="card mb-4 p-4">
          <h2 class="mb-3 text-base font-extrabold text-ink">
            {{
              editingSupplierId ? 'Yetkazib beruvchini tahrirlash' : 'Yetkazib beruvchi yaratish'
            }}
          </h2>
          <form class="grid gap-3 md:grid-cols-3" @submit.prevent="saveSupplier">
            <label class="field">
              <span>Nom</span>
              <input v-model="supplierForm.name" class="mp-input" required />
            </label>
            <label class="field">
              <span>Telefon</span>
              <input v-model="supplierForm.phone" class="mp-input" inputmode="tel" />
            </label>
            <label class="field">
              <span>Izoh</span>
              <input v-model="supplierForm.note" class="mp-input" />
            </label>
            <div class="flex items-end gap-2 md:col-span-3">
              <button type="submit" class="mp-button mp-button-primary" :disabled="supplierSaving">
                {{ supplierSaving ? 'Saqlanmoqda' : editingSupplierId ? 'Saqlash' : 'Yaratish' }}
              </button>
              <button
                v-if="editingSupplierId"
                type="button"
                class="mp-button mp-button-outline"
                @click="resetSupplierForm"
              >
                Bekor
              </button>
            </div>
          </form>
          <p
            v-if="supplierError"
            class="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            Yetkazib beruvchi saqlanmadi.
          </p>
        </section>

        <section class="card">
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>Nomi</th>
                  <th>Telefon</th>
                  <th>Izoh</th>
                  <th>Holat</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="supplier in workshop.suppliers" :key="supplier.id">
                  <td class="nm">{{ supplier.name }}</td>
                  <td class="num">{{ supplier.phone ?? '—' }}</td>
                  <td>{{ supplier.note ?? '—' }}</td>
                  <td>
                    <span :class="supplier.status === 'active' ? 'pill p-ok' : 'pill p-dn'">
                      <span class="pd"></span
                      >{{ supplier.status === 'active' ? 'Faol' : 'Faol emas' }}
                    </span>
                  </td>
                  <td class="right">
                    <button
                      type="button"
                      class="mp-button mp-button-outline mr-2 min-h-8 px-2 text-xs"
                      :disabled="supplierSaving"
                      @click="editSupplier(supplier)"
                    >
                      Tahrir
                    </button>
                    <button
                      type="button"
                      class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                      :disabled="supplierSaving"
                      @click="toggleSupplierStatus(supplier)"
                    >
                      {{ supplier.status === 'active' ? "O'chirish" : 'Faollashtirish' }}
                    </button>
                  </td>
                </tr>
                <tr v-if="workshop.suppliers.length === 0">
                  <td colspan="5">
                    <div class="st-empty !border-0 !py-8"><h3>Yetkazib beruvchi yo'q</h3></div>
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
