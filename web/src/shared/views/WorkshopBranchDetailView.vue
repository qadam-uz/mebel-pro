<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import FilterDropdown from '@/shared/components/FilterDropdown.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import {
  formatDate,
  formatStockQuantity,
  formatTiyin,
  parseDisplayQuantity,
} from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useFilesStore } from '@/shared/stores/files'
import {
  useWorkshopStore,
  type BranchMaterial,
  type StockItem,
  type Supplier,
} from '@/shared/stores/workshop'

const route = useRoute()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const files = useFilesStore()
const activeTab = ref<'materials' | 'inventory' | 'settings'>('materials')
const branchId = computed(() => String(route.params.branch_id ?? ''))
const loading = ref(false)
const pageError = ref<string | null>(null)
const pageTraceId = ref<string | null>(null)
const materialSaving = ref(false)
const movementSaving = ref(false)
const supplierSaving = ref(false)
const settingsSaving = ref(false)
const materialError = ref<string | null>(null)
const movementError = ref<string | null>(null)
const supplierError = ref<string | null>(null)
const settingsError = ref<string | null>(null)
const materialFieldError = ref<string | null>(null)
const stockInMaterialError = ref<string | null>(null)
const stockInSupplierError = ref<string | null>(null)
const adjustmentMaterialError = ref<string | null>(null)
const branchMaterialSearch = ref('')
const branchMaterialStatus = ref<string | null>('active')
const stockSearch = ref('')
const supplierStatus = ref<string | null>('active')
const editingBranchMaterialId = ref<string | null>(null)
const editingSupplierId = ref<string | null>(null)

const materialForm = reactive({
  materialId: null as string | null,
  priceTiyin: '0',
  minStock: '0',
})
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
const branchForm = reactive({
  name: '',
  address: '',
  phone: '',
  latitude: '',
  longitude: '',
})
const pricingForm = reactive({
  cuttingRateTiyin: '',
  edgeBandingRateTiyin: '',
})
const statusForm = reactive({
  status: 'active',
  reason: '',
  confirmed: false,
})

