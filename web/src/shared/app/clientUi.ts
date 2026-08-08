import { DRAFT_LIMIT } from '@/shared/app/constants'
import { snapshotMaterialLabel } from '@/shared/app/materialLabel'
import { translate, translatePlural } from '@/shared/i18n'
import type { NotificationItem } from '@/shared/stores/notifications'
import type { OrderStatus } from '@/shared/stores/orders'
import type { CuttingDraft } from '@/shared/stores/cutting'

/** User-facing draft identity. IDs are never part of a client label. */
export function draftDisplayName(draft: CuttingDraft): string {
  if (draft.name) return draft.name
  const result =
    draft.results.find((item) => item.id === draft.chosen_result_id) ?? draft.results[0]
  // Post-reshape snapshots have no `name`, so the label is composed (which also
  // gives pre-reshape drafts their historical string). The first `·` segment is
  // the identity prefix — «LDSP Egger H1334» — exactly what `.name.split('·')[0]`
  // used to yield. The fallback string is filtered out so an unlabelled snapshot
  // never becomes the draft's name.
  const fallback = translate('cutting.material.fallback')
  const materials = [
    ...new Set(
      draft.parts_snapshot
        .map((part) => {
          const snapshot = result?.material_snapshots[part.material_id]
          return snapshot ? snapshotMaterialLabel(snapshot, fallback) : ''
        })
        .map((value) => value.split('·')[0].trim())
        .filter((value) => value && value !== fallback),
    ),
  ]
  if (materials.length)
    return `${materials.slice(0, 2).join(' + ')}${materials.length > 2 ? ` +${materials.length - 2}` : ''}`
  return translate('client.draft.untitled')
}

// Status → catalog key, not status → copy: the label itself must be resolved on
// every call so a language switch reaches labels already on screen.
const STATUS_KEYS: Readonly<Record<OrderStatus, string>> = {
  new: 'new',
  confirmed: 'confirmed',
  cutting: 'production',
  edge_banding: 'production',
  ready: 'ready',
  completed: 'completed',
  cancelled: 'cancelled',
}

/** The five phases of the client-facing order track, in order. */
const PHASE_KEYS = ['new', 'confirmed', 'production', 'ready', 'completed'] as const

export function clientStatusLabel(status: OrderStatus): string {
  return translate(`client.status.${STATUS_KEYS[status]}`)
}

export function clientPhaseLabels(): string[] {
  return PHASE_KEYS.map((key) => translate(`client.status.${key}`))
}

export const activeClientStatuses: OrderStatus[] = [
  'new',
  'confirmed',
  'cutting',
  'edge_banding',
  'ready',
]

export function clientPhaseIndex(status: OrderStatus): number {
  if (status === 'new') return 0
  if (status === 'confirmed') return 1
  if (status === 'cutting' || status === 'edge_banding') return 2
  if (status === 'ready') return 3
  if (status === 'completed') return 4
  return -1
}

export function clientStatusPillClass(status: OrderStatus): string {
  if (status === 'completed') return 'client-pill client-pill-done'
  if (status === 'cancelled') return 'client-pill client-pill-danger'
  if (status === 'ready') return 'client-pill client-pill-ready'
  if (status === 'confirmed') return 'client-pill client-pill-info'
  if (status === 'cutting' || status === 'edge_banding') return 'client-pill client-pill-work'
  return 'client-pill client-pill-new'
}

/** Filled fraction (0..100) of the five-phase order track, for the dashboard progress bar.
 *  Terminal/off-track statuses (`cancelled`) read as 0. */
export function clientPhaseProgress(status: OrderStatus): number {
  const index = clientPhaseIndex(status)
  if (index < 0) return 0
  return [14, 30, 55, 85, 100][index] ?? 0
}

/** The next phase label after `status`, or null when already at the final phase / off-track. */
export function clientNextPhaseLabel(status: OrderStatus): string | null {
  const index = clientPhaseIndex(status)
  if (index < 0 || index >= PHASE_KEYS.length - 1) return null
  return translate(`client.status.${PHASE_KEYS[index + 1]}`)
}

/** First given name for the dashboard greeting, or null when no real name is set
 *  (so the caller falls back to a generic heading rather than greeting a phone number). */
