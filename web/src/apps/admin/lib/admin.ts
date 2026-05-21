// Pure helpers for the superadmin screens — temp-password generation,
// materials sheet/edge field rules, error-count display, and audit-filter
// query-string building. Kept side-effect-free so they're cheap to unit test.

import type {
  ActionLogFilters,
  MaterialCreate,
  MaterialKind,
  StatusChangeFilters,
} from '../api/types'

// Mirrors the prototype's window.genTempPassword: ≥10 chars, guarantees an
// upper + lower + digit, avoids ambiguous glyphs (0/O, 1/l/I), ends with '!'.
export function genTempPassword(): string {
  const U = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
  const L = 'abcdefghijkmnpqrstuvwxyz'
  const D = '23456789'
  const pick = (s: string) => s[Math.floor(Math.random() * s.length)]
  let p = pick(U) + pick(L) + pick(D)
  const all = U + L + D
  for (let i = 0; i < 7; i++) p += pick(all)
  return (
    p
      .split('')
      .sort(() => Math.random() - 0.5)
      .join('') + '!'
  )
}

// --- materials: sheet vs edge field rules -----------------------------------

export interface MaterialForm {
  kind: MaterialKind
  type: string
  name: string
  thickness_mm: string
  color: string
  decor_code: string
  sheet_length_mm: string
  sheet_width_mm: string
  grain_direction: boolean
}

export interface MaterialValidation {
  ok: boolean
  // length ≥ width invariant (sheets only) — long side carries the grain.
  dimsBad: boolean
}

export function validateMaterialForm(f: MaterialForm): MaterialValidation {
  const nameOk = f.name.trim().length > 0
  const colorOk = f.color.trim().length > 0
  const thickness = Number(f.thickness_mm)
  const thicknessOk = Number.isFinite(thickness) && thickness > 0

  if (f.kind === 'edge') {
    return { ok: nameOk && colorOk && thicknessOk, dimsBad: false }
  }

  const len = Number(f.sheet_length_mm)
  const wid = Number(f.sheet_width_mm)
  const lenOk = Number.isFinite(len) && len > 0
  const widOk = Number.isFinite(wid) && wid > 0
  // Only flag a dimension error once both are positive numbers.
  const dimsBad = lenOk && widOk && len < wid
  return { ok: nameOk && colorOk && thicknessOk && lenOk && widOk && !dimsBad, dimsBad }
}

// Build the create payload, dropping sheet-only fields for edges.
export function materialCreatePayload(f: MaterialForm): MaterialCreate {
  const base: MaterialCreate = {
    kind: f.kind,
    name: f.name.trim(),
    thickness_mm: Number(f.thickness_mm),
    color: f.color.trim(),
    decor_code: f.decor_code.trim() || null,
  }
  if (f.kind === 'sheet') {
    base.type = (f.type || 'dsp') as MaterialCreate['type']
    base.sheet_length_mm = Number(f.sheet_length_mm)
    base.sheet_width_mm = Number(f.sheet_width_mm)
    base.grain_direction = f.grain_direction
  }
  return base
}

// --- error monitor: 24h / 7d count display ----------------------------------

// A row is "hot" when 24h volume crosses the warn threshold (matches the
// prototype's >10 highlight on the dashboard + monitor).
export const ERROR_WARN_THRESHOLD = 10

export function isErrorHot(count24h: number): boolean {
  return count24h > ERROR_WARN_THRESHOLD
}

// "12 · 84" style "24h · 7d" summary, always showing both windows.
export function errorCountDisplay(count24h: number, count7d: number): string {
  return `${count24h} · ${count7d}`
}

// --- audit filters → query string -------------------------------------------

// Build a URLSearchParams for GET /admin/audit/actions, dropping empty values
// and mapping camelCase form keys to the snake_case the backend expects.
export function buildActionLogQuery(f: ActionLogFilters): string {
  const qs = new URLSearchParams()
  const set = (key: string, value: string | number | undefined | null) => {
    if (value === undefined || value === null) return
    const s = typeof value === 'string' ? value.trim() : String(value)
    if (s) qs.set(key, s)
  }
  set('action', f.action)
  set('family', f.family)
  set('module', f.module)
  set('actor', f.actor)
  set('entity_type', f.entityType)
  set('entity_id', f.entityId)
  set('workshop_id', f.workshopId)
  set('branch_id', f.branchId)
  set('date_from', f.dateFrom)
  set('date_to', f.dateTo)
  if (f.limit != null) qs.set('limit', String(f.limit))
  if (f.offset != null) qs.set('offset', String(f.offset))
  return qs.toString()
}

export function buildStatusChangeQuery(f: StatusChangeFilters): string {
  const qs = new URLSearchParams()
  const set = (key: string, value: string | number | undefined | null) => {
    if (value === undefined || value === null) return
    const s = typeof value === 'string' ? value.trim() : String(value)
    if (s) qs.set(key, s)
  }
  set('entity_type', f.entityType)
  set('entity_id', f.entityId)
  set('from_status', f.fromStatus)
  set('to_status', f.toStatus)
  set('actor', f.actor)
  set('workshop_id', f.workshopId)
  set('date_from', f.dateFrom)
  set('date_to', f.dateTo)
  if (f.limit != null) qs.set('limit', String(f.limit))
  if (f.offset != null) qs.set('offset', String(f.offset))
  return qs.toString()
}
