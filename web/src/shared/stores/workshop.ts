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
  INVENTORY_INVOICE_PAGE_LIMIT,
  INVENTORY_TX_PAGE_LIMIT,
  MATERIALS_PAGE_LIMIT,
} from '@/shared/app/constants'
import type { Decor, DecorFormat, DecorType, MaterialStatus } from '@/shared/stores/admin'
import { useAuthStore, type SessionResponse } from '@/shared/stores/auth'

export type BranchStatus = 'active' | 'temporarily_closed' | 'inactive'
export type SupplierStatus = 'active' | 'inactive'
export type StockTransactionType =
  | 'stock_in'
  // The reversal a voided arrival document writes, one per line.
  | 'stock_in_void'
  | 'consume'
  | 'restore'
  | 'adjust'

/** Which production surface a branch's orders offer (orders.md). `simple`
 *  collapses the floor to one Tayyor tap; `full` keeps assignment, starts and
 *  per-stage completion. Read at action time — never stamped on an order. */
export type ProductionMode = 'simple' | 'full'

export interface BranchContextItem {
  id: string
  name: string
  address: string
  phone: string
  status: 'active' | 'temporarily_closed'
  closed_reason: string | null
  kerf_mm: number
  edge_trim_mm: number
  edge_overhang_mm: number
  own_material_allowed: boolean
  production_mode: ProductionMode
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
  // Read-only, machine-generated, permanent: the code behind `/w/{code}` that
  // the "Mijoz havolasi" card prints. There is no write path for it.
  public_code: string
  status: 'active' | 'blocked'
  currency: 'UZS'
  owner_user_id: string
  created_at: string
  updated_at: string
}