const contextBranch = computed(() =>
  workshop.branches.find((branch) => branch.id === branchId.value),
)
const canManageCatalog = computed(
  () => auth.me?.is_owner || contextBranch.value?.permissions.includes('manage_catalog') === true,
)
const canManageInventory = computed(
  () => auth.me?.is_owner || contextBranch.value?.permissions.includes('manage_inventory') === true,
)
const canManageSettings = computed(() => auth.me?.is_owner === true)
const availableCatalogOptions = computed(() =>
  workshop.catalogOptions
    .filter((option) => !option.already_selected)
    .map((option) => ({
      value: option.material.id,
      label: option.material.name,
      meta: `${option.material.manufacturer_name} · ${option.material.kind}`,
    })),
)
const selectedCatalogMaterial = computed(
  () =>
    workshop.catalogOptions.find((option) => option.material.id === materialForm.materialId)
      ?.material ?? null,
)
const stockOptions = computed(() =>
  workshop.stockItems.map((item) => ({
    value: item.material_id,
    label: item.material.name,
    meta: `${formatStockQuantity(item.on_hand, item.display_unit)} on hand`,
  })),
)
const activeSupplierOptions = computed(() => [
  { value: 'inline', label: 'New supplier label', meta: 'create with stock-in' },
  ...workshop.suppliers
    .filter((supplier) => supplier.status === 'active')
    .map((supplier) => ({
      value: supplier.id,
      label: supplier.name,
      meta: supplier.phone ?? 'active',
    })),
])
const selectedStockInItem = computed(() => stockItemByMaterial(stockInForm.materialId))
const selectedAdjustmentItem = computed(() => stockItemByMaterial(adjustmentForm.materialId))
const materialMinStockUnit = computed(() =>
  selectedCatalogMaterial.value?.kind === 'edge' ? 'm' : 'pcs',
)
const statusOptions = [
  { value: 'active', label: 'Active', meta: 'visible to clients' },
  { value: 'temporarily_closed', label: 'Temporarily closed', meta: 'visible with reason' },
  { value: 'inactive', label: 'Inactive', meta: 'hidden from clients' },
]
const materialStatusOptions = [
  { value: 'all', label: 'Any status' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]
const supplierStatusOptions = [
  { value: 'all', label: 'Any status' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]
const tabs = [
  { key: 'materials', label: 'Materials' },
  { key: 'inventory', label: 'Inventory' },
  { key: 'settings', label: 'Settings' },
] as const
const visibleTabs = computed(() =>
  tabs.filter((tab) => {
    if (tab.key === 'materials') return canManageCatalog.value
    if (tab.key === 'inventory') return canManageInventory.value
    return canManageSettings.value
  }),
)

function stockItemByMaterial(materialId: string | null): StockItem | null {
  return workshop.stockItems.find((item) => item.material_id === materialId) ?? null
}

function statusFilter(value: string | null) {
  return value === 'all' ? null : value
}

function selectFirstVisibleTab() {
  if (visibleTabs.value.some((tab) => tab.key === activeTab.value)) return
  activeTab.value = visibleTabs.value[0]?.key ?? 'materials'
}

async function refreshBranch() {
  if (!branchId.value) return
  loading.value = true
  pageError.value = null
  pageTraceId.value = null
  try {
    await workshop.loadBranchContext()
    await workshop.loadBranch(branchId.value)
    syncBranchForms()
    selectFirstVisibleTab()
    const jobs: Promise<unknown>[] = []
    if (canManageCatalog.value) {
      jobs.push(
        workshop.loadBranchMaterials(branchId.value, {
          search: branchMaterialSearch.value,
          status: statusFilter(branchMaterialStatus.value) as 'active' | 'inactive' | null,
        }),
      )
      jobs.push(workshop.loadCatalogOptions(branchId.value))
    }
    if (canManageInventory.value) {
      jobs.push(workshop.loadInventory(branchId.value))
    }
    await Promise.all(jobs)
  } catch {
    pageError.value = 'branch_detail_load_failed'
    pageTraceId.value = workshop.traceId ?? workshop.setupTraceId
  } finally {
    loading.value = false
  }
}

async function refreshMaterials() {
  await Promise.all([
    workshop.loadBranchMaterials(branchId.value, {
      search: branchMaterialSearch.value,
      status: statusFilter(branchMaterialStatus.value) as 'active' | 'inactive' | null,
    }),
    workshop.loadCatalogOptions(branchId.value),
  ])
}

async function refreshInventory() {
  await Promise.all([
    workshop.loadStock(branchId.value, { search: stockSearch.value }),
    workshop.loadStockTransactions(branchId.value),
    workshop.loadSuppliers(
      branchId.value,
      statusFilter(supplierStatus.value) as 'active' | 'inactive' | null,
    ),
  ])
}

async function saveBranchMaterial() {
  materialSaving.value = true
  materialError.value = null
  materialFieldError.value = null
  try {
    if (!editingBranchMaterialId.value && !materialForm.materialId) {
      materialFieldError.value = 'Choose a material'
      return
    }
    const material =
      selectedCatalogMaterial.value ??
      workshop.branchMaterials.find((row) => row.id === editingBranchMaterialId.value)?.material
    const minStock = parseDisplayQuantity(
      materialForm.minStock,
      material?.kind === 'edge' ? 'm' : 'pcs',
    )
    const payload = {
      price_tiyin: Number(materialForm.priceTiyin),
      min_stock: minStock,
    }
    if (editingBranchMaterialId.value) {
      await workshop.updateBranchMaterial(branchId.value, editingBranchMaterialId.value, payload)
    } else {
      await workshop.addBranchMaterial(branchId.value, {
        material_id: materialForm.materialId,
        ...payload,
      })
    }
    resetMaterialForm()
    await refreshMaterials()
  } catch {
    materialError.value = 'branch_material_save_failed'
  } finally {
    materialSaving.value = false
  }
}

async function recordStockIn() {
  movementSaving.value = true
  movementError.value = null
  stockInMaterialError.value = null
  stockInSupplierError.value = null
  try {
    if (!stockInForm.materialId) {
      stockInMaterialError.value = 'Choose a material'
      return
    }
    if (!stockInForm.supplierId) {
      stockInSupplierError.value = 'Choose a supplier'
      return
    }
    if (stockInForm.supplierId === 'inline' && stockInForm.inlineSupplierName.trim() === '') {
      stockInSupplierError.value = 'Enter the new supplier name'
      return
    }
    const item = selectedStockInItem.value
    const quantity = parseDisplayQuantity(stockInForm.quantity, item?.display_unit ?? 'pcs')
    await workshop.recordStockIn(branchId.value, {
      material_id: stockInForm.materialId,
      quantity,
      supplier_id:
        stockInForm.supplierId && stockInForm.supplierId !== 'inline'
          ? stockInForm.supplierId
          : null,
      supplier:
        stockInForm.supplierId === 'inline'
          ? { name: stockInForm.inlineSupplierName, phone: null, note: null }
          : null,
      receipt_file_id: stockInForm.receiptFileId || null,
      note: stockInForm.note || null,
    })
    stockInForm.quantity = ''
    stockInForm.note = ''
    stockInForm.receiptFileId = ''
    stockInForm.inlineSupplierName = ''
    await refreshInventory()
  } catch {
    movementError.value = 'stock_in_failed'
  } finally {
    movementSaving.value = false
  }
}

async function recordAdjustment() {
  movementSaving.value = true
  movementError.value = null
  adjustmentMaterialError.value = null
  try {
    if (!adjustmentForm.materialId) {
      adjustmentMaterialError.value = 'Choose a material'
      return
    }
    const item = selectedAdjustmentItem.value
    const quantity = parseDisplayQuantity(adjustmentForm.quantity, item?.display_unit ?? 'pcs')
    await workshop.recordAdjustment(branchId.value, {
      material_id: adjustmentForm.materialId,
      quantity,
      note: adjustmentForm.note,
    })
    adjustmentForm.quantity = ''
    adjustmentForm.note = ''
    await refreshInventory()
  } catch {
    movementError.value = 'adjustment_failed'
  } finally {
    movementSaving.value = false
  }
}

async function saveSupplier() {
  supplierSaving.value = true
  supplierError.value = null
  try {
    const payload = {
      name: supplierForm.name,
      phone: supplierForm.phone || null,
      note: supplierForm.note || null,
    }
    if (editingSupplierId.value) {
      await workshop.updateSupplier(branchId.value, editingSupplierId.value, payload)
    } else {
      await workshop.createSupplier(branchId.value, payload)
    }
    resetSupplierForm()
  } catch {
    supplierError.value = 'supplier_save_failed'
  } finally {
    supplierSaving.value = false
  }
}

async function saveBranchSettings() {
  settingsSaving.value = true
  settingsError.value = null
  try {
    await workshop.updateBranch(branchId.value, {
      name: branchForm.name,
      address: branchForm.address,
      phone: branchForm.phone,
      latitude: branchForm.latitude,
      longitude: branchForm.longitude,
    })
    await workshop.updateBranchPricing(branchId.value, {
      cutting_rate_tiyin: pricingForm.cuttingRateTiyin
        ? Number(pricingForm.cuttingRateTiyin)
        : null,
      edge_banding_rate_tiyin: pricingForm.edgeBandingRateTiyin
        ? Number(pricingForm.edgeBandingRateTiyin)
        : null,
    })
  } catch {
    settingsError.value = 'branch_settings_save_failed'
  } finally {
    settingsSaving.value = false
  }
}

async function changeBranchStatus() {
  settingsSaving.value = true
  settingsError.value = null
  try {
    await workshop.setBranchStatus(branchId.value, {
      status: statusForm.status,
      reason: statusForm.status === 'active' ? null : statusForm.reason,
    })
    statusForm.confirmed = false
    syncBranchForms()
  } catch {
    settingsError.value = 'branch_status_failed'
  } finally {
    settingsSaving.value = false
  }
}

async function onReceiptFile(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement) || !target.files?.[0]) return
  const uploaded = await files.upload(target.files[0])
  stockInForm.receiptFileId = uploaded.id
  target.value = ''
}

