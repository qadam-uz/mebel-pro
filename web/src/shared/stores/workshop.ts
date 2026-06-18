import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiTraceId, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import type { Material, MaterialKind, MaterialStatus } from '@/shared/stores/admin'
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
  permissions: string[]
}

export interface WorkshopUser {
  id: string
  workshop_id: string
  login: string
  full_name: string
  phone: string
  is_owner: boolean
  home_branch_id: string | null
  status: 'active' | 'blocked'
  password_reset_required: boolean
  grants: Array<{ permission: string; branch_id: string }>
}

export interface WorkshopSettings {
  id: string
  name: string
  code: string
  logo_file_id: string | null
  phone: string
  address: string | null
  status: 'active' | 'blocked'
  currency: 'UZS'
  owner_user_id: string
  created_at: string
  updated_at: string
}

export interface ManagedBranch {
  id: string
  workshop_id: string
  name: string
  address: string
  phone: string
  latitude: string
  longitude: string
  working_hours: Record<string, unknown>
  status: BranchStatus
  closed_reason: string | null
  active_orders_count: number
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

export interface BranchMaterial {
  id: string
  branch_id: string
  material_id: string
  material: Material
  price_tiyin: number
  min_stock: number
  status: MaterialStatus
  created_at: string
  updated_at: string
}

export interface BranchCatalogOption {
  material: Material
  already_selected: boolean
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
  material_id: string
  material: Material
  kind: MaterialKind
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
  material_id: string
  material_name: string
  type: StockTransactionType
  quantity: number
  balance_after: number
  order_id: string | null
  supplier_id: string | null
  supplier_name: string | null
  receipt_file_id: string | null
  actor_user_id: string | null
  note: string | null
  created_at: string
}

export interface BranchMaterialFilters {
  search?: string
  kind?: MaterialKind | null
  status?: MaterialStatus | null
  manufacturer_id?: string | null
}

export const permissionCatalog = [
  'view_dashboard',
  'manage_orders',
  'process_production',
  'manage_catalog',
  'manage_inventory',
  'manage_finance',
  'view_finance_reports',
] as const

export const useWorkshopStore = defineStore('workshop', () => {
  const branches = ref<BranchContextItem[]>([])
  const settings = ref<WorkshopSettings | null>(null)
  const managedBranches = ref<ManagedBranch[]>([])
  const selectedBranch = ref<ManagedBranch | null>(null)
  const selectedBranchPricing = ref<BranchPricing | null>(null)
  const catalogOptions = ref<BranchCatalogOption[]>([])
  const branchMaterials = ref<BranchMaterial[]>([])
  const suppliers = ref<Supplier[]>([])
  const stockItems = ref<StockItem[]>([])
  const stockTransactions = ref<StockTransaction[]>([])
  const users = ref<WorkshopUser[]>([])
  const selectedUser = ref<WorkshopUser | null>(null)
  const sessions = ref<SessionResponse[]>([])
  const lastTempPassword = ref<string | null>(null)
  const loading = ref(false)
  const setupLoading = ref(false)
  const inventoryLoading = ref(false)
  const error = ref<string | null>(null)
  const setupError = ref<string | null>(null)
  const inventoryError = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const setupTraceId = ref<string | null>(null)
  const inventoryTraceId = ref<string | null>(null)
  const auth = useAuthStore()
  let usersLoadRequestId = 0

  function upsertUser(user: WorkshopUser) {
    users.value = [...users.value.filter((current) => current.id !== user.id), user]
  }

  async function loadBranchContext() {
    error.value = null
    traceId.value = null
    try {
      const response = await api.get<{ branches: BranchContextItem[] }>(
        '/workshop/branch-context',
        authInit(),
      )
      branches.value = response.branches
    } catch (errorValue) {
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
    await loadBranchContext().catch(() => undefined)
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

  async function loadCatalogOptions(id: string, filters: BranchMaterialFilters = {}) {
    catalogOptions.value = await api.get<BranchCatalogOption[]>(
      withQuery(`/workshop/branches/${id}/catalog/materials`, {
        search: filters.search,
        kind: filters.kind,
        manufacturer_id: filters.manufacturer_id,
      }),
      authInit(),
    )
  }

  async function loadBranchMaterials(id: string, filters: BranchMaterialFilters = {}) {
    branchMaterials.value = await api.get<BranchMaterial[]>(
      withQuery(`/workshop/branches/${id}/materials`, {
        search: filters.search,
        kind: filters.kind,
        status: filters.status,
      }),
      authInit(),
    )
  }

  async function addBranchMaterial(id: string, payload: unknown) {
    const created = await api.post<BranchMaterial>(
      `/workshop/branches/${id}/materials`,
      payload,
      authInit(),
    )
    branchMaterials.value = [created, ...branchMaterials.value]
    await loadStock(id).catch(() => undefined)
    await loadCatalogOptions(id).catch(() => undefined)
    return created
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
    stockItems.value = await api.get<StockItem[]>(
      withQuery(`/workshop/branches/${id}/stock`, {
        search: filters.search,
        low_stock: filters.low_stock ? true : undefined,
      }),
      authInit(),
    )
  }

  async function loadStockTransactions(id: string, materialId?: string | null) {
    stockTransactions.value = await api.get<StockTransaction[]>(
      withQuery(`/workshop/branches/${id}/stock-transactions`, {
        material_id: materialId,
      }),
      authInit(),
    )
  }

  async function loadSuppliers(id: string, status?: SupplierStatus | null) {
    suppliers.value = await api.get<Supplier[]>(
      withQuery(`/workshop/branches/${id}/suppliers`, { status }),
      authInit(),
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

  async function loadUsers() {
    const requestId = ++usersLoadRequestId
    loading.value = true
    error.value = null
    traceId.value = null
    lastTempPassword.value = null
    try {
      const loadedUsers = await api.get<WorkshopUser[]>('/workshop/users', authInit())
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
    const response = await api.post<{ user: WorkshopUser; temp_password: string }>(
      '/workshop/users',
      payload,
      authInit(),
    )
    usersLoadRequestId += 1
    loading.value = false
    upsertUser(response.user)
    lastTempPassword.value = response.temp_password
    return response
  }

  async function loadUser(id: string) {
    loading.value = true
    error.value = null
    traceId.value = null
    lastTempPassword.value = null
    try {
      selectedUser.value = await api.get<WorkshopUser>(`/workshop/users/${id}`, authInit())
      sessions.value = (
        await api.get<{ sessions: SessionResponse[] }>(`/workshop/users/${id}/sessions`, authInit())
      ).sessions
    } catch (errorValue) {
      error.value = 'user_load_failed'
      traceId.value = apiTraceId(errorValue)
    } finally {
      loading.value = false
    }
  }

  async function replaceGrants(
    id: string,
    grants: Array<{ permission: string; branch_id: string }>,
  ) {
    error.value = null
    selectedUser.value = await api.put<WorkshopUser>(
      `/workshop/users/${id}/grants`,
      { grants },
      authInit(),
    )
  }

  async function resetPassword(id: string) {
    error.value = null
    const response = await api.post<{ user: WorkshopUser; temp_password: string }>(
      `/workshop/users/${id}/reset-password`,
      undefined,
      authInit(),
    )
    selectedUser.value = response.user
    lastTempPassword.value = response.temp_password
  }

  async function blockUser(id: string, reason: string) {
    error.value = null
    selectedUser.value = await api.post<WorkshopUser>(
      `/workshop/users/${id}/block`,
      { reason },
      authInit(),
    )
  }

  async function unblockUser(id: string) {
    error.value = null
    selectedUser.value = await api.post<WorkshopUser>(
      `/workshop/users/${id}/unblock`,
      undefined,
      authInit(),
    )
  }

  async function revokeUserSessions(id: string) {
    error.value = null
    await api.del(`/workshop/users/${id}/sessions`, authInit())
    sessions.value = []
  }

  async function revokeUserSession(id: string, sessionId: string) {
    error.value = null
    await api.del(`/workshop/users/${id}/sessions/${sessionId}`, authInit())
    sessions.value = sessions.value.filter((session) => session.id !== sessionId)
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

  return {
    branches,
    settings,
    managedBranches,
    selectedBranch,
    selectedBranchPricing,
    catalogOptions,
    branchMaterials,
    suppliers,
    stockItems,
    stockTransactions,
    users,
    selectedUser,
    sessions,
    lastTempPassword,
    loading,
    setupLoading,
    inventoryLoading,
    error,
    setupError,
    inventoryError,
    traceId,
    setupTraceId,
    inventoryTraceId,
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
    loadBranchMaterials,
    addBranchMaterial,
    updateBranchMaterial,
    setBranchMaterialStatus,
    loadStock,
    loadStockTransactions,
    loadSuppliers,
    loadInventory,
    createSupplier,
    updateSupplier,
    setSupplierStatus,
    recordStockIn,
    recordAdjustment,
    loadUsers,
    createUser,
    loadUser,
    replaceGrants,
    resetPassword,
    blockUser,
    unblockUser,
    revokeUserSessions,
    revokeUserSession,
  }
})
