import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { api, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import { MATERIALS_PAGE_LIMIT } from '@/shared/app/constants'
import { useAuthStore } from '@/shared/stores/auth'

export type MaterialStatus = 'active' | 'inactive'
export type MaterialKind = 'panel' | 'edge'
export type PanelMaterialType = 'dsp' | 'mdf' | 'plywood' | 'natural_wood' | 'other'

export interface WorkshopSummary {
  id: string
  name: string
  status: 'active' | 'blocked'
  owner_user_id: string
  created_at: string
}

// AB-37: the workshops list adds the owner login and a branch count on top of the
// lean summary the single-object responses (provision/block/unblock) return.
export interface WorkshopListItem extends WorkshopSummary {
  owner_login: string
  branch_count: number
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
  }
  temp_password: string
}

export interface PlatformWorkshopDetail {
  workshop: WorkshopSummary
  branches: Array<{ id: string; name: string; status: string; address: string; phone: string }>
  owner: { id: string; login: string }
  // AB-20: the reason captured when the workshop was blocked (null when active).
  block_reason: string | null
}

export interface WorkshopOwnerTempPasswordResponse {
  owner: { id: string; login: string }
  temp_password: string
}

// AB-119: bucket counts, oldest first; the last entry is the current, partial
// period. Registrations carry no weekly rate — orders alone are weekly.
export interface SignupSpark {
  daily: number[]
  monthly: number[]
  yearly: number[]
}

export interface OrderSpark extends SignupSpark {
  weekly: number[]
}

export interface SignupMetrics {
  daily: number
  monthly: number
  yearly: number
  spark: SignupSpark
}

export interface OrderMetrics extends SignupMetrics {
  weekly: number
  spark: OrderSpark
}

export interface PlatformOverview {
  workshops_total: number
  workshops_active: number
  workshops_blocked: number
  branches_total: number
  clients_total: number
  platform_users_active: number
  orders: OrderMetrics
  workshop_signups: SignupMetrics
  client_signups: SignupMetrics
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
  edge_width_mm: number | null
  image_file_id: string | null
  status: MaterialStatus
  // AB-22: how many distinct branches carry this material (list responses only).
  branch_usage_count: number
  created_at: string
  updated_at: string
}

