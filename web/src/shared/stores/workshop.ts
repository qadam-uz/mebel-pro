import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  api,
  apiTraceId,
  captureApiError,
  isPermissionDenied,
  withQuery,
} from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import {
  CATALOG_PICKER_LIMIT,
  INVENTORY_TX_PAGE_LIMIT,
  MATERIALS_PAGE_LIMIT,
} from '@/shared/app/constants'
import type { Dekor, DekorType, MaterialStatus } from '@/shared/stores/admin'
import { useAuthStore, type SessionResponse } from '@/shared/stores/auth'

export type BranchStatus = 'active' | 'temporarily_closed' | 'inactive'
export type SupplierStatus = 'active' | 'inactive'
export type StockTransactionType = 'stock_in' | 'consume' | 'restore' | 'adjust'

export interface BranchContextItem {
  id: string
  name: string
  address: string
  phone: string
  status: 'active' | 'temporarily_closed'
  closed_reason: string | null
  kerf_mm: number
  edge_trim_mm: number
  permissions: string[]
}

export interface WorkshopUser {
  id: string
  workshop_id: string
  login: string
  full_name: string
  phone: string
  is_owner: boolean
  home_branch_id: string
  status: 'active' | 'blocked'
  password_reset_required: boolean
  last_login_at: string | null
  grants: Array<{ permission: string; branch_id: string }>
}

export interface WorkshopUserFilters {
  search?: string
  branch_id?: string | null
  status?: WorkshopUser['status'] | null
}

export interface WorkshopSettings {
  id: string
  name: string
  logo_file_id: string | null
  status: 'active' | 'blocked'
  currency: 'UZS'
  owner_user_id: string
  created_at: string
  updated_at: string
}

export interface ManagedBranch {
  id: string
  workshop_id: string
  // Platform-wide branch number, assigned at creation and immutable — it is the
  // middle segment of every order number the branch prints, `#26-1-0003`
  // (QAD-146). Read-only: it is never sent back in a create or patch payload.
  branch_no: number
  name: string
  address: string
  phone: string
  // Extra published numbers in display order; the primary stays `phone` (QAD-158).
  additional_phones: string[]
  latitude: string | null
  longitude: string | null
  status: BranchStatus
  closed_reason: string | null
  kerf_mm: number
  edge_trim_mm: number
  created_at: string
  updated_at: string
}

export interface BranchPricing {
  branch_id: string
  cutting_rate_tiyin: number | null
  edge_banding_rate_tiyin: number | null
  updated_at: string | null
  updated_by_user_id: string | null
}

/**
 * THE material: a dekor in one concrete format, owned by one branch. Identity is
 * nested under `.dekor`; the format lives here. There is no stored name — render
 * `label`, which the server composes (backend/app/core/material_label.py).
 */
export interface BranchMaterial {
  id: string
  branch_id: string
  dekor_id: string
  dekor: Dekor
  qalinlik_mm: string
  uzunlik_mm: number | null
  eni_mm: number | null
  kromka_eni_mm: number | null
  price_tiyin: number
  // price_tiyin === 0 means unpriced, not free. Client-facing listings drop these
  // rows; workshop-facing ones flag them so the gap is visible where it is fixable.
  price_unset: boolean
  min_stock: number
  status: MaterialStatus
  label: string
  created_at: string
  updated_at: string
}

// A dekor the branch may attach. It is never hidden once carried — carrying 18 mm
// does not stop you adding 16 mm — so the count says how many formats are already in.
export interface BranchCatalogOption {
  dekor: Dekor
  carried_format_count: number
}

// QAD-159: the picker needs an honest "Filtrdagi hammasi (N)" count, so this
// endpoint returns the page plus the total matching the same filters.
export interface BranchCatalogOptionsPage {
  items: BranchCatalogOption[]
  total: number
}

// Manufacturers only. Thickness used to be a facet here because it was a
// platform-catalog fact; it is now a per-branch format the operator types in, so
// there is nothing left to enumerate. `tur` is a fixed enum rendered without asking.
export interface BranchCatalogFilters {
  manufacturers: { id: string; name: string }[]
}

/** One (thickness + size) combination of a dekor a branch wants to carry. */
export interface BranchMaterialFormatInput {
  qalinlik_mm: string
  uzunlik_mm?: number
  eni_mm?: number
  kromka_eni_mm?: number
  // Both optional server-side, defaulting to 0: a branch routinely registers its
  // whole format list before it knows prices.
  price_tiyin?: number
  min_stock?: number
}

