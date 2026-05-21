// Admin-app DTOs — mirror backend Pydantic schemas (backend/app/schemas/
// workshop.py, catalog.py, identity.py, platform_ops.py). Only the shapes the
// superadmin screens need live here.

export type WorkshopStatus = 'active' | 'blocked'
export type BranchStatus = 'active' | 'temporarily_closed' | 'inactive'
export type MaterialKind = 'sheet' | 'edge'
export type MaterialType = 'dsp' | 'mdf' | 'plywood' | 'natural_wood' | 'other'
export type CatalogStatus = 'active' | 'inactive'
export type UserStatus = 'active' | 'blocked'
export type JobRunResult = 'ok' | 'failed' | 'running'
export type ErrorGroupStatus = 'open' | 'resolved'
export type ActorType = 'platform_user' | 'workshop_user' | 'client' | 'system'

// --- workshops --------------------------------------------------------------

export interface WorkshopOut {
  id: string
  name: string
  phone: string
  address: string | null
  logo_file_id: string | null
  owner_user_id: string | null
  status: WorkshopStatus
  created_at: string
  updated_at: string
}

export interface WorkshopSummary extends WorkshopOut {
  owner_name: string | null
  owner_phone: string | null
  branches_count: number
  orders_30d_count: number
}

export interface WorkshopProvision {
  name: string
  phone: string
  address?: string | null
  owner_full_name: string
  owner_login: string
  owner_phone: string
  owner_password?: string | null
}

export interface WorkshopProvisionResult {
  workshop: WorkshopOut
  owner_id: string
  owner_login: string
  temp_password: string
}

// --- materials master -------------------------------------------------------

export interface MaterialOut {
  id: string
  kind: MaterialKind
  type: MaterialType | null
  name: string
  thickness_mm: number
  color: string
  decor_code: string | null
  sheet_length_mm: number | null
  sheet_width_mm: number | null
  grain_direction: boolean | null
  image_file_id: string | null
  status: CatalogStatus
  created_at: string
  updated_at: string
}

export interface MaterialCreate {
  kind: MaterialKind
  type?: MaterialType | null
  name: string
  thickness_mm: number
  color: string
  decor_code?: string | null
  sheet_length_mm?: number | null
  sheet_width_mm?: number | null
  grain_direction?: boolean | null
}

export interface MaterialUpdate {
  type?: MaterialType | null
  type_set?: boolean
  name?: string
  thickness_mm?: number
  color?: string
  decor_code?: string | null
  decor_code_set?: boolean
  sheet_length_mm?: number | null
  sheet_width_mm?: number | null
  grain_direction?: boolean | null
}

// --- platform users ---------------------------------------------------------

export interface PlatformUserOut {
  id: string
  login: string
  full_name: string
  phone: string
  status: UserStatus
  force_password_change: boolean
  last_login_at: string | null
  created_at: string
}

export interface PlatformUserCreate {
  full_name: string
  login: string
  phone: string
  password?: string | null
}

export interface CreatedSecret {
  id: string
  login: string
  temp_password: string
}

// --- jobs -------------------------------------------------------------------

export interface JobOut {
  name: string
  interval_seconds: number
  last_started_at: string | null
  last_finished_at: string | null
  last_result: JobRunResult | null
  last_log: string | null
}

// --- errors -----------------------------------------------------------------

export interface ErrorGroupRow {
  id: string
  code: string
  module: string | null
  message_preview: string | null
  status: ErrorGroupStatus
  count_total: number
  count_24h: number
  count_7d: number
  last_occurred_at: string | null
}

export interface ErrorEventOut {
  id: string
  message: string | null
  stack: string | null
  context: Record<string, unknown> | null
  trace_id: string | null
  workshop_id: string | null
  occurred_at: string
}

export interface ErrorGroupDetail {
  id: string
  code: string
  module: string | null
  message_preview: string | null
  status: ErrorGroupStatus
  count_total: number
  count_24h: number
  count_7d: number
  last_occurred_at: string | null
  resolved_at: string | null
  affected_workshops: string[]
  trace_ids: string[]
  events: ErrorEventOut[]
}

// --- audit ------------------------------------------------------------------

export interface ActionLogRow {
  id: string
  actor_type: ActorType
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

export interface StatusChangeRow {
  id: string
  entity_type: string
  entity_id: string
  workshop_id: string | null
  branch_id: string | null
  from_status: string | null
  to_status: string
  actor_type: ActorType
  actor_user_id: string | null
  actor_client_id: string | null
  reason: string | null
  changed_at: string
}

export interface ActionLogFilters {
  action?: string
  family?: string
  module?: string
  actor?: string
  entityType?: string
  entityId?: string
  workshopId?: string
  branchId?: string
  dateFrom?: string
  dateTo?: string
  limit?: number
  offset?: number
}

export interface StatusChangeFilters {
  entityType?: string
  entityId?: string
  fromStatus?: string
  toStatus?: string
  actor?: string
  workshopId?: string
  dateFrom?: string
  dateTo?: string
  limit?: number
  offset?: number
}

// --- dashboard --------------------------------------------------------------

export interface RecentWorkshop {
  id: string
  name: string
  status: WorkshopStatus
  created_at: string
}

export interface DashboardOut {
  workshops_count: number
  branches_count: number
  clients_count: number
  recent_workshops: RecentWorkshop[]
  failed_jobs_24h: number
  open_error_groups: number
}