// Server-side material filters for the paginated platform catalog list. Omitted
// fields mean "no filter"; multi-selects go over as repeated query params.
export interface MaterialFilters {
  search?: string
  kind?: MaterialKind
  status?: MaterialStatus
  manufacturerIds?: string[]
  materialTypes?: PanelMaterialType[]
  offset?: number
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

// AB-29: typed request payloads for the privileged write paths (was `unknown`).
export interface ProvisionWorkshopRequest {
  workshop: { name: string }
  branch: {
    name: string
    address: string
    phone: string
    working_hours: Record<string, { open: string | null; close: string | null }>
  }
  owner: { login: string }
  temp_password?: string
}

export interface ManufacturerWriteRequest {
  name: string
  country: string | null
  note: string | null
}

interface MaterialWriteBase {
  manufacturer_id: string
  thickness_mm: string
  color: string
  decor_code: string | null
  image_file_id: string | null
}

export type MaterialWriteRequest =
  | (MaterialWriteBase & {
      kind: 'panel'
      type: PanelMaterialType
      panel_length_mm: number
      panel_width_mm: number
      grain_direction: boolean
    })
  | (MaterialWriteBase & {
      kind: 'edge'
      edge_width_mm: number
    })

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

type QueryValue = string | number | boolean | null | undefined

export interface AuditActionQuery extends Record<string, QueryValue> {
  workshop_id?: string
  branch_id?: string
  action?: string
  action_prefix?: string
  module?: string
  actor?: string
  entity_type?: string
  entity_id?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export interface AuditStatusQuery extends Record<string, QueryValue> {
  workshop_id?: string
  branch_id?: string
  entity_type?: string
  entity_id?: string
  from_status?: string
  to_status?: string
  actor?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export interface AuditLoadOptions {
  actions?: AuditActionQuery
  status?: AuditStatusQuery
  appendActions?: boolean
  appendStatus?: boolean
}

export const useAdminStore = defineStore('admin', () => {
  const workshops = ref<WorkshopListItem[]>([])
  const detail = ref<PlatformWorkshopDetail | null>(null)
  const overview = ref<PlatformOverview | null>(null)
  const lastProvision = ref<ProvisionWorkshopResponse | null>(null)
  const manufacturers = ref<Manufacturer[]>([])
  const materials = ref<Material[]>([])
  const platformUsers = ref<PlatformUser[]>([])
  const lastPlatformUserSecret = ref<PlatformUserTempPasswordResponse | null>(null)
  const lastOwnerSecret = ref<WorkshopOwnerTempPasswordResponse | null>(null)
  const jobs = ref<PlatformJobSummary[]>([])
  const errors = ref<ErrorRecord[]>([])
  const errorDetail = ref<ErrorRecordDetail | null>(null)
  const auditActions = ref<ActionLog[]>([])
  const auditStatusChanges = ref<StatusChangeLog[]>([])
  const loading = ref(false)
  const manufacturersLoading = ref(false)
  const materialsLoading = ref(false)
  const materialsHasMore = ref(false)
  const catalogLoading = computed(() => manufacturersLoading.value || materialsLoading.value)
  const opsLoading = ref(false)
  const error = ref<string | null>(null)
  const manufacturersError = ref<string | null>(null)
  const materialsError = ref<string | null>(null)
  const catalogError = computed(() => manufacturersError.value ?? materialsError.value)
  const opsError = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const manufacturersTraceId = ref<string | null>(null)
  const materialsTraceId = ref<string | null>(null)
  const catalogTraceId = computed(() => manufacturersTraceId.value ?? materialsTraceId.value)
  const opsTraceId = ref<string | null>(null)

  // AB-03: the one-time provision / temp-password secrets must not outlive the
  // session. They linger on `lastProvision` / `lastPlatformUserSecret` so a view
  // can render them once; clear them explicitly (modal close / unmount) and,
  // defensively, the moment auth is dropped (logout / "log out everywhere" /
  // session-expiry all null the access token).
  function clearSecrets() {
    lastProvision.value = null
    lastPlatformUserSecret.value = null
    lastOwnerSecret.value = null
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
      workshops.value = await api.get<WorkshopListItem[]>('/platform/workshops', authInit())
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
    // The provision response carries the lean WorkshopSummary; lift it to a list
    // item with the known owner login and the one branch just created, so the
    // dashboard/list show the AB-37 columns without waiting for a reload.
    const listed: WorkshopListItem = {
      ...lastProvision.value.workshop,
      owner_login: lastProvision.value.owner.login,
      branch_count: 1,
    }
    workshops.value = [listed, ...workshops.value]
    return lastProvision.value
  }

  async function blockWorkshop(id: string, reason: string) {
    const updated = await api.post<WorkshopSummary>(
      `/platform/workshops/${id}/block`,
      { reason },
      authInit(),
    )
    patchWorkshop(updated)
    // AB-20: surface the just-entered reason on the open detail immediately; a
    // reload re-reads the canonical (whitespace-normalized) value from the log.
    if (detail.value?.workshop.id === id) detail.value.block_reason = reason
  }

  async function unblockWorkshop(id: string) {
    const updated = await api.post<WorkshopSummary>(
      `/platform/workshops/${id}/unblock`,
      undefined,
      authInit(),
    )
    patchWorkshop(updated)
    if (detail.value?.workshop.id === id) detail.value.block_reason = null
  }

  function patchWorkshop(updated: WorkshopSummary) {
    // block/unblock return the lean WorkshopSummary; merge so the AB-37 list-only
    // fields (owner_login, branch_count) survive the status change.
    workshops.value = workshops.value.map((row) =>
      row.id === updated.id ? { ...row, ...updated } : row,
    )
    if (detail.value?.workshop.id === updated.id) {
      detail.value = { ...detail.value, workshop: updated }
    }
  }

  // The manufacturer list stays small and operator-curated, so it loads in full
  // for the filter dropdown. Materials, by contrast, now number in the hundreds
  // (real catalog import), so `loadMaterials` filters and pages server-side —
  // see the note there.
  async function loadManufacturers() {
    manufacturersLoading.value = true
    manufacturersError.value = null
    manufacturersTraceId.value = null
    try {
      manufacturers.value = await api.get<Manufacturer[]>(
        '/platform/catalog/manufacturers',
        authInit(),
      )
    } catch (errorValue) {
      // Preserve a 403 as permission_denied so AdminManufacturersView /
      // AdminMaterialsView render the no-access AdminErrorState (AB-01/AB-08),
      // instead of masking it as a generic load failure (CB-100).
      const captured = captureApiError(errorValue, 'manufacturers_load_failed')
      manufacturersError.value = captured.code
      manufacturersTraceId.value = captured.traceId
    } finally {
      manufacturersLoading.value = false
    }
  }

  // Paginated with append (matches the orders/notifications convention): offset 0
  // replaces the list, a higher offset appends the next page, and materialsHasMore
  // is inferred from a full page so the "load more" button hides on the last one.
  // Filtering is server-side — the caller passes the active filters on every call.
  async function loadMaterials(filters: MaterialFilters = {}) {
    const offset = filters.offset ?? 0
    materialsLoading.value = true
    materialsError.value = null
    materialsTraceId.value = null
    try {
      const page = await api.get<Material[]>(
        withQuery('/platform/catalog/materials', {
          search: filters.search,
          kind: filters.kind,
          status: filters.status,
          manufacturer_ids: filters.manufacturerIds,
          material_types: filters.materialTypes,
          limit: MATERIALS_PAGE_LIMIT,
          offset,
        }),
        authInit(),
      )
      materials.value = offset === 0 ? page : [...materials.value, ...page]
      materialsHasMore.value = page.length === MATERIALS_PAGE_LIMIT
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'materials_load_failed')
      materialsError.value = captured.code
      materialsTraceId.value = captured.traceId
    } finally {
      materialsLoading.value = false
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
    // AB-22: single-material responses (edit / activate) don't compute the usage
    // count and return 0 — preserve the existing list row's count on patch.
    materials.value = materials.value.map((row) =>
      row.id === updated.id ? { ...updated, branch_usage_count: row.branch_usage_count } : row,
    )
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

  async function resetWorkshopOwnerPassword(workshopId: string) {
    lastOwnerSecret.value = await api.post<WorkshopOwnerTempPasswordResponse>(
      `/platform/workshops/${workshopId}/owner/reset-password`,
      undefined,
      authInit(),
    )
    return lastOwnerSecret.value
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

  // AB-25: the inverse of resolveError — flip a resolved record back to open so a
  // code that recurs after being marked resolved can be re-triaged.
  async function reopenError(id: string) {
    const updated = await api.post<ErrorRecord>(
      `/platform/errors/${id}/reopen`,
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

  async function loadAudit(options: AuditLoadOptions = {}) {
    const actionQuery = options.actions ?? { limit: 50 }
    const statusQuery = options.status ?? { limit: 50 }
    opsLoading.value = true
    opsError.value = null
    opsTraceId.value = null
    const [actionsResult, statusResult] = await Promise.allSettled([
      api.get<ActionLog[]>(withQuery('/platform/audit/actions', actionQuery), authInit()),
      api.get<StatusChangeLog[]>(
        withQuery('/platform/audit/status-changes', statusQuery),
        authInit(),
      ),
    ])
    if (actionsResult.status === 'fulfilled') {
      auditActions.value = options.appendActions
        ? [...auditActions.value, ...actionsResult.value]
        : actionsResult.value
    }
    if (statusResult.status === 'fulfilled') {
      auditStatusChanges.value = options.appendStatus
        ? [...auditStatusChanges.value, ...statusResult.value]
        : statusResult.value
    }
    if (actionsResult.status === 'rejected' && statusResult.status === 'rejected') {
      const captured = captureApiError(actionsResult.reason, 'audit_load_failed')
      opsError.value = captured.code
      opsTraceId.value = captured.traceId
    }
    opsLoading.value = false
    return {
      actionsCount: actionsResult.status === 'fulfilled' ? actionsResult.value.length : 0,
      statusCount: statusResult.status === 'fulfilled' ? statusResult.value.length : 0,
    }
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
    lastOwnerSecret.value = null
    jobs.value = []
    errors.value = []
    errorDetail.value = null
    auditActions.value = []
    auditStatusChanges.value = []
    loading.value = false
    manufacturersLoading.value = false
    materialsLoading.value = false
    opsLoading.value = false
    error.value = null
    manufacturersError.value = null
    materialsError.value = null
    opsError.value = null
    traceId.value = null
    manufacturersTraceId.value = null
    materialsTraceId.value = null
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
    lastOwnerSecret,
    jobs,
    errors,
    errorDetail,
    auditActions,
    auditStatusChanges,
    loading,
    manufacturersLoading,
    materialsLoading,
    materialsHasMore,
    catalogLoading,
    opsLoading,
    error,
    manufacturersError,
    materialsError,
    catalogError,
    opsError,
    traceId,
    manufacturersTraceId,
    materialsTraceId,
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
    resetWorkshopOwnerPassword,
    blockPlatformUser,
    unblockPlatformUser,
    loadJobs,
    runJob,
    loadErrors,
    loadErrorDetail,
    resolveError,
    reopenError,
    loadAudit,
    reset,
  }
})