function editBranchMaterial(row: BranchMaterial) {
  editingBranchMaterialId.value = row.id
  materialForm.materialId = row.material_id
  materialForm.priceTiyin = String(row.price_tiyin)
  materialForm.minStock =
    row.material.kind === 'edge' ? String(row.min_stock / 1000) : String(row.min_stock)
}

function resetMaterialForm() {
  editingBranchMaterialId.value = null
  materialForm.materialId = null
  materialForm.priceTiyin = '0'
  materialForm.minStock = '0'
  materialFieldError.value = null
}

function editSupplier(row: Supplier) {
  editingSupplierId.value = row.id
  supplierForm.name = row.name
  supplierForm.phone = row.phone ?? ''
  supplierForm.note = row.note ?? ''
}

function resetSupplierForm() {
  editingSupplierId.value = null
  supplierForm.name = ''
  supplierForm.phone = ''
  supplierForm.note = ''
}

function syncBranchForms() {
  const branch = workshop.selectedBranch
  if (branch) {
    branchForm.name = branch.name
    branchForm.address = branch.address
    branchForm.phone = branch.phone
    branchForm.latitude = String(branch.latitude)
    branchForm.longitude = String(branch.longitude)
    statusForm.status = branch.status
    statusForm.reason = branch.closed_reason ?? ''
  }
  const pricing = workshop.selectedBranchPricing
  if (pricing) {
    pricingForm.cuttingRateTiyin = String(pricing.cutting_rate_tiyin ?? '')
    pricingForm.edgeBandingRateTiyin = String(pricing.edge_banding_rate_tiyin ?? '')
  }
}

