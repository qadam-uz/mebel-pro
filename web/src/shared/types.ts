// Core DTOs reused across the three apps. Mirrors backend Pydantic schemas
// (backend/app/schemas/*). Only the shapes the shared layer needs live here;
// per-domain DTOs belong with the screens that own them.

export type PrincipalType = 'platform_user' | 'workshop_user' | 'client'

// Workshop staff permissions — coarse, branch-scoped (see docs/access-patterns.md).
export type Permission =
  | 'view_dashboard'
  | 'manage_orders'
  | 'process_production'
  | 'manage_catalog'
  | 'manage_inventory'
  | 'manage_finance'
  | 'view_finance_reports'

export interface Grant {
  permission: Permission
  branch_id: string
}

// POST /auth/{platform,workshop}/login, /auth/client/telegram
export interface Tokens {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface ClientTokens extends Tokens {
  is_new: boolean
}

// POST /auth/refresh
export interface RefreshResponse {
  access_token: string
  token_type: string
}

// GET /auth/me
export interface Me {
  principal_type: PrincipalType
  id: string
  full_name: string | null
  phone: string | null
  force_password_change: boolean
  // workshop-user fields
  workshop_id: string | null
  is_owner: boolean
  home_branch_id: string | null
  grants: Grant[]
  // client fields
  first_name: string | null
  photo_url: string | null
}

// GET /auth/sessions
export interface SessionInfo {
  id: string
  device_info: Record<string, unknown>
  created_at: string
  last_used_at: string
  current: boolean
}

// GET /notifications, /notifications/unread-count
export interface Notification {
  id: string
  event_code: string
  entity_type: string | null
  entity_id: string | null
  payload: Record<string, unknown>
  created_at: string
  read_at: string | null
}

export interface UnreadCount {
  unread: number
}

// Error envelope: { code, detail, trace_id }
export interface ApiErrorBody {
  code: string
  detail: string
  trace_id?: string
}
