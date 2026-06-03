import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '@/shared/api/client'
import { useAuthStore } from '@/shared/stores/auth'

export interface WorkshopSummary {
  id: string
  code: string
  name: string
  phone: string
  address: string | null
  status: 'active' | 'blocked'
  owner_user_id: string
  created_at: string
}

export interface ProvisionWorkshopResponse {
  workshop: WorkshopSummary
  branch: {
    id: string
    name: string
    address: string
    phone: string
    status: string
  }
  owner: {
    id: string
    login: string
    full_name: string
    phone: string
  }
  temp_password: string
}

export interface PlatformWorkshopDetail {
  workshop: WorkshopSummary
  branches: Array<{ id: string; name: string; status: string; address: string; phone: string }>
  owner: { id: string; login: string; full_name: string; phone: string }
}

export const useAdminStore = defineStore('admin', () => {
  const workshops = ref<WorkshopSummary[]>([])
  const detail = ref<PlatformWorkshopDetail | null>(null)
  const lastProvision = ref<ProvisionWorkshopResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const auth = useAuthStore()

  function authInit() {
    return { accessToken: auth.accessToken }
  }

  async function loadWorkshops() {
    loading.value = true
    error.value = null
    try {
      workshops.value = await api.get<WorkshopSummary[]>('/platform/workshops', authInit())
    } catch {
      error.value = 'workshops_load_failed'
    } finally {
      loading.value = false
    }
  }

  async function loadWorkshop(id: string) {
    loading.value = true
    error.value = null
    try {
      detail.value = await api.get<PlatformWorkshopDetail>(`/platform/workshops/${id}`, authInit())
    } catch {
      error.value = 'workshop_load_failed'
    } finally {
      loading.value = false
    }
  }

  async function provision(payload: unknown) {
    lastProvision.value = await api.post<ProvisionWorkshopResponse>(
      '/platform/workshops',
      payload,
      authInit(),
    )
    workshops.value = [lastProvision.value.workshop, ...workshops.value]
    return lastProvision.value
  }

  async function blockWorkshop(id: string, reason: string) {
    const updated = await api.post<WorkshopSummary>(
      `/platform/workshops/${id}/block`,
      { reason },
      authInit(),
    )
    patchWorkshop(updated)
  }

  async function unblockWorkshop(id: string) {
    const updated = await api.post<WorkshopSummary>(
      `/platform/workshops/${id}/unblock`,
      undefined,
      authInit(),
    )
    patchWorkshop(updated)
  }

  function patchWorkshop(updated: WorkshopSummary) {
    workshops.value = workshops.value.map((row) => (row.id === updated.id ? updated : row))
    if (detail.value?.workshop.id === updated.id) {
      detail.value = { ...detail.value, workshop: updated }
    }
  }

  return {
    workshops,
    detail,
    lastProvision,
    loading,
    error,
    loadWorkshops,
    loadWorkshop,
    provision,
    blockWorkshop,
    unblockWorkshop,
  }
})
