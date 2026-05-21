// Superadmin-app API surface — thin wrappers over the /admin/* and
// /platform/* endpoints. Screens call these; the shared api client handles
// auth/refresh/errors.

import { api } from '@/shared/api'
import { buildActionLogQuery, buildStatusChangeQuery } from '../lib/admin'
import type {
  ActionLogFilters,
  ActionLogRow,
  CreatedSecret,
  DashboardOut,
  ErrorGroupDetail,
  ErrorGroupRow,
  ErrorGroupStatus,
  JobOut,
  MaterialCreate,
  MaterialKind,
  MaterialOut,
  MaterialUpdate,
  PlatformUserCreate,
  PlatformUserOut,
  StatusChangeFilters,
  StatusChangeRow,
  WorkshopOut,
  WorkshopProvision,
  WorkshopProvisionResult,
  WorkshopSummary,
} from './types'

// --- dashboard --------------------------------------------------------------

export function getDashboard(): Promise<DashboardOut> {
  return api.get<DashboardOut>('/admin/dashboard')
}

// --- workshops --------------------------------------------------------------

export function listWorkshops(): Promise<WorkshopSummary[]> {
  return api.get<WorkshopSummary[]>('/admin/workshops')
}

export function getWorkshop(id: string): Promise<WorkshopSummary> {
  return api.get<WorkshopSummary>(`/admin/workshops/${id}`)
}

export function provisionWorkshop(body: WorkshopProvision): Promise<WorkshopProvisionResult> {
  return api.post<WorkshopProvisionResult>('/admin/workshops', body)
}

export function editWorkshopProfile(
  id: string,
  body: { name?: string; phone?: string; address?: string | null },
): Promise<WorkshopOut> {
  return api.patch<WorkshopOut>(`/admin/workshops/${id}/profile`, body)
}

export function blockWorkshop(id: string, reason: string): Promise<WorkshopOut> {
  return api.post<WorkshopOut>(`/admin/workshops/${id}/block`, { reason })
}

export function unblockWorkshop(id: string, reason: string): Promise<WorkshopOut> {
  return api.post<WorkshopOut>(`/admin/workshops/${id}/unblock`, { reason })
}

// --- materials master -------------------------------------------------------

export function listMaterials(kind?: MaterialKind): Promise<MaterialOut[]> {
  return api.get<MaterialOut[]>(`/admin/materials${kind ? `?kind=${kind}` : ''}`)
}

export function getMaterial(id: string): Promise<MaterialOut> {
  return api.get<MaterialOut>(`/admin/materials/${id}`)
}

export function createMaterial(body: MaterialCreate): Promise<MaterialOut> {
  return api.post<MaterialOut>('/admin/materials', body)
}

export function editMaterial(id: string, body: MaterialUpdate): Promise<MaterialOut> {
  return api.patch<MaterialOut>(`/admin/materials/${id}`, body)
}

export function setMaterialStatus(id: string, active: boolean): Promise<MaterialOut> {
  return api.post<MaterialOut>(`/admin/materials/${id}/${active ? 'activate' : 'deactivate'}`)
}

// --- platform users ---------------------------------------------------------

export function listPlatformUsers(): Promise<PlatformUserOut[]> {
  return api.get<PlatformUserOut[]>('/platform/users')
}

export function createPlatformUser(body: PlatformUserCreate): Promise<CreatedSecret> {
  return api.post<CreatedSecret>('/platform/users', body)
}

export function resetPlatformPassword(id: string): Promise<CreatedSecret> {
  return api.post<CreatedSecret>(`/platform/users/${id}/reset-password`)
}

export function blockPlatformUser(id: string): Promise<PlatformUserOut> {
  return api.post<PlatformUserOut>(`/platform/users/${id}/block`)
}

export function unblockPlatformUser(id: string): Promise<PlatformUserOut> {
  return api.post<PlatformUserOut>(`/platform/users/${id}/unblock`)
}

// --- jobs -------------------------------------------------------------------

export function listJobs(): Promise<JobOut[]> {
  return api.get<JobOut[]>('/admin/platform/jobs')
}

export function runJob(name: string): Promise<JobOut> {
  return api.post<JobOut>(`/admin/platform/jobs/${encodeURIComponent(name)}/run`)
}

// --- errors -----------------------------------------------------------------

export function listErrors(params: {
  module?: string
  code?: string
  status?: ErrorGroupStatus
  minCount24h?: number
}): Promise<ErrorGroupRow[]> {
  const qs = new URLSearchParams()
  if (params.module) qs.set('module', params.module)
  if (params.code) qs.set('code', params.code)
  if (params.status) qs.set('status', params.status)
  if (params.minCount24h != null) qs.set('min_count_24h', String(params.minCount24h))
  const q = qs.toString()
  return api.get<ErrorGroupRow[]>(`/admin/platform/errors${q ? `?${q}` : ''}`)
}

export function getError(id: string): Promise<ErrorGroupDetail> {
  return api.get<ErrorGroupDetail>(`/admin/platform/errors/${id}`)
}

export function resolveError(id: string): Promise<ErrorGroupRow> {
  return api.post<ErrorGroupRow>(`/admin/platform/errors/${id}/resolve`)
}

// --- audit ------------------------------------------------------------------

export function listAuditActions(filters: ActionLogFilters): Promise<ActionLogRow[]> {
  const q = buildActionLogQuery(filters)
  return api.get<ActionLogRow[]>(`/admin/audit/actions${q ? `?${q}` : ''}`)
}

export function listAuditStatusChanges(filters: StatusChangeFilters): Promise<StatusChangeRow[]> {
  const q = buildStatusChangeQuery(filters)
  return api.get<StatusChangeRow[]>(`/admin/audit/status-changes${q ? `?${q}` : ''}`)
}

export type * from './types'