function statusClass(status: string) {
  return {
    'bg-success-soft text-success': status === 'active',
    'bg-warning-soft text-warning': status === 'temporarily_closed',
    'bg-danger-soft text-danger': status === 'inactive',
  }
}

function stockDisplayUnit(materialId: string) {
  return stockItemByMaterial(materialId)?.display_unit ?? 'pcs'
}

function formatTransactionQuantity(materialId: string, quantity: number) {
  return formatStockQuantity(quantity, stockDisplayUnit(materialId))
}

async function setBranchMaterialStatusWithConfirm(row: BranchMaterial) {
  const nextStatus = row.status === 'active' ? 'inactive' : 'active'
  const effect =
    nextStatus === 'inactive'
      ? 'hide this material from client selection while inventory remains manageable'
      : 'make this material available for client selection again'
  if (
    !window.confirm(
      `${nextStatus === 'inactive' ? 'Deactivate' : 'Activate'} ${row.material.name}: ${effect}.`,
    )
  ) {
    return
  }
  materialError.value = null
  try {
    await workshop.setBranchMaterialStatus(branchId.value, row.id, nextStatus)
  } catch {
    materialError.value = 'branch_material_status_failed'
  }
}

async function setSupplierStatusWithConfirm(supplier: Supplier) {
  const nextStatus = supplier.status === 'active' ? 'inactive' : 'active'
  if (
    !window.confirm(
      `${nextStatus === 'inactive' ? 'Deactivate' : 'Activate'} supplier ${supplier.name}.`,
    )
  ) {
    return
  }
  supplierError.value = null
  try {
    await workshop.setSupplierStatus(branchId.value, supplier.id, nextStatus)
  } catch {
    supplierError.value = 'supplier_status_failed'
  }
}

