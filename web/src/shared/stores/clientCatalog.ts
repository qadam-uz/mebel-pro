import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'

export interface ClientBranchMaterialPreview {
  id: string
  manufacturer_name: string
  name: string
  price_tiyin: number
  display_unit: string
}

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
  // Inline material preview (CB-13) — the branches list is one request now.
  materials_preview: ClientBranchMaterialPreview[]
  materials_total: number
}

export const useClientCatalogStore = defineStore('clientCatalog', () => {
  const branches = ref<ClientBranch[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)

  async function loadBranches(search?: string) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      // The branch payload now carries an inline material preview (CB-13), so the
      // list is one request — the per-branch materials fetch + CB-23 fault-tolerant
      // batch were removed as dead code.
      branches.value = await api.get<ClientBranch[]>(
        withQuery('/client/branches', { search }),
        authInit(),
      )
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'client_branches_load_failed')
      error.value = captured.code
      traceId.value = captured.traceId
    } finally {
      loading.value = false
    }
  }

  function reset() {
    branches.value = []
    loading.value = false
    error.value = null
    traceId.value = null
  }

  return {
    branches,
    loading,
    error,
    traceId,
    loadBranches,
    reset,
  }
})