export interface ManagedBranch {
  id: string
  workshop_id: string
  // Read-only, carried on every branch read so the branch screen can print
  // `/w/{code}/{branch_no}` without a second request.
  workshop_public_code: string
  // Platform-wide branch number, assigned at creation and immutable — the last
  // segment of the branch's own QR link, `/w/{code}/{branch_no}` (QAD-146).
  // Read-only: it is never sent back in a create or patch payload. Order
  // numbers do not carry it (sales.md — six random platform-wide digits).
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
  edge_overhang_mm: number
  own_material_allowed: boolean
  production_mode: ProductionMode
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
 * THE material: a decor in one concrete format, owned by one branch. Identity is
 * nested under `.decor`; the format lives here. There is no stored name — render
 * `label`, which the server composes (backend/app/core/material_label.py).
 */
export interface BranchMaterial {
  id: string
  branch_id: string
  decor_format_id: string
  // One nesting level each, never flattened: `decor_format.thickness_mm` says
  // WHERE the number is owned — the platform, not this branch — which is the
  // whole point of the format reshape.
  decor_format: DecorFormat
  decor: Decor
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

// A decor the branch may attach. It is never hidden once carried — carrying 18 mm
// does not stop you adding 16 mm — so the count says how many formats are already in.
export interface BranchCatalogOption {
  decor: Decor
  carried_format_count: number
  // Active formats the platform offers for this decor. `carried === available`
  // is what the picker greys out as "nothing left to add".
  available_format_count: number
}

/** One active format in step two of the attach sheet, with the branch's answer. */
export interface BranchCatalogFormatOption {
  decor_format: DecorFormat
  // Carried rows stay in the list, disabled. Hiding them would leave the branch
  // wondering whether the size exists at all — the exact question step two is
  // there to answer.
  carried: boolean
}

// QAD-159: the picker needs an honest "Filtrdagi hammasi (N)" count, so this
// endpoint returns the page plus the total matching the same filters.
export interface BranchCatalogOptionsPage {
  items: BranchCatalogOption[]
  total: number
}

// Manufacturers only. Thickness used to be a facet here because it was a
// platform-catalog fact; it is now a per-branch format the operator types in, so
// there is nothing left to enumerate. `type` is a fixed enum rendered without asking.
export interface BranchCatalogFilters {
  manufacturers: { id: string; name: string }[]
}

/**
 * Which set a facet enumerates, and the two are not interchangeable.
 *
 * `attachable` is the platform's offer — the attach sheet's question. `carried`
 * is what this branch already holds, which is the only honest set for a filter
 * over the branch's own table: the platform list would offer manufacturers that
 * match no row on screen.
 */
export type BranchCatalogFacetScope = 'attachable' | 'carried'

/** One (thickness + size) combination of a decor a branch wants to carry. */
/** One platform format the branch wants to carry, with its own numbers. */
export interface BranchMaterialAttachItem {
  decor_format_id: string
  // Both optional server-side, defaulting to 0: a branch routinely registers its
  // whole list before it knows prices.
  price_tiyin?: number
  min_stock?: number
}

/**
 * Carry several platform formats in ONE transaction.
 *
 * A flat list of format ids rather than decor-then-formats: the branch no
 * longer invents formats, so there is nothing per-decor left to nest — a format
 * id already names its decor.
 */
export interface BranchMaterialAttachRequest {
  items: BranchMaterialAttachItem[]
}

export interface BranchMaterialAttachResponse {
  created: BranchMaterial[]
  // Format ids this branch already carries. The picker shows what is carried, so
  // a duplicate here is a race, not user error — surface it as "already carried,
  // skipped", never as a failure.
  skipped: string[]
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
  type: DecorType
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
  invoice_id: string | null
  invoice_no: string | null
  // Server-composed label, not a stored column — leave it alone.
  material_name: string
  type: StockTransactionType
  quantity: number
  balance_after: number
  unit_price_tiyin: number | null
  total_price_tiyin: number | null
  order_id: string | null
  // The order's own number — a consume/restore row's context has to
  // be a document the reader recognises, not an id prefix.
  order_number: string | null
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
  type: DecorType
  display_unit: string
  quantity: number
  unit_price_tiyin: number | null
  total_price_tiyin: number | null
  note: string | null
}

export type LedgerStatus = 'recorded' | 'voided'

export interface SupplierInvoicePayment {
  expense_id: string
  spent_on: string
  amount_tiyin: number
  status: LedgerStatus
}

export interface SupplierInvoice {
  id: string
  workshop_id: string
  branch_id: string
  branch_name: string | null
  supplier_id: string | null
  supplier_name: string | null
  invoice_no: string
  // The number on the supplier's own paper — free text, not the `K-…` we mint.
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
  status: LedgerStatus
  voided_reason: string | null
  voided_at: string | null
  voided_by_name: string | null
  recorded_by_user_id: string
  recorded_by_name: string | null
  created_at: string
  lines: SupplierInvoiceLine[]
  // Only the single-invoice read fills this; list rows carry an empty array.
  payments: SupplierInvoicePayment[]
}

export interface SupplierInvoiceFilters {
  supplier_id?: string | null
  search?: string | null
  payment_status?: InvoicePaymentStatus | null
  date_from?: string | null
  date_to?: string | null
  limit?: number
  offset?: number
}

export interface SupplierInvoiceLineInput {
  branch_material_id: string
  quantity: number
  unit_price_tiyin: number
}

/**
 * The correction an invoice accepts. `lines` omitted is a header-only edit;
 * `lines` present is the FULL desired set — the server rewrites the invoice's
 * stock-in rows to match and replays each touched material's balance chain.
 *
 * `note` / `discount_tiyin` / `surcharge_tiyin` are gone: the server refuses
 * them outright, so they must not reappear here.
 */
export interface SupplierInvoicePatch {
  supplier_id?: string | null
  invoice_date?: string | null
  lines?: SupplierInvoiceLineInput[]
}

export interface StockLastPrice {
  unit_price_tiyin: number | null
  recorded_at: string | null
  supplier_id: string | null
  supplier_name: string | null
}

export interface StockListFilters {
  search?: string
  low_stock?: boolean | null
  // Restrict to rows with at least one movement — the Zaxira table's default
  // scope, and nothing else's: the pickers and the global search preview must
  // keep seeing the branch's whole catalog.
  moved_only?: boolean
  /**
   * The decor types to list — panels and kromka share a shelf but not a
   * question. Plural because one label can cover two enum members («LDSP»).
   */
  types?: DecorType[] | null
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
  type?: DecorType | null
  status?: MaterialStatus | null
  manufacturer_id?: string | null
  // Narrows the grouped-by-decor table to one decor's formats.
  decor_id?: string | null
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
  // Held apart from `catalogFilters` on purpose: the attach sheet opens *over*
  // the catalog page, and one shared ref would let the sheet's attachable set
  // silently replace the page filter's carried one underneath it.
  const carriedCatalogFilters = ref<BranchCatalogFilters>({ manufacturers: [] })
  const branchMaterials = ref<BranchMaterial[]>([])
  const branchMaterialsHasMore = ref(false)
  const suppliers = ref<Supplier[]>([])
  const stockItems = ref<StockItem[]>([])
  // The table's list and the pickers' list are two different questions. The
  // Zaxira table asks for the *moved* scope; a material combobox must offer the
  // whole branch catalog, or an arrival for a never-stocked material — the most
  // common first arrival there is — would be impossible to enter.
  const stockPickerItems = ref<StockItem[]>([])
  const stockPickerBranchId = ref<string | null>(null)
  const lowStockItems = ref<StockItem[]>([])
  const stockValueTiyin = ref<number | null>(null)
  const stockTransactions = ref<StockTransaction[]>([])
  const stockTransactionsHasMore = ref(false)
  const supplierInvoices = ref<SupplierInvoice[]>([])
  const supplierInvoicesHasMore = ref(false)
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
  let lastStockFilters: StockListFilters = {}

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

