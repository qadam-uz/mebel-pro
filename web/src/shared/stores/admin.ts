import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiTraceId } from '@/shared/api/client'
import { useAuthStore } from '@/shared/stores/auth'

export type MaterialStatus = 'active' | 'inactive'
export type MaterialKind = 'panel' | 'edge'
export type PanelMaterialType = 'dsp' | 'mdf' | 'plywood' | 'natural_wood' | 'other'

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

export interface Manufacturer {
  id: string
  name: string
  country: string | null
  note: string | null
  status: MaterialStatus
  created_at: string
  updated_at: string
}

export interface Material {
  id: string
  kind: MaterialKind
  manufacturer_id: string
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
  status: MaterialStatus
  created_at: string
  updated_at: string
}

export interface CatalogFilters {
  search?: string
  status?: MaterialStatus | null
  kind?: MaterialKind | null
  manufacturer_id?: string | null
}

function withQuery(path: string, params: Record<string, string | null | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value)
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

export const useAdminStore = defineStore('admin', () => {
  const workshops = ref<WorkshopSummary[]>([])
  const detail = ref<PlatformWorkshopDetail | null>(null)
  const lastProvision = ref<ProvisionWorkshopResponse | null>(null)
  const manufacturers = ref<Manufacturer[]>([])
  const materials = ref<Material[]>([])
  const loading = ref(false)
  const catalogLoading = ref(false)
  const error = ref<string | null>(null)
  const catalogError = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const catalogTraceId = ref<string | null>(null)
  const auth = useAuthStore()

  function authInit() {
    return { accessToken: auth.accessToken }
  }

  async function loadWorkshops() {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      workshops.value = await api.get<WorkshopSummary[]>('/platform/workshops', authInit())
    } catch (errorValue) {
      error.value = 'workshops_load_failed'
      traceId.value = apiTraceId(errorValue)
    } finally {
      loading.value = false
    }
  }

  async function loadWorkshop(id: string) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      detail.value = await api.get<PlatformWorkshopDetail>(`/platform/workshops/${id}`, authInit())
    } catch (errorValue) {
      error.value = 'workshop_load_failed'
      traceId.value = apiTraceId(errorValue)
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

  async function loadManufacturers(filters: CatalogFilters = {}) {
    catalogLoading.value = true
    catalogError.value = null
    catalogTraceId.value = null
    try {
      manufacturers.value = await api.get<Manufacturer[]>(
        withQuery('/platform/catalog/manufacturers', {
          search: filters.search,
          status: filters.status,
        }),
        authInit(),
      )
    } catch (errorValue) {
      catalogError.value = 'manufacturers_load_failed'
      catalogTraceId.value = apiTraceId(errorValue)
    } finally {
      catalogLoading.value = false
    }
  }

  async function loadMaterials(filters: CatalogFilters = {}) {
    catalogLoading.value = true
    catalogError.value = null
    catalogTraceId.value = null
    try {
      materials.value = await api.get<Material[]>(
        withQuery('/platform/catalog/materials', {
          search: filters.search,
          status: filters.status,
          kind: filters.kind,
          manufacturer_id: filters.manufacturer_id,
        }),
        authInit(),
      )
    } catch (errorValue) {
      catalogError.value = 'materials_load_failed'
      catalogTraceId.value = apiTraceId(errorValue)
    } finally {
      catalogLoading.value = false
    }
  }

  async function createManufacturer(payload: unknown) {
    const created = await api.post<Manufacturer>(
      '/platform/catalog/manufacturers',
      payload,
      authInit(),
    )
    manufacturers.value = [created, ...manufacturers.value]
    return created
  }

  async function updateManufacturer(id: string, payload: unknown) {
    const updated = await api.patch<Manufacturer>(
      `/platform/catalog/manufacturers/${id}`,
      payload,
      authInit(),
    )
    patchManufacturer(updated)
    return updated
  }

  async function setManufacturerStatus(id: string, status: MaterialStatus) {
    const updated = await api.post<Manufacturer>(
      `/platform/catalog/manufacturers/${id}/${status === 'active' ? 'activate' : 'deactivate'}`,
      undefined,
      authInit(),
    )
    patchManufacturer(updated)
    return updated
  }

  async function createMaterial(payload: unknown) {
    const created = await api.post<Material>('/platform/catalog/materials', payload, authInit())
    materials.value = [created, ...materials.value]
    return created
  }

  async function updateMaterial(id: string, payload: unknown) {
    const updated = await api.patch<Material>(
      `/platform/catalog/materials/${id}`,
      payload,
      authInit(),
    )
    patchMaterial(updated)
    return updated
  }

  async function setMaterialStatus(id: string, status: MaterialStatus) {
    const updated = await api.post<Material>(
      `/platform/catalog/materials/${id}/${status === 'active' ? 'activate' : 'deactivate'}`,
      undefined,
      authInit(),
    )
    patchMaterial(updated)
    return updated
  }

  function patchManufacturer(updated: Manufacturer) {
    manufacturers.value = manufacturers.value.map((row) => (row.id === updated.id ? updated : row))
  }

  function patchMaterial(updated: Material) {
    materials.value = materials.value.map((row) => (row.id === updated.id ? updated : row))
  }

  return {
    workshops,
    detail,
    lastProvision,
    manufacturers,
    materials,
    loading,
    catalogLoading,
    error,
    catalogError,
    traceId,
    catalogTraceId,
    loadWorkshops,
    loadWorkshop,
    provision,
    blockWorkshop,
    unblockWorkshop,
    loadManufacturers,
    loadMaterials,
    createManufacturer,
    updateManufacturer,
    setManufacturerStatus,
    createMaterial,
    updateMaterial,
    setMaterialStatus,
  }
})