/** One dekor and the o'lchamlar the branch wants to carry it in. */
export interface BranchMaterialAttachItem {
  dekor_id: string
  formats: BranchMaterialFormatInput[]
}

/**
 * Attach several dekorlar, each in one or more o'lchamlar, in ONE transaction.
 *
 * A list rather than a single dekor because that is the shape of the real job:
 * 87% of carried dekorlar exist in exactly one o'lcham, so a branch registering
 * its supplier list picks many dekorlar and one o'lcham, not the reverse.
 * Per-dekor `formats` keeps a mixed batch possible — a board and its matching
 * kromka have different o'lcham axes and still belong in one save.
 */
export interface BranchMaterialAttachRequest {
  items: BranchMaterialAttachItem[]
}

/** Identifies one o'lcham of one dekor within a branch. */
export interface BranchMaterialFormatKey {
  dekor_id: string
  qalinlik_mm: string
  uzunlik_mm: number | null
  eni_mm: number | null
  kromka_eni_mm: number | null
}

export interface BranchMaterialAttachResponse {
  created: BranchMaterial[]
  // Formats this branch already carries. The picker shows what is carried, so a
  // duplicate here is a race, not user error — surface it as "already carried,
  // skipped", never as a failure.
  skipped: BranchMaterialFormatKey[]
}

export interface Supplier {
  id: string
  workshop_id: string
  name: string
  phone: string | null
  note: string | null
  status: SupplierStatus
  created_by_user_id: string
  created_at: string
  updated_at: string
}

export interface StockItem {
  id: string
  branch_id: string
  branch_material_id: string
  material: BranchMaterial
  tur: DekorType
  stock_unit: string
  display_unit: string
  on_hand: number
  min_stock: number
  is_low_stock: boolean
  updated_at: string
}

export interface StockTransaction {
  id: string
  stock_item_id: string
  branch_material_id: string
  // Server-composed label, not a stored column — leave it alone.
  material_name: string
  type: StockTransactionType
  quantity: number
  balance_after: number
  unit_price_tiyin: number | null
  total_price_tiyin: number | null
  order_id: string | null
  supplier_id: string | null
  supplier_name: string | null
  actor_user_id: string | null
  actor_name: string | null
  note: string | null
  created_at: string
}

export type InvoicePaymentStatus = 'unpaid' | 'partial' | 'paid'

export interface SupplierInvoiceLine {
  transaction_id: string
  branch_material_id: string
  material_name: string
  tur: DekorType
  display_unit: string
  quantity: number
  unit_price_tiyin: number | null
  total_price_tiyin: number | null
  note: string | null
}

export interface SupplierInvoice {
  id: string
  workshop_id: string
  branch_id: string
  branch_name: string | null
  supplier_id: string | null
  supplier_name: string | null
  invoice_no: string
  invoice_date: string
  subtotal_tiyin: number
  discount_tiyin: number
  surcharge_tiyin: number
  total_tiyin: number
  note: string | null
  line_count: number
  paid_tiyin: number
  outstanding_tiyin: number
  payment_status: InvoicePaymentStatus
  recorded_by_user_id: string
  recorded_by_name: string | null
  created_at: string
  lines: SupplierInvoiceLine[]
}

export interface SupplierInvoiceFilters {
  supplier_id?: string | null
  search?: string | null
  payment_status?: InvoicePaymentStatus | null
}

export interface StockLastPrice {
  unit_price_tiyin: number | null
  recorded_at: string | null
  supplier_id: string | null
  supplier_name: string | null
}

export interface StockTransactionFilters {
  branch_material_id?: string | null
  date_from?: string | null
  date_to?: string | null
  limit?: number
  offset?: number
}

export interface BranchMaterialFilters {
  search?: string
  tur?: DekorType | null
  status?: MaterialStatus | null
  manufacturer_id?: string | null
  // Narrows the grouped-by-dekor table to one dekor's formats.
  dekor_id?: string | null
  offset?: number
  limit?: number
}

export const permissionCatalog = [
  'view_orders',
  'manage_orders',
  'process_production',
  'manage_catalog',
  'manage_inventory',
  'manage_finance',
  'view_finance_reports',
] as const

