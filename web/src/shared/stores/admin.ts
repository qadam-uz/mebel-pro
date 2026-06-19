import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { api, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
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

export interface PlatformOverview {
  workshops_total: number
  workshops_active: number
  workshops_blocked: number
  branches_total: number
  clients_total: number
  platform_users_active: number
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

export type PlatformUserStatus = 'active' | 'blocked'
export type JobRunStatus = 'running' | 'ok' | 'failed' | 'skipped'
export type ErrorRecordStatus = 'open' | 'resolved'

export interface PlatformUser {
  id: string
  login: string
  full_name: string
  phone: string
  status: PlatformUserStatus
  password_reset_required: boolean
  failed_login_count: number
  locked_until: string | null
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface PlatformUserTempPasswordResponse {
  user: PlatformUser
  temp_password: string
}

export interface JobDefinition {
  id: string
  name: string
  schedule: string
  enabled: boolean
  running: boolean
  last_run_at: string | null
  last_result: JobRunStatus | null
  updated_at: string
}

export interface JobRun {
  id: string
  job_definition_id: string | null
  job_name: string
  status: JobRunStatus
  started_at: string
  finished_at: string | null
  brief_log: string | null
  error_code: string | null
  error_message: string | null
  trace_id: string | null
}

export interface PlatformJobSummary {
  definition: JobDefinition
  recent_runs: JobRun[]
}

export interface ErrorRecord {
  id: string
  code: string
  module: string
  status: ErrorRecordStatus
  count_24h: number
  count_7d: number
  last_occurred_at: string | null
  preview_message: string | null
  resolved_by_user_id: string | null
  resolved_at: string | null
  created_at: string
  updated_at: string
}

export interface ErrorOccurrence {
  id: string
  error_record_id: string
  trace_id: string
  message: string
  stack: string | null
  context: Record<string, unknown> | null
  workshop_id: string | null
  user_id: string | null
  occurred_at: string
}

export interface ErrorRecordDetail {
  record: ErrorRecord
  occurrences: ErrorOccurrence[]
}

export interface ActionLog {
  id: string
  actor_type: 'platform_user' | 'workshop_user' | 'client' | 'system'
  actor_user_id: string | null
  actor_client_id: string | null
  workshop_id: string | null
  branch_id: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  summary: string | null
  details: Record<string, unknown> | null
  trace_id: string
  created_at: string
}

export interface StatusChangeLog {
  id: string
  entity_type: string
  entity_id: string
  workshop_id: string | null
  branch_id: string | null
  from_status: string | null
  to_status: string
  actor_type: 'platform_user' | 'workshop_user' | 'client' | 'system'
  actor_user_id: string | null
  actor_client_id: string | null
  reason: string | null
  action_log_id: string | null
  changed_at: string
}

export interface CatalogFilters {
  search?: string
  status?: MaterialStatus | null
  kind?: MaterialKind | null
  manufacturer_id?: string | null
}

// AB-29: typed request payloads for the privileged write paths (was `unknown`).
export interface ProvisionWorkshopRequest {
  workshop: { name: string; code: string | null; phone: string; address: string | null }
  branch: {
    name: string
    address: string
    phone: string
    latitude: string
    longitude: string
    working_hours: Record<string, { open: string | null; close: string | null }>
  }
  owner: { full_name: string; login: string; phone: string }
  temp_password?: string
}

export interface ManufacturerWriteRequest {
  name: string
  country: string | null
  note: string | null
}

export interface MaterialWriteRequest {
  kind: MaterialKind
  manufacturer_id: string
  type: PanelMaterialType | null
  name: string
  thickness_mm: string
  color: string
  decor_code: string | null
  panel_length_mm: number | null
  panel_width_mm: number | null
  grain_direction: boolean | null
  image_file_id: string | null
}

export interface PlatformUserCreateRequest {
  full_name: string
  login: string
  phone: string
  temp_password: string | null
}

export interface PlatformUserUpdateRequest {
  full_name?: string
  phone?: string
}

export const useAdminStore = defineStore('admin', () => {
  const workshops = ref<WorkshopSummary[]>([])
  const detail = ref<PlatformWorkshopDetail | null>(null)
  const overview = ref<PlatformOverview | null>(null)
  const lastProvision = ref<ProvisionWorkshopResponse | null>(null)
  const manufacturers = ref<Manufacturer[]>([])
  const materials = ref<Material[]>([])
  const platformUsers = ref<PlatformUser[]>([])
  const lastPlatformUserSecret = ref<PlatformUserTempPasswordResponse | null>(null)
  const jobs = ref<PlatformJobSummary[]>([])
  const errors = ref<ErrorRecord[]>([])
  const errorDetail = ref<ErrorRecordDetail | null>(null)
  const auditActions = ref<ActionLog[]>([])
  const auditStatusChanges = ref<StatusChangeLog[]>([])
  const loading = ref(false)
  const catalogLoading = ref(false)
  const opsLoading = ref(false)
  const error = ref<string | null>(null)
  const catalogError = ref<string | null>(null)
  const opsError = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const catalogTraceId = ref<string | null>(null)
  const opsTraceId = ref<string | null>(null)

  // AB-03: the one-time provision / temp-password secrets must not outlive the
  // session. They linger on `lastProvision` / `lastPlatformUserSecret` so a view
  // can render them once; clear them explicitly (modal close / unmount) and,
  // defensively, the moment auth is dropped (logout / "log out everywhere" /
  // session-expiry all null the access token).
  function clearSecrets() {
    lastProvision.value = null
    lastPlatformUserSecret.value = null
  }

  const auth = useAuthStore()
  watch(
    () => auth.accessToken,
    (token) => {
      if (!token) clearSecrets()
    },
  )

  async function loadWorkshops() {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      workshops.value = await api.get<WorkshopSummary[]>('/platform/workshops', authInit())
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'workshops_load_failed')
      error.value = captured.code
      traceId.value = captured.traceId
    } finally {
      loading.value = false
    }
  }

  async function loadOverview() {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      overview.value = await api.get<PlatformOverview>('/platform/overview', authInit())
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'overview_load_failed')
      error.value = captured.code
      traceId.value = captured.traceId
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
      const captured = captureApiError(errorValue, 'workshop_load_failed')
      error.value = captured.code
      traceId.value = captured.traceId
    } finally {
      loading.value = false
    }
  }

  async function provision(payload: ProvisionWorkshopRequest) {
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
      // Preserve a 403 as permission_denied so AdminManufacturersView /
      // AdminMaterialsView render the no-access AdminErrorState (AB-01/AB-08),
      // instead of masking it as a generic load failure (CB-100).
      const captured = captureApiError(errorValue, 'manufacturers_load_failed')
      catalogError.value = captured.code
      catalogTraceId.value = captured.traceId
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
      const captured = captureApiError(errorValue, 'materials_load_failed')
      catalogError.value = captured.code
      catalogTraceId.value = captured.traceId
    } finally {
      catalogLoading.value = false
    }
  }

  async function createManufacturer(payload: ManufacturerWriteRequest) {
    const created = await api.post<Manufacturer>(
      '/platform/catalog/manufacturers',
      payload,
      authInit(),
    )
    manufacturers.value = [created, ...manufacturers.value]
    return created
  }

  async function updateManufacturer(id: string, payload: ManufacturerWriteRequest) {
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

  async function createMaterial(payload: MaterialWriteRequest) {
    const created = await api.post<Material>('/platform/catalog/materials', payload, authInit())
    materials.value = [created, ...materials.value]
    return created
  }

  async function updateMaterial(id: string, payload: MaterialWriteRequest) {
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
    // AB-16: materials carry a denormalized manufacturer_name; refresh it so a
    // rename doesn't leave stale labels on the cached materials list/filter.
    materials.value = materials.value.map((row) =>
      row.manufacturer_id === updated.id ? { ...row, manufacturer_name: updated.name } : row,
    )
  }

  function patchMaterial(updated: Material) {
    materials.value = materials.value.map((row) => (row.id === updated.id ? updated : row))
  }

  async function loadPlatformUsers() {
    opsLoading.value = true
    opsError.value = null
    opsTraceId.value = null
    try {
      platformUsers.value = await api.get<PlatformUser[]>('/platform/users', authInit())
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'platform_users_load_failed')
      opsError.value = captured.code
      opsTraceId.value = captured.traceId
    } finally {
      opsLoading.value = false
    }
  }

  async function createPlatformUser(payload: PlatformUserCreateRequest) {
    lastPlatformUserSecret.value = await api.post<PlatformUserTempPasswordResponse>(
      '/platform/users',
      payload,
      authInit(),
    )
    // AB-34: the list is server-sorted by (status, full_name); insert the new
    // user in that order rather than unshifting, so it doesn't jump to the top
    // and then visibly relocate after the next reload.
    platformUsers.value = [...platformUsers.value, lastPlatformUserSecret.value.user].sort(
      (a, b) => a.status.localeCompare(b.status) || a.full_name.localeCompare(b.full_name),
    )
    return lastPlatformUserSecret.value
  }

  async function updatePlatformUser(id: string, payload: PlatformUserUpdateRequest) {
    const updated = await api.patch<PlatformUser>(`/platform/users/${id}`, payload, authInit())
    patchPlatformUser(updated)
    return updated
  }

  async function resetPlatformUserPassword(id: string) {
    lastPlatformUserSecret.value = await api.post<PlatformUserTempPasswordResponse>(
      `/platform/users/${id}/reset-password`,
      undefined,
      authInit(),
    )
    patchPlatformUser(lastPlatformUserSecret.value.user)
    return lastPlatformUserSecret.value
  }

  async function blockPlatformUser(id: string, reason: string) {
    const updated = await api.post<PlatformUser>(
      `/platform/users/${id}/block`,
      { reason },
      authInit(),
    )
    patchPlatformUser(updated)
    return updated
  }

  async function unblockPlatformUser(id: string) {
    const updated = await api.post<PlatformUser>(
      `/platform/users/${id}/unblock`,
      undefined,
      authInit(),
    )
    patchPlatformUser(updated)
    return updated
  }

  function patchPlatformUser(updated: PlatformUser) {
    platformUsers.value = platformUsers.value.map((row) => (row.id === updated.id ? updated : row))
  }

  async function loadJobs() {
    opsLoading.value = true
    opsError.value = null
    opsTraceId.value = null
    try {
      jobs.value = await api.get<PlatformJobSummary[]>('/platform/jobs', authInit())
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'jobs_load_failed')
      opsError.value = captured.code
      opsTraceId.value = captured.traceId
    } finally {
      opsLoading.value = false
    }
  }

  async function runJob(name: string) {
    const run = await api.post<JobRun>(`/platform/jobs/${name}/run`, undefined, authInit())
    const row = jobs.value.find((job) => job.definition.name === name)
    if (row) {
      // AB-15: a `skipped` run (job already running) does NOT update the
      // definition's last_run_at/last_result server-side, so only mirror a
      // terminal result optimistically — otherwise we'd overwrite a real
      // `failed` with `skipped` and silently drop it from the dashboard KPI.
      if (run.status === 'ok' || run.status === 'failed') {
        row.definition.last_run_at = run.started_at
        row.definition.last_result = run.status
      }
      row.recent_runs = [run, ...row.recent_runs].slice(0, 5)
    }
    return run
  }

  async function loadErrors() {
    opsLoading.value = true
    opsError.value = null
    opsTraceId.value = null
    try {
      errors.value = await api.get<ErrorRecord[]>('/platform/errors', authInit())
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'errors_load_failed')
      opsError.value = captured.code
      opsTraceId.value = captured.traceId
    } finally {
      opsLoading.value = false
    }
  }

  async function loadErrorDetail(id: string) {
    errorDetail.value = await api.get<ErrorRecordDetail>(`/platform/errors/${id}`, authInit())
    patchError(errorDetail.value.record)
    return errorDetail.value
  }

  async function resolveError(id: string) {
    const updated = await api.post<ErrorRecord>(
      `/platform/errors/${id}/resolve`,
      undefined,
      authInit(),
    )
    patchError(updated)
    if (errorDetail.value?.record.id === id) errorDetail.value.record = updated
    return updated
  }

  function patchError(updated: ErrorRecord) {
    errors.value = errors.value.map((row) => (row.id === updated.id ? updated : row))
  }

  async function loadAudit() {
    opsLoading.value = true
    opsError.value = null
    opsTraceId.value = null
    // AB-32: settle each feed independently so a transient failure on ONE feed
    // doesn't blank both tabs; only show the full-screen error when both fail.
    const [actionsResult, statusResult] = await Promise.allSettled([
      api.get<ActionLog[]>('/platform/audit/actions', authInit()),
      api.get<StatusChangeLog[]>('/platform/audit/status-changes', authInit()),
    ])
    if (actionsResult.status === 'fulfilled') auditActions.value = actionsResult.value
    if (statusResult.status === 'fulfilled') auditStatusChanges.value = statusResult.value
    if (actionsResult.status === 'rejected' && statusResult.status === 'rejected') {
      const captured = captureApiError(actionsResult.reason, 'audit_load_failed')
      opsError.value = captured.code
      opsTraceId.value = captured.traceId
    }
    opsLoading.value = false
  }

  function reset() {
    workshops.value = []
    detail.value = null
    overview.value = null
    lastProvision.value = null
    manufacturers.value = []
    materials.value = []
    platformUsers.value = []
    lastPlatformUserSecret.value = null
    jobs.value = []
    errors.value = []
    errorDetail.value = null
    auditActions.value = []
    auditStatusChanges.value = []
    loading.value = false
    catalogLoading.value = false
    opsLoading.value = false
    error.value = null
    catalogError.value = null
    opsError.value = null
    traceId.value = null
    catalogTraceId.value = null
    opsTraceId.value = null
  }

  return {
    workshops,
    detail,
    overview,
    clearSecrets,
    lastProvision,
    manufacturers,
    materials,
    platformUsers,
    lastPlatformUserSecret,
    jobs,
    errors,
    errorDetail,
    auditActions,
    auditStatusChanges,
    loading,
    catalogLoading,
    opsLoading,
    error,
    catalogError,
    opsError,
    traceId,
    catalogTraceId,
    opsTraceId,
    loadWorkshops,
    loadOverview,
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
    loadPlatformUsers,
    createPlatformUser,
    updatePlatformUser,
    resetPlatformUserPassword,
    blockPlatformUser,
    unblockPlatformUser,
    loadJobs,
    runJob,
    loadErrors,
    loadErrorDetail,
    resolveError,
    loadAudit,
    reset,
  }
})
