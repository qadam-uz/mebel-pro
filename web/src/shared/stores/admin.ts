import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { api, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import { MATERIALS_PAGE_LIMIT } from '@/shared/app/constants'
import { useAuthStore } from '@/shared/stores/auth'

// The decor's own column is `status`, but the wire enum values and the `status=`
// query param both keep these names — catalog/routes.py pins the alias on purpose.
export type MaterialStatus = 'active' | 'inactive'

// What a decor *is* — the single axis that replaced the old `kind` (panel/edge)
// plus `type` (dsp/mdf/…) pair. Order matches backend/app/models/enums.py DecorType.
export type DecorType = 'ldsp' | 'dsp' | 'mdf' | 'fanera' | 'yogoch' | 'kromka' | 'boshqa'

export interface WorkshopSummary {
  id: string
  name: string
  status: 'active' | 'blocked'
  // The `/w/{code}` client-entry code — the head of every client link this
  // workshop and its branches publish (client-entry.md).
  public_code: string
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
  // `branch_no` is the branch's immutable platform-wide number and the last
  // segment of its QR link (`/w/{code}/{branch_no}`) — read-only. It is not
  // part of an order number: those are six random digits (sales.md).
  branches: Array<{
    id: string
    branch_no: number
    name: string
    status: string
    address: string
    phone: string
  }>
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

// The platform half of the catalog: identity only. No thickness, no size, no
// price — a platform operator cannot know what formats a workshop's supplier
// sells. The format lives on the branch's own row (`BranchMaterial`).
/**
 * A decor is a PATTERN identity — who makes it, what it is called, what it looks
 * like. It deliberately carries no substrate: Egger H1145 is one decor that
 * exists as an LDSP board *and* as a matching kromka, and both are
 * `DecorFormat`s of this row. Making the substrate part of the decor is what
 * produced the duplicate twin rows the format reshape merged away.
 */
export interface Decor {
  id: string
  manufacturer_id: string
  manufacturer_name: string
  code: string | null
  name: string
  has_grain: boolean
  image_file_id: string | null
  status: MaterialStatus
  // Server-composed display string. There is no stored name any more; render
  // this rather than rebuilding it (backend/app/core/material_label.py). It
  // carries no substrate prefix and no dimensions — a decor has neither.
  label: string
  // AB-22: how many distinct branches carry any format of this decor (list
  // responses only — single-object responses return 0).
  branch_usage_count: number
  // Active formats. A decor with none is a name nobody can attach anything of.
  format_count: number
  created_at: string
  updated_at: string
}

/**
 * One concrete product of a decor — the thing a supplier actually sells, and
 * the thing a branch decides to carry.
 *
 * Platform-owned and **immutable**: there is no PATCH. A wrong format is
 * deactivated and a correct one created, because branch rows, stock, cutting
 * panels and order history all resolve through this id and a silent
 * re-dimension would rewrite what those rows mean. `status` is the only mutable
 * field.
 */
export interface DecorFormat {
  id: string
  decor_id: string
  type: DecorType
  thickness_mm: string
  // Panel-shaped formats carry length/width; kromka carries tape_width.
  length_mm: number | null
  width_mm: number | null
  tape_width_mm: number | null
  // 1 or 2 for the board types (ldsp/dsp/mdf), null for everything else. A
  // one-sided sheet is a different product at a different price.
  finished_sides: number | null
  status: MaterialStatus
  label: string
  created_at: string
  updated_at: string
}

/** The body of `POST /platform/catalog/decors/{id}/formats`. */
export interface DecorFormatWriteRequest {
  type: DecorType
  thickness_mm: string
  length_mm?: number | null
  width_mm?: number | null
  tape_width_mm?: number | null
  finished_sides?: number | null
}

// Server-side decor filters for the paginated platform catalog list. Omitted
// fields mean "no filter"; multi-selects go over as repeated query params. The
// status filter keeps the `status` wire name even though the column is `status`.
export interface DecorFilters {
  search?: string
  type?: DecorType
  types?: DecorType[]
  status?: MaterialStatus
  manufacturerIds?: string[]
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
  }
  owner: { login: string }
  temp_password?: string
}

export interface ManufacturerWriteRequest {
  name: string
  country: string | null
  note: string | null
}

// One flat shape, no panel/edge union: the admin app owns identity only, so
// there is nothing left for the two arms to differ about.
export interface DecorWriteRequest {
  manufacturer_id: string
  code: string | null
  name: string
  has_grain: boolean
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
  const decors = ref<Decor[]>([])
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
  const decorsLoading = ref(false)
  const decorsHasMore = ref(false)
  const catalogLoading = computed(() => manufacturersLoading.value || decorsLoading.value)
  const opsLoading = ref(false)
  const error = ref<string | null>(null)
  const manufacturersError = ref<string | null>(null)
  const decorsError = ref<string | null>(null)
  const catalogError = computed(() => manufacturersError.value ?? decorsError.value)
  const opsError = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const manufacturersTraceId = ref<string | null>(null)
  const decorsTraceId = ref<string | null>(null)
  const catalogTraceId = computed(() => manufacturersTraceId.value ?? decorsTraceId.value)
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

  // A list read carries a server snapshot taken when it *started*. If a mutation
  // lands while it is in flight, that snapshot predates the change — assigning it
  // on arrival silently reverts the screen. Provisioning a workshop on a slow
  // connection did exactly that: the new row appeared, then vanished when the
  // page's own initial read completed, with no error and nothing to retry.
  // Every writer bumps this; a read whose generation is stale keeps its result.
  let workshopsGeneration = 0

  function invalidateWorkshopReads() {
    workshopsGeneration += 1
  }

  async function loadWorkshops() {
    const generation = workshopsGeneration
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      const rows = await api.get<WorkshopListItem[]>('/platform/workshops', authInit())
      if (generation !== workshopsGeneration) return
      workshops.value = rows
    } catch (errorValue) {
      // A superseded read must not paint an error over state that is fine.
      if (generation !== workshopsGeneration) return
      const captured = captureApiError(errorValue, 'workshops_load_failed')
      error.value = captured.code
      traceId.value = captured.traceId
    } finally {
      // Always cleared, even when the result was dropped: a mutation does not
      // start a new read, so nothing else would ever lower this flag and the
      // screen would keep its skeleton forever.
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
    invalidateWorkshopReads()
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
    // Same reasoning as `provision`: a block or unblock that lands during a list
    // read must survive that read's arrival, not be rolled back by it.
    invalidateWorkshopReads()
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
  // for the filter dropdown. Decors, by contrast, now number in the hundreds
  // (real catalog import), so `loadDecors` filters and pages server-side —
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
      // AdminDecorsView render the no-access AdminErrorState (AB-01/AB-08),
      // instead of masking it as a generic load failure (CB-100).
      const captured = captureApiError(errorValue, 'manufacturers_load_failed')
      manufacturersError.value = captured.code
      manufacturersTraceId.value = captured.traceId
    } finally {
      manufacturersLoading.value = false
    }
  }

  // Paginated with append (matches the orders/notifications convention): offset 0
  // replaces the list, a higher offset appends the next page, and decorsHasMore
  // is inferred from a full page so the "load more" button hides on the last one.
  // Filtering is server-side — the caller passes the active filters on every call.
  async function loadDecors(filters: DecorFilters = {}) {
    const offset = filters.offset ?? 0
    decorsLoading.value = true
    decorsError.value = null
    decorsTraceId.value = null
    try {
      const page = await api.get<Decor[]>(
        withQuery('/platform/catalog/decors', {
          search: filters.search,
          type: filters.type,
          types: filters.types,
          status: filters.status,
          manufacturer_ids: filters.manufacturerIds,
          limit: MATERIALS_PAGE_LIMIT,
          offset,
        }),
        authInit(),
      )
      decors.value = offset === 0 ? page : [...decors.value, ...page]
      decorsHasMore.value = page.length === MATERIALS_PAGE_LIMIT
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'decors_load_failed')
      decorsError.value = captured.code
      decorsTraceId.value = captured.traceId
    } finally {
      decorsLoading.value = false
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

  async function createDecor(payload: DecorWriteRequest) {
    const created = await api.post<Decor>('/platform/catalog/decors', payload, authInit())
    decors.value = [created, ...decors.value]
    return created
  }

  // One decor, for the detail route reached by URL with no list in memory. It
  // returns rather than storing: a detail page's own record is not shared state,
  // and parking it in the store would mean another ref to reset and a stale row
  // to trip over on the next visit.
  async function fetchDecor(id: string) {
    return api.get<Decor>(`/platform/catalog/decors/${id}`, authInit())
  }

  async function updateDecor(id: string, payload: Partial<DecorWriteRequest>) {
    const updated = await api.patch<Decor>(`/platform/catalog/decors/${id}`, payload, authInit())
    patchDecor(updated)
    return updated
  }

  /**
   * A decor's formats, active first. Returned rather than stored: the detail
   * page's own record is not shared state, and parking it in the store would
   * mean another ref to reset and a stale list to trip over on the next visit.
   */
  async function fetchDecorFormats(decorId: string) {
    return api.get<DecorFormat[]>(`/platform/catalog/decors/${decorId}/formats`, authInit())
  }

  async function createDecorFormat(decorId: string, payload: DecorFormatWriteRequest) {
    return api.post<DecorFormat>(`/platform/catalog/decors/${decorId}/formats`, payload, authInit())
  }

  /**
   * Status is the only thing a format can change. Deactivating one never
   * cascades into branch rows — the branch keeps selling the remainder on its
   * shelf and keeps receiving arrivals, because a supplier may still hold stock
   * of a product the maker has stopped making.
   */
  async function setDecorFormatStatus(
    decorId: string,
    decorFormatId: string,
    status: MaterialStatus,
  ) {
    return api.post<DecorFormat>(
      `/platform/catalog/decors/${decorId}/formats/${decorFormatId}/${
        status === 'active' ? 'activate' : 'deactivate'
      }`,
      undefined,
      authInit(),
    )
  }

  async function setDecorStatus(id: string, status: MaterialStatus) {
    const updated = await api.post<Decor>(
      `/platform/catalog/decors/${id}/${status === 'active' ? 'activate' : 'deactivate'}`,
      undefined,
      authInit(),
    )
    patchDecor(updated)
    return updated
  }

  function patchManufacturer(updated: Manufacturer) {
    manufacturers.value = manufacturers.value.map((row) => (row.id === updated.id ? updated : row))
    // AB-16: decors carry a denormalized manufacturer_name; refresh it so a
    // rename doesn't leave stale labels on the cached list/filter. `label` is
    // server-composed and still carries the old manufacturer until the next
    // list load — accepted, the rename dialog reloads the page it came from.
    decors.value = decors.value.map((row) =>
      row.manufacturer_id === updated.id ? { ...row, manufacturer_name: updated.name } : row,
    )
  }

  function patchDecor(updated: Decor) {
    // AB-22: single-decor responses (edit / activate) don't compute the usage
    // count and return 0 — preserve the existing list row's count on patch.
    // `updated` is spread FIRST so the fresh `label` wins; only the count is kept.
    decors.value = decors.value.map((row) =>
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
    decors.value = []
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
    decorsLoading.value = false
    decorsHasMore.value = false
    opsLoading.value = false
    error.value = null
    manufacturersError.value = null
    decorsError.value = null
    opsError.value = null
    traceId.value = null
    manufacturersTraceId.value = null
    decorsTraceId.value = null
    opsTraceId.value = null
  }

  return {
    workshops,
    detail,
    overview,
    clearSecrets,
    lastProvision,
    manufacturers,
    decors,
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
    decorsLoading,
    decorsHasMore,
    catalogLoading,
    opsLoading,
    error,
    manufacturersError,
    decorsError,
    catalogError,
    opsError,
    traceId,
    manufacturersTraceId,
    decorsTraceId,
    catalogTraceId,
    opsTraceId,
    loadWorkshops,
    loadOverview,
    loadWorkshop,
    provision,
    blockWorkshop,
    unblockWorkshop,
    loadManufacturers,
    loadDecors,
    createManufacturer,
    updateManufacturer,
    setManufacturerStatus,
    createDecor,
    fetchDecor,
    updateDecor,
    setDecorStatus,
    fetchDecorFormats,
    createDecorFormat,
    setDecorFormatStatus,
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