  // The "already loaded" guard below only covers callers that arrive *after* a
  // load finished. The shell and the dashboard both ask on startup, within the
  // same round trip of each other, so both saw `branchContextLoaded === false`
  // and both fetched. Sharing the in-flight promise makes concurrent callers
  // wait on one request instead of issuing their own.
  let branchContextInFlight: Promise<void> | null = null

  async function loadBranchContext(options: { force?: boolean } = {}) {
    if (branchContextLoaded.value && !options.force) return
    if (branchContextInFlight && !options.force) return branchContextInFlight
    const run = (async () => {
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
    })()
    branchContextInFlight = run
    try {
      await run
    } finally {
      // Cleared only if this run is still the current one, so a `force` reload
      // started meanwhile keeps its own promise available to later callers.
      if (branchContextInFlight === run) branchContextInFlight = null
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
  // catalog — so opening the sheet on the full decor set doesn't freeze. Returns
  // the page so a caller can render an honest "Filtrdagi hammasi (N)" without the
  // store holding more than the visible list.
  async function fetchCatalogOptions(id: string, filters: BranchMaterialFilters = {}) {
    return api.get<BranchCatalogOptionsPage>(
      withQuery(`/workshop/branches/${id}/catalog/decors`, {
        search: filters.search,
        type: filters.type,
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

  /**
   * Step two of the attach sheet: this decor's ACTIVE formats, carried flagged.
   *
   * Inactive formats are absent rather than disabled — the platform has said the
   * product is no longer made, so offering a branch the chance to start carrying
   * one would be offering a dead end.
   */
  async function fetchCatalogFormats(id: string, decorId: string) {
    return api.get<BranchCatalogFormatOption[]>(
      `/workshop/branches/${id}/catalog/decors/${decorId}/formats`,
      authInit(),
    )
  }

  async function loadCatalogFilters(id: string, scope: BranchCatalogFacetScope = 'attachable') {
    const page = await api.get<BranchCatalogFilters>(
      withQuery(`/workshop/branches/${id}/catalog/filters`, { scope }),
      authInit(),
    )
    if (scope === 'carried') carriedCatalogFilters.value = page
    else catalogFilters.value = page
    return page
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
          type: filters.type,
          manufacturer_id: filters.manufacturer_id,
          decor_id: filters.decor_id,
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
   * Attach several decors, each in one or more o'lchamlar, in one server-side
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
    await refreshStockCollections(id)
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
    await refreshStockCollections(id)
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

  async function loadStock(id: string, filters: StockListFilters = {}) {
    // Remembered so a mutation can refresh the table under the filters the
    // operator is actually looking at, instead of dropping them to unfiltered.
    lastStockFilters = filters
    stockItems.value = await readOrDrop(
      () =>
        api.get<StockItem[]>(
          withQuery(`/workshop/branches/${id}/stock`, {
            search: filters.search,
            low_stock: filters.low_stock ? true : undefined,
            moved_only: filters.moved_only ? true : undefined,
            types: filters.types ?? undefined,
          }),
          authInit(),
        ),
      () => {
        stockItems.value = []
      },
    )
  }

  /**
   * The unfiltered branch catalog behind every material combobox.
   *
   * Cached per branch — the pickers ask on every modal open, and the answer
   * only changes when stock or the catalog moves, which is exactly when
   * `invalidateStockPicker` is called.
   */
  async function loadStockPicker(id: string, options: { force?: boolean } = {}) {
    if (!options.force && stockPickerBranchId.value === id) return
    stockPickerItems.value = await readOrDrop(
      () => api.get<StockItem[]>(`/workshop/branches/${id}/stock`, authInit()),
      () => {
        stockPickerItems.value = []
        stockPickerBranchId.value = null
      },
    )
    stockPickerBranchId.value = id
  }

  // Every stock mutation moves a balance the pickers print in their meta line,
  // and may mint the very first movement for a row — so both collections are
  // stale together and are refreshed together.
  async function refreshStockCollections(id: string) {
    await loadStock(id, lastStockFilters).catch(() => undefined)
    if (stockPickerBranchId.value === id) {
      await loadStockPicker(id, { force: true }).catch(() => undefined)
    }
  }

  function patchStockItem(updated: StockItem) {
    const swap = (rows: StockItem[]) =>
      rows.map((row) => (row.branch_material_id === updated.branch_material_id ? updated : row))
    stockItems.value = swap(stockItems.value)
    stockPickerItems.value = swap(stockPickerItems.value)
  }

  /**
   * The low-stock threshold, written from the stock surface by `manage_inventory`.
   *
   * The same `branch_materials.min_stock` the catalog form edits — two doors,
   * one fact. The response is the refreshed row, patched in place so the open
   * detail modal re-derives its pill without a list reload.
   */
  /**
   * One material's balance row, addressed by the material alone.
   *
   * The material page is reached by URL — a link, a reload, a colleague's
   * message — so it cannot depend on the topbar already naming the right
   * branch. The server derives the branch from the material and checks the
   * reader against *that* branch.
   */
  async function fetchMaterialStock(branchMaterialId: string) {
    return api.get<StockItem>(`/workshop/inventory/materials/${branchMaterialId}/stock`, authInit())
  }

  async function updateStockMinStock(id: string, branchMaterialId: string, minStock: number) {
    const updated = await api.put<StockItem>(
      `/workshop/inventory/branches/${id}/stock/${branchMaterialId}/min-stock`,
      { min_stock: minStock },
      authInit(),
    )
    patchStockItem(updated)
    return updated
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

  /**
   * One page of movements, returned rather than stored.
   *
   * The material detail modal shows a material's own history while the
   * Tranzaksiyalar tab keeps whatever page and filters the operator left it on
   * — two readers of one endpoint, so only the tab owns `stockTransactions`.
   */
  async function fetchStockTransactions(id: string, filters: StockTransactionFilters = {}) {
    return api.get<StockTransaction[]>(
      withQuery(`/workshop/branches/${id}/stock-transactions`, {
        branch_material_id: filters.branch_material_id,
        date_from: filters.date_from,
        date_to: filters.date_to,
        limit: filters.limit ?? INVENTORY_TX_PAGE_LIMIT,
        offset: filters.offset ?? 0,
      }),
      authInit(),
    )
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
    const limit = filters.limit ?? INVENTORY_INVOICE_PAGE_LIMIT
    const offset = filters.offset ?? 0
    const page = await readOrDrop(
      () =>
        api.get<SupplierInvoice[]>(
          withQuery('/workshop/inventory/invoices', {
            branch_id: id,
            supplier_id: filters.supplier_id,
            search: filters.search,
            payment_status: filters.payment_status,
            date_from: filters.date_from,
            date_to: filters.date_to,
            limit,
            offset,
          }),
          authInit(),
        ),
      () => {
        supplierInvoices.value = []
        supplierInvoicesHasMore.value = false
      },
    )
    supplierInvoices.value = offset === 0 ? page : [...supplierInvoices.value, ...page]
    supplierInvoicesHasMore.value = page.length === limit
  }

  /** One arrival document with its lines and its linked payments. */
  async function fetchSupplierInvoice(invoiceId: string) {
    return api.get<SupplierInvoice>(`/workshop/inventory/invoices/${invoiceId}`, authInit())
  }

  // Header facts, and optionally the whole line set. A line edit moves stock
  // server-side, so the branch's balances are stale the moment this returns —
  // the caller refetches them.
  async function updateSupplierInvoice(invoiceId: string, payload: SupplierInvoicePatch) {
    const updated = await api.patch<SupplierInvoice>(
      `/workshop/inventory/invoices/${invoiceId}`,
      payload,
      authInit(),
    )
    patchSupplierInvoice(updated)
    return updated
  }

  // Reverses every line's stock server-side, so the branch's balances are stale
  // the moment this returns — the caller refetches them.
  async function voidSupplierInvoice(invoiceId: string, reason: string) {
    const voided = await api.post<SupplierInvoice>(
      `/workshop/inventory/invoices/${invoiceId}/void`,
      { reason },
      authInit(),
    )
    patchSupplierInvoice(voided)
    return voided
  }

  function patchSupplierInvoice(updated: SupplierInvoice) {
    supplierInvoices.value = supplierInvoices.value.map((row) =>
      row.id === updated.id ? updated : row,
    )
  }

  function clearInventory() {
    suppliers.value = []
    stockItems.value = []
    stockPickerItems.value = []
    stockPickerBranchId.value = null
    lowStockItems.value = []
    stockTransactions.value = []
    stockTransactionsHasMore.value = false
    supplierInvoices.value = []
    supplierInvoicesHasMore.value = false
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
    await refreshStockCollections(id)
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
    await refreshStockCollections(id)
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
    await refreshStockCollections(id)
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
    carriedCatalogFilters.value = { manufacturers: [] }
    branchMaterials.value = []
    suppliers.value = []
    stockItems.value = []
    stockPickerItems.value = []
    stockPickerBranchId.value = null
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
    // Exposed so a view can wait for the shell's branch pick before loading,
    // instead of loading once without it and again once it lands.
    branchContextLoaded,
    selectedBranchContext,
    settings,
    managedBranches,
    selectedBranch,
    selectedBranchPricing,
    catalogOptions,
    catalogOptionsTotal,
    catalogFilters,
    carriedCatalogFilters,
    branchMaterials,
    branchMaterialsHasMore,
    suppliers,
    stockItems,
    stockPickerItems,
    lowStockItems,
    stockValueTiyin,
    stockTransactions,
    stockTransactionsHasMore,
    supplierInvoices,
    supplierInvoicesHasMore,
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
    fetchCatalogFormats,
    loadCatalogFilters,
    loadBranchMaterials,
    attachBranchMaterials,
    updateBranchMaterial,
    setBranchMaterialStatus,
    loadStock,
    loadStockPicker,
    updateStockMinStock,
    fetchMaterialStock,
    loadLowStock,
    loadStockValue,
    loadStockTransactions,
    fetchStockTransactions,
    loadSuppliers,
    loadSupplierInvoices,
    fetchSupplierInvoice,
    updateSupplierInvoice,
    voidSupplierInvoice,
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