export const useWorkshopStore = defineStore('workshop', () => {
  const branches = ref<BranchContextItem[]>([])
  const selectedBranchContext = ref<string | null>(null)
  const settings = ref<WorkshopSettings | null>(null)
  const managedBranches = ref<ManagedBranch[]>([])
  const selectedBranch = ref<ManagedBranch | null>(null)
  const selectedBranchPricing = ref<BranchPricing | null>(null)
  const catalogOptions = ref<BranchCatalogOption[]>([])
  const catalogOptionsTotal = ref(0)
  const catalogFilters = ref<BranchCatalogFilters>({ manufacturers: [] })
  const branchMaterials = ref<BranchMaterial[]>([])
  const branchMaterialsHasMore = ref(false)
  const suppliers = ref<Supplier[]>([])
  const stockItems = ref<StockItem[]>([])
  const lowStockItems = ref<StockItem[]>([])
  const stockValueTiyin = ref<number | null>(null)
  const stockTransactions = ref<StockTransaction[]>([])
  const stockTransactionsHasMore = ref(false)
  const supplierInvoices = ref<SupplierInvoice[]>([])
  const users = ref<WorkshopUser[]>([])
  const selectedUser = ref<WorkshopUser | null>(null)
  const sessions = ref<SessionResponse[]>([])
  const lastTempPassword = ref<string | null>(null)
  const loading = ref(false)
  const catalogLoading = ref(false)
  const setupLoading = ref(false)
  const inventoryLoading = ref(false)
  const error = ref<string | null>(null)
  const catalogError = ref<string | null>(null)
  const setupError = ref<string | null>(null)
  const inventoryError = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const catalogTraceId = ref<string | null>(null)
  const setupTraceId = ref<string | null>(null)
  const inventoryTraceId = ref<string | null>(null)
  const actionError = ref<string | null>(null)
  const actionTraceId = ref<string | null>(null)
  const branchContextLoaded = ref(false)
  const auth = useAuthStore()
  let usersLoadRequestId = 0
  let catalogLoadRequestId = 0

  function upsertUser(user: WorkshopUser) {
    users.value = [...users.value.filter((current) => current.id !== user.id), user]
  }

  function captureAction(errorValue: unknown, fallback: string) {
    const captured = captureApiError(errorValue, fallback)
    actionError.value = captured.code
    actionTraceId.value = captured.traceId
  }

  /**
   * A refused read means the grant behind the rows on screen is gone. Drop them
   * instead of leaving them under an error line — a table the server just said
   * you may not read has no business staying visible (QAD-172). Other failures
   * (offline, 5xx) keep the last good rows: the data is still the viewer's, it
   * merely failed to refresh.
   */
  async function readOrDrop<T>(read: () => Promise<T>, drop: () => void): Promise<T> {
    try {
      return await read()
    } catch (errorValue) {
      if (isPermissionDenied(errorValue)) drop()
      throw errorValue
    }
  }

  function setSelectedBranchContext(value: string | null) {
    selectedBranchContext.value = value && value !== 'none' ? value : null
  }

  async function loadBranchContext(options: { force?: boolean } = {}) {
    if (branchContextLoaded.value && !options.force) return
    error.value = null
    traceId.value = null
    try {
      const response = await api.get<{ branches: BranchContextItem[] }>(
        '/workshop/branch-context',
        authInit(),
      )
      branches.value = response.branches
      branchContextLoaded.value = true
    } catch (errorValue) {
      branchContextLoaded.value = false
      error.value = 'branch_context_load_failed'
      traceId.value = apiTraceId(errorValue)
      throw error.value
    }
  }

  async function loadSettings() {
    setupLoading.value = true
    setupError.value = null
    setupTraceId.value = null
    try {
      settings.value = await api.get<WorkshopSettings>('/workshop/settings', authInit())
    } catch (errorValue) {
      setupError.value = 'settings_load_failed'
      setupTraceId.value = apiTraceId(errorValue)
    } finally {
      setupLoading.value = false
    }
  }

  async function updateSettings(payload: unknown) {
    settings.value = await api.patch<WorkshopSettings>('/workshop/settings', payload, authInit())
    return settings.value
  }

  async function loadManagedBranches() {
    setupLoading.value = true
    setupError.value = null
    setupTraceId.value = null
    try {
      managedBranches.value = await api.get<ManagedBranch[]>('/workshop/branches', authInit())
    } catch (errorValue) {
      setupError.value = 'branches_load_failed'
      setupTraceId.value = apiTraceId(errorValue)
    } finally {
      setupLoading.value = false
    }
  }

  async function createBranch(payload: unknown) {
    const created = await api.post<ManagedBranch>('/workshop/branches', payload, authInit())
    managedBranches.value = [created, ...managedBranches.value]
    await loadBranchContext({ force: true }).catch(() => undefined)
    return created
  }

  async function loadBranch(id: string) {
    setupLoading.value = true
    setupError.value = null
    setupTraceId.value = null
    selectedBranch.value = null
    selectedBranchPricing.value = null
    try {
      selectedBranch.value = await api.get<ManagedBranch>(`/workshop/branches/${id}`, authInit())
      if (auth.me?.is_owner) {
        selectedBranchPricing.value = await api.get<BranchPricing>(
          `/workshop/branches/${id}/pricing`,
          authInit(),
        )
      }
    } catch (errorValue) {
      setupError.value = 'branch_load_failed'
      setupTraceId.value = apiTraceId(errorValue)
      selectedBranch.value = null
      selectedBranchPricing.value = null
      throw setupError.value
    } finally {
      setupLoading.value = false
    }
  }

  async function updateBranch(id: string, payload: unknown) {
    const updated = await api.patch<ManagedBranch>(`/workshop/branches/${id}`, payload, authInit())
    patchManagedBranch(updated)
    selectedBranch.value = updated
    await loadBranchContext({ force: true }).catch(() => undefined)
    return updated
  }

  async function setBranchStatus(id: string, payload: unknown) {
    const updated = await api.post<ManagedBranch>(
      `/workshop/branches/${id}/status`,
      payload,
      authInit(),
    )
    patchManagedBranch(updated)
    selectedBranch.value = updated
    await loadBranchContext({ force: true }).catch(() => undefined)
    return updated
  }

  async function updateBranchPricing(id: string, payload: unknown) {
    selectedBranchPricing.value = await api.put<BranchPricing>(
      `/workshop/branches/${id}/pricing`,
      payload,
      authInit(),
    )
    return selectedBranchPricing.value
  }

  // The add-material picker is server-searched and capped — never the whole
  // catalog — so opening the sheet on the full dekor set doesn't freeze. Returns
  // the page so a caller can render an honest "Filtrdagi hammasi (N)" without the
  // store holding more than the visible list.
  async function fetchCatalogOptions(id: string, filters: BranchMaterialFilters = {}) {
    return api.get<BranchCatalogOptionsPage>(
      withQuery(`/workshop/branches/${id}/catalog/dekorlar`, {
        search: filters.search,
        tur: filters.tur,
        manufacturer_id: filters.manufacturer_id,
        limit: filters.limit ?? CATALOG_PICKER_LIMIT,
        offset: filters.offset,
      }),
      authInit(),
    )
  }

  async function loadCatalogOptions(id: string, filters: BranchMaterialFilters = {}) {
    const page = await fetchCatalogOptions(id, filters)
    catalogOptions.value = page.items
    catalogOptionsTotal.value = page.total
    return page
  }

  async function loadCatalogFilters(id: string) {
    catalogFilters.value = await api.get<BranchCatalogFilters>(
      `/workshop/branches/${id}/catalog/filters`,
      authInit(),
    )
    return catalogFilters.value
  }

  // Paginated with append (offset 0 replaces, higher offset appends the next
  // page); branchMaterialsHasMore is inferred from a full page. The requestId
  // guard drops stale responses when filters change mid-flight.
  async function loadBranchMaterials(id: string, filters: BranchMaterialFilters = {}) {
    const offset = filters.offset ?? 0
    const requestId = ++catalogLoadRequestId
    catalogLoading.value = true
    catalogError.value = null
    catalogTraceId.value = null
    try {
      const rows = await api.get<BranchMaterial[]>(
        withQuery(`/workshop/branches/${id}/materials`, {
          search: filters.search,
          tur: filters.tur,
          manufacturer_id: filters.manufacturer_id,
          dekor_id: filters.dekor_id,
          status: filters.status,
          limit: MATERIALS_PAGE_LIMIT,
          offset,
        }),
        authInit(),
      )
      if (requestId === catalogLoadRequestId) {
        branchMaterials.value = offset === 0 ? rows : [...branchMaterials.value, ...rows]
        branchMaterialsHasMore.value = rows.length === MATERIALS_PAGE_LIMIT
      }
    } catch (errorValue) {
      if (requestId === catalogLoadRequestId) {
        catalogError.value = 'catalog_load_failed'
        catalogTraceId.value = apiTraceId(errorValue)
        if (isPermissionDenied(errorValue)) {
          branchMaterials.value = []
          branchMaterialsHasMore.value = false
        }
      }
      throw errorValue
    } finally {
      if (requestId === catalogLoadRequestId) catalogLoading.value = false
    }
  }

  /**
   * Attach several dekorlar, each in one or more o'lchamlar, in one server-side
   * transaction. The batch is all-or-nothing on *validity* — one malformed
   * o'lcham writes nothing — but never on duplication: an o'lcham this branch
   * already carries comes back under `skipped` instead of failing the call.
   * Callers must surface `skipped` as "already carried", never as an error.
   */
  async function attachBranchMaterials(id: string, payload: BranchMaterialAttachRequest) {
    const result = await api.post<BranchMaterialAttachResponse>(
      `/workshop/branches/${id}/materials`,
      payload,
      authInit(),
    )
    branchMaterials.value = [...result.created, ...branchMaterials.value]
    await loadStock(id).catch(() => undefined)
    await loadCatalogOptions(id).catch(() => undefined)
    return result
  }

  async function updateBranchMaterial(id: string, branchMaterialId: string, payload: unknown) {
    const updated = await api.patch<BranchMaterial>(
      `/workshop/branches/${id}/materials/${branchMaterialId}`,
      payload,
      authInit(),
    )
    patchBranchMaterial(updated)
    await loadStock(id).catch(() => undefined)
    return updated
  }

  async function setBranchMaterialStatus(
    id: string,
    branchMaterialId: string,
    status: MaterialStatus,
  ) {
    const updated = await api.post<BranchMaterial>(
      `/workshop/branches/${id}/materials/${branchMaterialId}/${
        status === 'active' ? 'activate' : 'deactivate'
      }`,
      undefined,
      authInit(),
    )
    patchBranchMaterial(updated)
    return updated
  }

  async function loadStock(
    id: string,
    filters: { search?: string; low_stock?: boolean | null } = {},
  ) {
    stockItems.value = await readOrDrop(
      () =>
        api.get<StockItem[]>(
          withQuery(`/workshop/branches/${id}/stock`, {
            search: filters.search,
            low_stock: filters.low_stock ? true : undefined,
          }),
          authInit(),
        ),
      () => {
        stockItems.value = []
      },
    )
  }

  async function loadLowStock(branchIds: string[]) {
    if (branchIds.length === 0) {
      lowStockItems.value = []
      return
    }
    const pages = await readOrDrop(
      () =>
        Promise.all(
          [...new Set(branchIds)].map((id) =>
            api.get<StockItem[]>(
              withQuery(`/workshop/branches/${id}/stock`, {
                low_stock: true,
              }),
              authInit(),
            ),
          ),
        ),
      () => {
        lowStockItems.value = []
      },
    )
    lowStockItems.value = pages.flat()
  }

  // Warehouse value at the latest purchase prices — derived server-side per
  // branch and summed here across the branches in view.
  async function loadStockValue(branchIds: string[]) {
    if (branchIds.length === 0) {
      stockValueTiyin.value = null
      return
    }
    const values = await readOrDrop(
      () =>
        Promise.all(
          [...new Set(branchIds)].map((id) =>
            api.get<{ value_tiyin: number }>(`/workshop/branches/${id}/stock-value`, authInit()),
          ),
        ),
      () => {
        stockValueTiyin.value = null
      },
    )
    stockValueTiyin.value = values.reduce((sum, row) => sum + row.value_tiyin, 0)
  }

  async function loadStockTransactions(id: string, filters: StockTransactionFilters = {}) {
    const limit = filters.limit ?? INVENTORY_TX_PAGE_LIMIT
    const offset = filters.offset ?? 0
    const page = await readOrDrop(
      () =>
        api.get<StockTransaction[]>(
          withQuery(`/workshop/branches/${id}/stock-transactions`, {
            branch_material_id: filters.branch_material_id,
            date_from: filters.date_from,
            date_to: filters.date_to,
            limit,
            offset,
          }),
          authInit(),
        ),
      () => {
        stockTransactions.value = []
        stockTransactionsHasMore.value = false
      },
    )
    stockTransactions.value = offset === 0 ? page : [...stockTransactions.value, ...page]
    stockTransactionsHasMore.value = page.length === limit
  }

  async function loadSuppliers(id: string, status?: SupplierStatus | null) {
    suppliers.value = await readOrDrop(
      () =>
        api.get<Supplier[]>(
          withQuery(`/workshop/branches/${id}/suppliers`, { status }),
          authInit(),
        ),
      () => {
        suppliers.value = []
      },
    )
  }

  async function loadInventory(id: string) {
    inventoryLoading.value = true
    inventoryError.value = null
    inventoryTraceId.value = null
    try {
      await Promise.all([loadStock(id), loadStockTransactions(id), loadSuppliers(id)])
    } catch (errorValue) {
      inventoryError.value = 'inventory_load_failed'
      inventoryTraceId.value = apiTraceId(errorValue)
    } finally {
      inventoryLoading.value = false
    }
  }

  async function loadSupplierInvoices(id: string, filters: SupplierInvoiceFilters = {}) {
    supplierInvoices.value = await readOrDrop(
      () =>
        api.get<SupplierInvoice[]>(
          withQuery('/workshop/inventory/invoices', {
            branch_id: id,
            supplier_id: filters.supplier_id,
            search: filters.search,
            payment_status: filters.payment_status,
          }),
          authInit(),
        ),
      () => {
        supplierInvoices.value = []
      },
    )
  }

  function clearInventory() {
    suppliers.value = []
    stockItems.value = []
    lowStockItems.value = []
    stockTransactions.value = []
    stockTransactionsHasMore.value = false
    supplierInvoices.value = []
    inventoryError.value = null
    inventoryTraceId.value = null
  }

  async function createSupplier(id: string, payload: unknown) {
    const created = await api.post<Supplier>(
      `/workshop/branches/${id}/suppliers`,
      payload,
      authInit(),
    )
    suppliers.value = [created, ...suppliers.value]
    return created
  }

  async function updateSupplier(id: string, supplierId: string, payload: unknown) {
    const updated = await api.patch<Supplier>(
      `/workshop/branches/${id}/suppliers/${supplierId}`,
      payload,
      authInit(),
    )
    patchSupplier(updated)
    return updated
  }

  async function setSupplierStatus(id: string, supplierId: string, status: SupplierStatus) {
    const updated = await api.post<Supplier>(
      `/workshop/branches/${id}/suppliers/${supplierId}/${
        status === 'active' ? 'activate' : 'deactivate'
      }`,
      undefined,
      authInit(),
    )
    patchSupplier(updated)
    return updated
  }

  // Read-only prefill helper — intentionally not stored: the latest price is
  // always derived from transaction history, never cached as state.
  async function fetchMaterialLastPrice(
    id: string,
    branchMaterialId: string,
    supplierId?: string | null,
  ) {
    return api.get<StockLastPrice>(
      withQuery(`/workshop/branches/${id}/materials/${branchMaterialId}/last-price`, {
        supplier_id: supplierId ?? undefined,
      }),
      authInit(),
    )
  }

  // One arrival document and all its lines, committed together server-side.
  // The stock and transaction views are refreshed after it so the page never
  // shows a half-applied arrival.
  async function createSupplierInvoice(id: string, payload: unknown) {
    const invoice = await api.post<SupplierInvoice>(
      '/workshop/inventory/invoices',
      { ...(payload as object), branch_id: id },
      authInit(),
    )
    supplierInvoices.value = [invoice, ...supplierInvoices.value]
    await loadStock(id).catch(() => undefined)
    if ((payload as { supplier?: unknown }).supplier) await loadSuppliers(id).catch(() => undefined)
    return invoice
  }

  async function recordStockIn(id: string, payload: unknown) {
    const transaction = await api.post<StockTransaction>(
      `/workshop/branches/${id}/stock-in`,
      payload,
      authInit(),
    )
    stockTransactions.value = [transaction, ...stockTransactions.value]
    await loadStock(id).catch(() => undefined)
    if ((payload as { supplier?: unknown }).supplier) await loadSuppliers(id).catch(() => undefined)
    return transaction
  }

  async function recordAdjustment(id: string, payload: unknown) {
    const transaction = await api.post<StockTransaction>(
      `/workshop/branches/${id}/stock-adjustments`,
      payload,
      authInit(),
    )
    stockTransactions.value = [transaction, ...stockTransactions.value]
    await loadStock(id).catch(() => undefined)
    return transaction
  }

  async function loadUsers(
    options: { preserveTempPassword?: boolean; filters?: WorkshopUserFilters } = {},
  ) {
    const requestId = ++usersLoadRequestId
    loading.value = true
    error.value = null
    traceId.value = null
    if (!options.preserveTempPassword) lastTempPassword.value = null
    try {
      const loadedUsers = await api.get<WorkshopUser[]>(
        withQuery('/workshop/users', {
          search: options.filters?.search,
          branch_id: options.filters?.branch_id,
          status: options.filters?.status,
        }),
        authInit(),
      )
      if (requestId === usersLoadRequestId) {
        users.value = loadedUsers
      }
    } catch (errorValue) {
      if (requestId === usersLoadRequestId) {
        error.value = 'users_load_failed'
        traceId.value = apiTraceId(errorValue)
      }
    } finally {
      if (requestId === usersLoadRequestId) {
        loading.value = false
      }
    }
  }

  async function createUser(payload: unknown) {
    error.value = null
    actionError.value = null
    actionTraceId.value = null
    try {
      const response = await api.post<{ user: WorkshopUser; temp_password: string }>(
        '/workshop/users',
        payload,
        authInit(),
      )
      usersLoadRequestId += 1
      upsertUser(response.user)
      lastTempPassword.value = response.temp_password
      await loadUsers({ preserveTempPassword: true })
      return response
    } catch (errorValue) {
      captureAction(errorValue, 'user_create_failed')
      throw errorValue
    }
  }

  async function loadUser(id: string) {
    loading.value = true
    error.value = null
    traceId.value = null
    lastTempPassword.value = null
    selectedUser.value = null
    sessions.value = []
    try {
      const loadedUser = await api.get<WorkshopUser>(`/workshop/users/${id}`, authInit())
      selectedUser.value = loadedUser
      if (!loadedUser.is_owner) {
        try {
          sessions.value = (
            await api.get<{ sessions: SessionResponse[] }>(
              `/workshop/users/${id}/sessions`,
              authInit(),
            )
          ).sessions
        } catch {
          sessions.value = []
        }
      }
    } catch (errorValue) {
      error.value = 'user_load_failed'
      traceId.value = apiTraceId(errorValue)
    } finally {
      loading.value = false
    }
  }

  async function updateUser(
    id: string,
    payload: {
      full_name?: string
      phone?: string
      login?: string
      home_branch_id?: string
    },
  ) {
    error.value = null
    actionError.value = null
    actionTraceId.value = null
    try {
      selectedUser.value = await api.patch<WorkshopUser>(
        `/workshop/users/${id}`,
        payload,
        authInit(),
      )
      upsertUser(selectedUser.value)
      return selectedUser.value
    } catch (errorValue) {
      captureAction(errorValue, 'user_save_failed')
      throw errorValue
    }
  }

  async function replaceGrants(
    id: string,
    grants: Array<{ permission: string; branch_id: string }>,
  ) {
    error.value = null
    actionError.value = null
    actionTraceId.value = null
    try {
      selectedUser.value = await api.put<WorkshopUser>(
        `/workshop/users/${id}/grants`,
        { grants },
        authInit(),
      )
    } catch (errorValue) {
      captureAction(errorValue, 'grants_save_failed')
      throw errorValue
    }
  }

  async function resetPassword(id: string) {
    error.value = null
    actionError.value = null
    actionTraceId.value = null
    try {
      const response = await api.post<{ user: WorkshopUser; temp_password: string }>(
        `/workshop/users/${id}/reset-password`,
        undefined,
        authInit(),
      )
      selectedUser.value = response.user
      lastTempPassword.value = response.temp_password
    } catch (errorValue) {
      captureAction(errorValue, 'password_reset_failed')
      throw errorValue
    }
  }

  async function blockUser(id: string, reason: string) {
    error.value = null
    actionError.value = null
    actionTraceId.value = null
    try {
      selectedUser.value = await api.post<WorkshopUser>(
        `/workshop/users/${id}/block`,
        { reason },
        authInit(),
      )
    } catch (errorValue) {
      captureAction(errorValue, 'user_block_failed')
      throw errorValue
    }
  }

  async function unblockUser(id: string) {
    error.value = null
    actionError.value = null
    actionTraceId.value = null
    try {
      selectedUser.value = await api.post<WorkshopUser>(
        `/workshop/users/${id}/unblock`,
        undefined,
        authInit(),
      )
    } catch (errorValue) {
      captureAction(errorValue, 'user_unblock_failed')
      throw errorValue
    }
  }

  async function revokeUserSessions(id: string) {
    error.value = null
    actionError.value = null
    actionTraceId.value = null
    try {
      await api.del(`/workshop/users/${id}/sessions`, authInit())
      sessions.value = []
    } catch (errorValue) {
      captureAction(errorValue, 'sessions_revoke_failed')
      throw errorValue
    }
  }

  async function revokeUserSession(id: string, sessionId: string) {
    error.value = null
    actionError.value = null
    actionTraceId.value = null
    try {
      await api.del(`/workshop/users/${id}/sessions/${sessionId}`, authInit())
      sessions.value = sessions.value.filter((session) => session.id !== sessionId)
    } catch (errorValue) {
      captureAction(errorValue, 'session_revoke_failed')
      throw errorValue
    }
  }

  function patchManagedBranch(updated: ManagedBranch) {
    managedBranches.value = managedBranches.value.map((row) =>
      row.id === updated.id ? updated : row,
    )
  }

  function patchBranchMaterial(updated: BranchMaterial) {
    branchMaterials.value = branchMaterials.value.map((row) =>
      row.id === updated.id ? updated : row,
    )
  }

  function patchSupplier(updated: Supplier) {
    suppliers.value = suppliers.value.map((row) => (row.id === updated.id ? updated : row))
  }

  function reset() {
    branches.value = []
    branchContextLoaded.value = false
    selectedBranchContext.value = null
    settings.value = null
    managedBranches.value = []
    selectedBranch.value = null
    selectedBranchPricing.value = null
    catalogOptions.value = []
    catalogOptionsTotal.value = 0
    catalogFilters.value = { manufacturers: [] }
    branchMaterials.value = []
    suppliers.value = []
    stockItems.value = []
    lowStockItems.value = []
    stockTransactions.value = []
    stockTransactionsHasMore.value = false
    users.value = []
    selectedUser.value = null
    sessions.value = []
    lastTempPassword.value = null
    loading.value = false
    catalogLoading.value = false
    setupLoading.value = false
    inventoryLoading.value = false
    error.value = null
    catalogError.value = null
    setupError.value = null
    inventoryError.value = null
    traceId.value = null
    catalogTraceId.value = null
    setupTraceId.value = null
    inventoryTraceId.value = null
    actionError.value = null
    actionTraceId.value = null
    usersLoadRequestId += 1
    catalogLoadRequestId += 1
  }

  return {
    branches,
    selectedBranchContext,
    settings,
    managedBranches,
    selectedBranch,
    selectedBranchPricing,
    catalogOptions,
    catalogOptionsTotal,
    catalogFilters,
    branchMaterials,
    branchMaterialsHasMore,
    suppliers,
    stockItems,
    lowStockItems,
    stockValueTiyin,
    stockTransactions,
    stockTransactionsHasMore,
    supplierInvoices,
    users,
    selectedUser,
    sessions,
    lastTempPassword,
    loading,
    catalogLoading,
    setupLoading,
    inventoryLoading,
    error,
    catalogError,
    setupError,
    inventoryError,
    traceId,
    catalogTraceId,
    setupTraceId,
    inventoryTraceId,
    actionError,
    actionTraceId,
    setSelectedBranchContext,
    loadBranchContext,
    loadSettings,
    updateSettings,
    loadManagedBranches,
    createBranch,
    loadBranch,
    updateBranch,
    setBranchStatus,
    updateBranchPricing,
    loadCatalogOptions,
    fetchCatalogOptions,
    loadCatalogFilters,
    loadBranchMaterials,
    attachBranchMaterials,
    updateBranchMaterial,
    setBranchMaterialStatus,
    loadStock,
    loadLowStock,
    loadStockValue,
    loadStockTransactions,
    loadSuppliers,
    loadSupplierInvoices,
    loadInventory,
    clearInventory,
    createSupplier,
    updateSupplier,
    setSupplierStatus,
    fetchMaterialLastPrice,
    createSupplierInvoice,
    recordStockIn,
    recordAdjustment,
    loadUsers,
    createUser,
    loadUser,
    updateUser,
    replaceGrants,
    resetPassword,
    blockUser,
    unblockUser,
    revokeUserSessions,
    revokeUserSession,
    reset,
  }
})