export function clientGreetingName(
  me: { full_name?: string | null; name?: string | null } | null | undefined,
): string | null {
  // `||` (not `??`) so an empty-string full_name falls through to `name`.
  const raw = me?.full_name?.trim() || me?.name?.trim()
  const first = raw?.split(/\s+/)[0]
  return first ? first : null
}

/** One-line dashboard subtitle keyed off what most needs the client's attention:
 *  ready-for-pickup first, then in-flight orders, then saved drafts, then first-run. */
export function clientHomeSubtitle(counts: {
  ready: number
  active: number
  drafts: number
}): string {
  const { ready, active, drafts } = counts
  if (ready > 0) {
    return active > ready
      ? translatePlural('client.home.subtitleReadyMore', ready)
      : translatePlural('client.home.subtitleReady', ready)
  }
  if (active > 0) return translatePlural('client.home.subtitleActive', active)
  if (drafts > 0) return translate('client.home.subtitleDrafts')
  return translate('client.home.subtitleFirstRun')
}

export function normalizeUzPhone(value: string): string {
  let digits = value.replace(/\D/g, '')
  // drop a trunk-prefix 8 typed before the 998 country code ("8 998 …")
  if (digits.startsWith('8998')) digits = digits.slice(1)
  // drop a leading national-trunk 0 ("0 90 …")
  if (digits.startsWith('0')) digits = digits.replace(/^0+/, '')
  // a bare 9-digit national subscriber number gets the 998 country code
  if (digits.length === 9) digits = `998${digits}`
  return `+${digits}`
}

export function formatPhone(value: string | null | undefined): string {
  if (!value) return '-'
  const normalized = normalizeUzPhone(value)
  return normalized.replace(/^(\+998)(\d{2})(\d{3})(\d{2})(\d{2})$/, '$1 $2 $3 $4 $5')
}

export function isUzPhone(value: string): boolean {
  return /^\+998\d{9}$/.test(normalizeUzPhone(value))
}

export function formatRelativeDate(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${day}.${month} ${hour}:${minute}`
}

/** Same clock as `formatRelativeDate` but with the year — for lists that
 *  accumulate across years, where a bare `12.07` is ambiguous. */
export function formatFullDate(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${day}.${month}.${date.getFullYear()} ${hour}:${minute}`
}

export function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '-'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '-'
  // waste_percentage is always a 0..1 fraction (backend constrains it to [0,1])
  return `${(numeric * 100).toFixed(2)}%`
}

// The codes that carry their own client-facing message, each one an entry under
// `client.error.<code>`. A set of codes rather than a map of copy: the sentence
// lives in the catalog, so it follows the active locale instead of freezing at
// module-evaluation time.
const CLIENT_ERROR_CODES: ReadonlySet<string> = new Set([
  'permission_denied',
  'order_version_conflict',
  'order_not_found',
  'order_cancel_not_allowed',
  'order_cancel_failed',
  'order_quote_failed',
  'order_action_failed',
  'client_orders_load_failed',
  'client_order_load_failed',
  'branch_does_not_carry_panel',
  'branch_does_not_carry_edge',
  'missing_cutting_rate',
  'missing_edge_banding_rate',
  'cutting_result_not_usable',
  'part_too_large',
  'part_too_small',
  'draft_limit_exceeded',
  'invalid_name',
  'profile_update_failed',
  'password_change_failed',
  'request_timeout',
])

/**
 * Map a backend/store error code to client copy. Unknown snake_case codes fall
 * back to a generic message (a raw code is never shown to the user); a value
 * that is already a human sentence is returned unchanged.
 */
export function clientErrorLabel(
  code: string | null | undefined,
  fallback: string = translate('client.error.fallback'),
): string {
  if (!code) return fallback
  // `limit` is only read by `draft_limit_exceeded`; the rest ignore it.
  if (CLIENT_ERROR_CODES.has(code)) return translate(`client.error.${code}`, { limit: DRAFT_LIMIT })
  if (/\s/.test(code)) return code
  return fallback
}

