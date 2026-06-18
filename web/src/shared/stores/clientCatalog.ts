import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiErrorCode, apiTraceId } from '@/shared/api/client'
import type { MaterialKind, PanelMaterialType } from '@/shared/stores/admin'
import { useAuthStore } from '@/shared/stores/auth'

export interface ClientBranch {
  branch_id: string
  workshop_id: string
  workshop_name: string
  workshop_logo_file_id: string | null
  branch_name: string
  address: string
  phone: string
  latitude: string
  longitude: string
  working_hours: Record<string, unknown>
  status: 'active' | 'temporarily_closed'
  closed_reason: string | null
}

export interface ClientBranchMaterial {
  id: string
  kind: MaterialKind
  manufacturer_name: string
  type: PanelMaterialType | null
  name: string
  thickness_mm: string
  color: string
  decor_code: string | null
  panel_length_mm: number | null
  panel_width_mm: number | null
  grain_direction: boolean | null
  image_file_id: string | null
  price_tiyin: number
  display_unit: string
}

function withQuery(path: string, params: Record<string, string | null | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value)
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

export const useClientCatalogStore = defineStore('clientCatalog', () => {
  const branches = ref<ClientBranch[]>([])
  const materials = ref<ClientBranchMaterial[]>([])
  const materialsByBranch = ref<Record<string, ClientBranchMaterial[]>>({})
  const selectedBranchId = ref<string | null>(null)
  const loading = ref(false)
  const materialsLoading = ref(false)
  const error = ref<string | null>(null)
  const materialsError = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const materialsTraceId = ref<string | null>(null)
  // Per-branch material-load error/trace so one failing branch doesn't blank the
  // whole list (CB-23).
  const branchMaterialsError = ref<Record<string, string | null>>({})
  const branchMaterialsTraceId = ref<Record<string, string | null>>({})
  const auth = useAuthStore()

  function authInit() {
    return { accessToken: auth.accessToken }
  }

  async function loadBranches(search?: string) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      branches.value = await api.get<ClientBranch[]>(
        withQuery('/client/branches', { search }),
        authInit(),
      )
      if (
        !selectedBranchId.value ||
        !branches.value.some((row) => row.branch_id === selectedBranchId.value)
      ) {
        selectedBranchId.value = branches.value[0]?.branch_id ?? null
      }
    } catch (errorValue) {
      error.value = 'client_branches_load_failed'
      traceId.value = apiTraceId(errorValue)
    } finally {
      loading.value = false
    }
  }

  async function loadMaterials(branchId: string, search?: string) {
    materialsLoading.value = true
    materialsError.value = null
    materialsTraceId.value = null
    selectedBranchId.value = branchId
    try {
      materials.value = await api.get<ClientBranchMaterial[]>(
        withQuery(`/client/branches/${branchId}/materials`, { search }),
        authInit(),
      )
      materialsByBranch.value = { ...materialsByBranch.value, [branchId]: materials.value }
    } catch (errorValue) {
      materialsError.value = 'client_materials_load_failed'
      materialsTraceId.value = apiTraceId(errorValue)
    } finally {
      materialsLoading.value = false
    }
  }

  async function loadMaterialsForBranch(branchId: string) {
    const rows = await api.get<ClientBranchMaterial[]>(
      withQuery(`/client/branches/${branchId}/materials`, {}),
      authInit(),
    )
    materialsByBranch.value = { ...materialsByBranch.value, [branchId]: rows }
    return rows
  }

  // Load several branches' materials concurrently but fault-tolerantly: one
  // branch failing records a per-branch error instead of rejecting the whole
  // batch and stranding every branch on "loading" (CB-23).
  async function loadMaterialsForBranchBatch(branchIds: string[]) {
    const results = await Promise.allSettled(
      branchIds.map(async (branchId) => ({
        branchId,
        rows: await loadMaterialsForBranch(branchId),
      })),
    )
    const nextErrors = { ...branchMaterialsError.value }
    const nextTraces = { ...branchMaterialsTraceId.value }
    results.forEach((result, index) => {
      const branchId = branchIds[index]
      if (!branchId) return
      if (result.status === 'fulfilled') {
        nextErrors[branchId] = null
        nextTraces[branchId] = null
      } else {
        nextErrors[branchId] = apiErrorCode(result.reason) ?? 'client_materials_load_failed'
        nextTraces[branchId] = apiTraceId(result.reason)
      }
    })
    branchMaterialsError.value = nextErrors
    branchMaterialsTraceId.value = nextTraces
  }

  return {
    branches,
    materials,
    materialsByBranch,
    selectedBranchId,
    loading,
    materialsLoading,
    error,
    materialsError,
    traceId,
    materialsTraceId,
    branchMaterialsError,
    branchMaterialsTraceId,
    loadBranches,
    loadMaterials,
    loadMaterialsForBranch,
    loadMaterialsForBranchBatch,
  }
})