watch(branchId, refreshBranch)
onMounted(refreshBranch)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">
          {{ workshop.selectedBranch?.name ?? 'Branch' }}
        </h1>
        <p class="mt-2 text-base text-ink-soft">
          Materials, stock, supplier labels, pricing, and client visibility for this branch.
        </p>
      </div>
      <span
        v-if="workshop.selectedBranch"
        class="mp-chip"
        :class="statusClass(workshop.selectedBranch.status)"
      >
        <span class="mp-dot" aria-hidden="true"></span>
        {{ workshop.selectedBranch.status }}
      </span>
    </div>

    <div v-if="loading" class="rounded-lg bg-info-soft p-4 font-bold text-info" aria-live="polite">
      Loading branch workspace
    </div>
    <div v-else-if="pageError" class="rounded-lg bg-danger-soft p-4 font-bold text-danger">
      Branch workspace could not be loaded. trace {{ pageTraceId ?? 'unavailable' }}
    </div>

    <div v-if="visibleTabs.length > 0" class="flex flex-wrap gap-2" aria-label="Branch workspace">
      <button
        v-for="tab in visibleTabs"
        :key="tab.key"
        type="button"
        class="mp-button min-h-10 px-4 text-sm"
        :class="activeTab === tab.key ? 'mp-button-primary' : 'mp-button-outline'"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>
    <div
      v-else-if="!loading && !pageError"
      class="rounded-lg bg-warning-soft p-4 font-bold text-warning"
    >
      This account has no branch workspace permissions.
    </div>

    <section v-if="activeTab === 'materials' && canManageCatalog" class="space-y-5">
      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Add branch material</h2>
          <p class="mt-1 text-sm text-ink-soft">
            Edge min stock is entered in metres and stored internally as millimetres.
          </p>
        </div>
        <form class="grid gap-3 p-5 md:grid-cols-4" @submit.prevent="saveBranchMaterial">
          <SearchCombobox
            v-model="materialForm.materialId"
            label="Material"
            :options="availableCatalogOptions"
            :disabled="editingBranchMaterialId !== null"
            :error="materialFieldError"
            class="md:col-span-2"
          />
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-material-price">
              Price tiyin
            </label>
            <input
              id="branch-material-price"
              v-model="materialForm.priceTiyin"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              inputmode="numeric"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-material-min">
              Min stock {{ materialMinStockUnit }}
            </label>
            <input
              id="branch-material-min"
              v-model="materialForm.minStock"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              inputmode="decimal"
              required
            />
          </div>
          <div class="flex flex-wrap gap-2 md:col-span-4">
            <button class="mp-button mp-button-primary" type="submit" :disabled="materialSaving">
              {{
                materialSaving
                  ? 'Saving'
                  : editingBranchMaterialId
                    ? 'Save selection'
                    : 'Add material'
              }}
            </button>
            <button
              v-if="editingBranchMaterialId"
              type="button"
              class="mp-button mp-button-outline"
              @click="resetMaterialForm"
            >
              Cancel edit
            </button>
          </div>
          <p
            v-if="materialError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger md:col-span-4"
          >
            Branch material could not be saved.
          </p>
        </form>
      </section>

      <section class="mp-surface overflow-hidden">
        <div class="grid gap-3 border-b border-hairline p-5 md:grid-cols-[1fr_180px_auto]">
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-material-search">
              Search materials
            </label>
            <input
              id="branch-material-search"
              v-model="branchMaterialSearch"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
            />
          </div>
          <FilterDropdown
            v-model="branchMaterialStatus"
            label="Status"
            :options="materialStatusOptions"
          />
          <button
            class="mp-button mp-button-outline self-end"
            type="button"
            @click="refreshMaterials"
          >
            Apply
          </button>
        </div>
        <div v-if="workshop.branchMaterials.length === 0" class="px-5 py-6 text-sm text-ink-soft">
          No branch materials match the current filters.
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-[760px] w-full text-left text-sm">
            <thead class="bg-sunk text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-5 py-3">Material</th>
                <th class="px-5 py-3">Price</th>
                <th class="px-5 py-3">Min stock</th>
                <th class="px-5 py-3">Status</th>
                <th class="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr v-for="row in workshop.branchMaterials" :key="row.id">
                <td class="px-5 py-4">
                  <div class="font-extrabold text-ink">{{ row.material.name }}</div>
                  <div class="font-mono text-xs text-ink-muted">
                    {{ row.material.manufacturer_name }} · {{ row.material.kind }}
                  </div>
                </td>
                <td class="px-5 py-4">{{ formatTiyin(row.price_tiyin) }}</td>
                <td class="px-5 py-4">
                  {{
                    formatStockQuantity(row.min_stock, row.material.kind === 'edge' ? 'm' : 'pcs')
                  }}
                </td>
                <td class="px-5 py-4">
                  <span
                    class="mp-chip"
                    :class="
                      row.status === 'active'
                        ? 'bg-success-soft text-success'
                        : 'bg-danger-soft text-danger'
                    "
                  >
                    <span class="mp-dot" aria-hidden="true"></span>
                    {{ row.status }}
                  </span>
                </td>
                <td class="px-5 py-4">
                  <div class="flex justify-end gap-2">
                    <button
                      class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                      type="button"
                      @click="editBranchMaterial(row)"
                    >
                      Edit
                    </button>
                    <button
                      class="mp-button min-h-9 px-3 text-xs"
                      :class="
                        row.status === 'active'
                          ? 'border-danger bg-danger-soft text-danger'
                          : 'border-success bg-success-soft text-success'
                      "
                      type="button"
                      @click="setBranchMaterialStatusWithConfirm(row)"
                    >
                      {{ row.status === 'active' ? 'Deactivate' : 'Activate' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <section v-if="activeTab === 'inventory' && canManageInventory" class="space-y-5">
      <div class="grid gap-5 xl:grid-cols-2">
        <section class="mp-surface p-5">
          <h2 class="font-serif text-xl font-semibold text-ink">Stock in</h2>
          <form class="mt-4 grid gap-3" @submit.prevent="recordStockIn">
            <SearchCombobox
              v-model="stockInForm.materialId"
              label="Material"
              :options="stockOptions"
              :error="stockInMaterialError"
            />
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="stock-in-quantity">
                Quantity {{ selectedStockInItem?.display_unit ?? '' }}
              </label>
              <input
                id="stock-in-quantity"
                v-model="stockInForm.quantity"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="decimal"
                required
              />
            </div>
            <FormSelect
              v-model="stockInForm.supplierId"
              label="Supplier"
              :options="activeSupplierOptions"
              :error="stockInSupplierError"
            />
            <div v-if="stockInForm.supplierId === 'inline'">
              <label class="mb-1 block text-sm font-bold text-ink" for="inline-supplier">
                New supplier name
              </label>
              <input
                id="inline-supplier"
                v-model="stockInForm.inlineSupplierName"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                required
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="receipt-file"
                >Receipt</label
              >
              <input
                id="receipt-file"
                type="file"
                class="block min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 py-2 text-sm"
                @change="onReceiptFile"
              />
              <p v-if="stockInForm.receiptFileId" class="mt-1 font-mono text-[11px] text-ink-muted">
                receipt {{ stockInForm.receiptFileId.slice(0, 8) }}
              </p>
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="stock-in-note">Note</label>
              <input
                id="stock-in-note"
                v-model="stockInForm.note"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              />
            </div>
            <button class="mp-button mp-button-primary" type="submit" :disabled="movementSaving">
              {{ movementSaving ? 'Recording' : 'Record stock-in' }}
            </button>
            <p
              v-if="movementError"
              class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Stock movement could not be recorded.
            </p>
          </form>
        </section>

        <section class="mp-surface p-5">
          <h2 class="font-serif text-xl font-semibold text-ink">Adjustment</h2>
          <form class="mt-4 grid gap-3" @submit.prevent="recordAdjustment">
            <SearchCombobox
              v-model="adjustmentForm.materialId"
              label="Material"
              :options="stockOptions"
              :error="adjustmentMaterialError"
            />
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="adjustment-quantity">
                Signed quantity {{ selectedAdjustmentItem?.display_unit ?? '' }}
              </label>
              <input
                id="adjustment-quantity"
                v-model="adjustmentForm.quantity"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="decimal"
                required
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="adjustment-note"
                >Note</label
              >
              <input
                id="adjustment-note"
                v-model="adjustmentForm.note"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                required
              />
            </div>
            <button class="mp-button mp-button-primary" type="submit" :disabled="movementSaving">
              {{ movementSaving ? 'Recording' : 'Record adjustment' }}
            </button>
            <p
              v-if="movementError"
              class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Stock movement could not be recorded.
            </p>
          </form>
        </section>
      </div>

      <section class="mp-surface overflow-hidden">
        <div class="grid gap-3 border-b border-hairline p-5 md:grid-cols-[1fr_auto]">
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="stock-search"
              >Search stock</label
            >
            <input
              id="stock-search"
              v-model="stockSearch"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
            />
          </div>
          <button
            class="mp-button mp-button-outline self-end"
            type="button"
            @click="refreshInventory"
          >
            Refresh
          </button>
        </div>
        <div
          v-if="workshop.inventoryLoading"
          class="px-5 py-6 text-sm font-bold text-ink-soft"
          aria-live="polite"
        >
          Loading inventory
        </div>
        <div v-else-if="workshop.inventoryError" class="px-5 py-6 text-sm font-bold text-danger">
          Inventory could not be loaded. trace {{ workshop.inventoryTraceId ?? 'unavailable' }}
        </div>
        <div v-else-if="workshop.stockItems.length === 0" class="px-5 py-6 text-sm text-ink-soft">
          No stock rows yet. Add branch materials first.
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-[760px] w-full text-left text-sm">
            <thead class="bg-sunk text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-5 py-3">Material</th>
                <th class="px-5 py-3">On hand</th>
                <th class="px-5 py-3">Min stock</th>
                <th class="px-5 py-3">State</th>
                <th class="px-5 py-3">Updated</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr v-for="item in workshop.stockItems" :key="item.id">
                <td class="px-5 py-4">
                  <div class="font-extrabold text-ink">{{ item.material.name }}</div>
                  <div class="font-mono text-xs text-ink-muted">
                    {{ item.material.manufacturer_name }}
                  </div>
                </td>
                <td class="px-5 py-4">
                  {{ formatStockQuantity(item.on_hand, item.display_unit) }}
                </td>
                <td class="px-5 py-4">
                  {{ formatStockQuantity(item.min_stock, item.display_unit) }}
                </td>
                <td class="px-5 py-4">
                  <span
                    class="mp-chip"
                    :class="
                      item.is_low_stock
                        ? 'bg-warning-soft text-warning'
                        : 'bg-success-soft text-success'
                    "
                  >
                    <span class="mp-dot" aria-hidden="true"></span>
                    {{ item.is_low_stock ? 'low stock' : 'in range' }}
                  </span>
                </td>
                <td class="px-5 py-4 text-ink-soft">{{ formatDate(item.updated_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="grid gap-5 xl:grid-cols-[minmax(320px,0.72fr)_minmax(0,1.28fr)]">
        <section class="mp-surface p-5">
          <h2 class="font-serif text-xl font-semibold text-ink">Supplier labels</h2>
          <form class="mt-4 grid gap-3" @submit.prevent="saveSupplier">
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="supplier-name">Name</label>
              <input
                id="supplier-name"
                v-model="supplierForm.name"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                required
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="supplier-phone"
                >Phone</label
              >
              <input
                id="supplier-phone"
                v-model="supplierForm.phone"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="supplier-note">Note</label>
              <input
                id="supplier-note"
                v-model="supplierForm.note"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              />
            </div>
            <div class="flex flex-wrap gap-2">
              <button class="mp-button mp-button-primary" type="submit" :disabled="supplierSaving">
                {{
                  supplierSaving
                    ? 'Saving'
                    : editingSupplierId
                      ? 'Save supplier'
                      : 'Create supplier'
                }}
              </button>
              <button
                v-if="editingSupplierId"
                type="button"
                class="mp-button mp-button-outline"
                @click="resetSupplierForm"
              >
                Cancel edit
              </button>
            </div>
            <p
              v-if="supplierError"
              class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Supplier could not be saved.
            </p>
          </form>
        </section>

        <section class="mp-surface overflow-hidden">
          <div class="grid gap-3 border-b border-hairline p-5 md:grid-cols-[180px_auto]">
            <FilterDropdown
              v-model="supplierStatus"
              label="Supplier status"
              :options="supplierStatusOptions"
            />
            <button
              class="mp-button mp-button-outline self-end"
              type="button"
              @click="refreshInventory"
            >
              Apply
            </button>
          </div>
          <div v-if="workshop.suppliers.length === 0" class="px-5 py-6 text-sm text-ink-soft">
            No suppliers match the current filters.
          </div>
          <div v-else class="divide-y divide-hairline">
            <article
              v-for="supplier in workshop.suppliers"
              :key="supplier.id"
              class="grid gap-3 px-5 py-4 md:grid-cols-[1fr_auto]"
            >
              <div>
                <div class="font-extrabold text-ink">{{ supplier.name }}</div>
                <div class="text-sm text-ink-soft">
                  {{ supplier.phone || 'No phone' }} · {{ supplier.note || 'No note' }}
                </div>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <span
                  class="mp-chip"
                  :class="
                    supplier.status === 'active'
                      ? 'bg-success-soft text-success'
                      : 'bg-danger-soft text-danger'
                  "
                >
                  <span class="mp-dot" aria-hidden="true"></span>
                  {{ supplier.status }}
                </span>
                <button
                  class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                  type="button"
                  @click="editSupplier(supplier)"
                >
                  Edit
                </button>
                <button
                  class="mp-button min-h-9 px-3 text-xs"
                  :class="
                    supplier.status === 'active'
                      ? 'border-danger bg-danger-soft text-danger'
                      : 'border-success bg-success-soft text-success'
                  "
                  type="button"
                  @click="setSupplierStatusWithConfirm(supplier)"
                >
                  {{ supplier.status === 'active' ? 'Deactivate' : 'Activate' }}
                </button>
              </div>
            </article>
          </div>
        </section>
      </div>

      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Transactions</h2>
        </div>
        <div v-if="workshop.stockTransactions.length === 0" class="px-5 py-6 text-sm text-ink-soft">
          No stock transactions yet.
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-[780px] w-full text-left text-sm">
            <thead class="bg-sunk text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-5 py-3">Date</th>
                <th class="px-5 py-3">Material</th>
                <th class="px-5 py-3">Type</th>
                <th class="px-5 py-3">Qty</th>
                <th class="px-5 py-3">Balance</th>
                <th class="px-5 py-3">Supplier</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr v-for="tx in workshop.stockTransactions" :key="tx.id">
                <td class="px-5 py-4">{{ formatDate(tx.created_at) }}</td>
                <td class="px-5 py-4 font-bold text-ink">{{ tx.material_name }}</td>
                <td class="px-5 py-4">{{ tx.type }}</td>
                <td class="px-5 py-4 font-mono">
                  {{ formatTransactionQuantity(tx.material_id, tx.quantity) }}
                </td>
                <td class="px-5 py-4 font-mono">
                  {{ formatTransactionQuantity(tx.material_id, tx.balance_after) }}
                </td>
                <td class="px-5 py-4 text-ink-soft">{{ tx.supplier_name || 'none' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <section v-if="activeTab === 'settings' && canManageSettings" class="grid gap-5 xl:grid-cols-2">
      <section class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold text-ink">Branch details and pricing</h2>
        <form class="mt-4 grid gap-3" @submit.prevent="saveBranchSettings">
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-name"
              >Name</label
            >
            <input
              id="detail-branch-name"
              v-model="branchForm.name"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-address"
              >Address</label
            >
            <input
              id="detail-branch-address"
              v-model="branchForm.address"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div class="grid gap-3 md:grid-cols-3">
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-phone"
                >Phone</label
              >
              <input
                id="detail-branch-phone"
                v-model="branchForm.phone"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                required
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-lat"
                >Latitude</label
              >
              <input
                id="detail-branch-lat"
                v-model="branchForm.latitude"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="decimal"
                required
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-lng"
                >Longitude</label
              >
              <input
                id="detail-branch-lng"
                v-model="branchForm.longitude"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="decimal"
                required
              />
            </div>
          </div>
          <div class="grid gap-3 md:grid-cols-2">
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="cutting-rate"
                >Cutting rate tiyin</label
              >
              <input
                id="cutting-rate"
                v-model="pricingForm.cuttingRateTiyin"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="numeric"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="edge-rate"
                >Edge rate tiyin</label
              >
              <input
                id="edge-rate"
                v-model="pricingForm.edgeBandingRateTiyin"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="numeric"
              />
            </div>
          </div>
          <button class="mp-button mp-button-primary" type="submit" :disabled="settingsSaving">
            {{ settingsSaving ? 'Saving' : 'Save branch settings' }}
          </button>
        </form>
      </section>

      <section class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold text-ink">Client visibility</h2>
        <form class="mt-4 grid gap-3" @submit.prevent="changeBranchStatus">
          <FormSelect v-model="statusForm.status" label="Status" :options="statusOptions" />
          <div v-if="statusForm.status !== 'active'">
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-status-reason"
              >Reason</label
            >
            <input
              id="branch-status-reason"
              v-model="statusForm.reason"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <label
            class="flex items-start gap-3 rounded-md border border-warning bg-warning-soft p-3 text-sm font-bold text-warning"
          >
            <input
              v-model="statusForm.confirmed"
              type="checkbox"
              class="mt-1 size-4 accent-warning"
            />
            <span>
              Confirm client visibility change. Open-order warning count:
              {{ workshop.selectedBranch?.active_orders_count ?? 0 }}.
            </span>
          </label>
          <button
            class="mp-button mp-button-primary"
            type="submit"
            :disabled="settingsSaving || !statusForm.confirmed"
          >
            {{ settingsSaving ? 'Changing' : 'Change status' }}
          </button>
          <p
            v-if="settingsError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            Branch settings could not be saved.
          </p>
        </form>
      </section>
    </section>
  </section>
</template>