const CLIENT_ICON_PATHS: Record<string, string> = {
  alert: '<path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v5"/><path d="M12 17h.01"/>',
  box: '<path d="m3 7 9-4 9 4-9 4-9-4Z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>',
  scissors:
    '<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="M8 8l10 10M8 16 18 6"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
  inbox:
    '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.5 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.5A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.5Z"/>',
  upload: '<path d="M12 16V4"/><path d="m6 10 6-6 6 6"/><path d="M4 20h16"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  store: '<path d="M4 10h16l-1-5H5l-1 5Z"/><path d="M6 10v10h12V10"/><path d="M9 20v-6h6v6"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  globe:
    '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><path d="M12 3.5c2.2 2.3 3.4 5.3 3.4 8.5s-1.2 6.2-3.4 8.5c-2.2-2.3-3.4-5.3-3.4-8.5S9.8 5.8 12 3.5Z"/>',
  board:
    '<rect x="3.5" y="4" width="5" height="12" rx="1"/><rect x="9.5" y="4" width="5" height="16" rx="1"/><rect x="15.5" y="4" width="5" height="9" rx="1"/>',
  table:
    '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17"/><path d="M3.5 14.5h17"/>',
  'chevron-down': '<path d="m6 9 6 6 6-6"/>',
  'chevron-right': '<path d="m9 18 6-6-6-6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/>',
  monitor: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  pencil: '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  swap: '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>',
  trash:
    '<path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/><path d="M9 7V4h6v3"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  // Void, not delete — a ledger row is only ever bekor qilingan, so `trash`
  // would name the wrong operation (QAD-184).
  ban: '<circle cx="12" cy="12" r="8.5"/><path d="m6 6 12 12"/>',
  'eye-off':
    '<path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="M10.7 5.1A10.4 10.4 0 0 1 12 5c7 0 10 7 10 7a13.2 13.2 0 0 1-1.7 2.7"/><path d="M6.6 6.6A13.5 13.5 0 0 0 2 12s3 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/><path d="M2 2l20 20"/>',
  // The two states of the «Burilish» cell. `grain` is a panel whose texture runs
  // one way — the part is pinned to it; `rotate` is the same panel released.
  // Drawn as a pair so the cell reads as one control in either state.
  grain: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 6v12M15 6v12"/>',
  'map-pin':
    '<path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>',
  rotate: '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v4h-4"/>',
}

export function clientIconPath(name: string): string {
  return CLIENT_ICON_PATHS[name] ?? CLIENT_ICON_PATHS.box
}

// Notification presentation (CB-126): a per-family icon + a localized one-line
// title, so the bell never shows a raw snake/dotted event_code. Forward-compatible
// with the order.* events the backend will add (CB-02).
const NOTIFICATION_TITLE_KEYS: Readonly<Record<string, string>> = {
  'inventory.negative_stock': 'inventoryNegativeStock',
  'order.placed': 'orderPlaced',
  'order.confirmed': 'orderConfirmed',
  'order.status_changed': 'orderStatusChanged',
  'order.updated': 'orderUpdated',
  'order.ready': 'orderReady',
  'order.cancelled': 'orderCancelled',
  'order.completed': 'orderCompleted',
}

function payloadString(payload: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = payload[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return null
}

export function clientNotificationTitle(item: NotificationItem): string {
  const explicit = payloadString(item.payload, ['summary', 'title'])
  if (explicit) return explicit
  const key = NOTIFICATION_TITLE_KEYS[item.event_code]
  return translate(key ? `client.notification.${key}` : 'client.notification.fallback')
}

export function clientNotificationBody(item: NotificationItem): string | null {
  const explicit = payloadString(item.payload, ['body', 'detail', 'message'])
  if (explicit) return explicit
  // Order events (CB-02) carry a denormalized order_number but no prose body —
  // surface it so the row identifies which order changed, not just that one did.
  const orderNumber = payloadString(item.payload, ['order_number'])
  if (orderNumber) return translate('client.notification.orderNumber', { number: orderNumber })
  // Inventory events carry the material the balance belongs to — same reason.
  const materialName = payloadString(item.payload, ['material_name'])
  return materialName ? translate('client.notification.material', { name: materialName }) : null
}

export function clientNotificationIconName(item: NotificationItem): string {
  const code = item.event_code
  if (code.startsWith('inventory')) return 'alert'
  if (code.startsWith('cutting')) return 'scissors'
  if (code.startsWith('order') || item.entity_type === 'order') return 'box'
  return 'inbox'
}
