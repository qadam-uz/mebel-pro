import { DRAFT_LIMIT } from '@/shared/app/constants'
import type { NotificationItem } from '@/shared/stores/notifications'
import type { OrderStatus } from '@/shared/stores/orders'

export const clientStatusLabel: Record<OrderStatus, string> = {
  new: 'Joylashtirildi',
  confirmed: 'Tasdiqlandi',
  cutting: 'Ishlab chiqarishda',
  edge_banding: 'Ishlab chiqarishda',
  ready: 'Tayyor',
  completed: 'Topshirildi',
  cancelled: 'Bekor qilingan',
}

export const clientPhaseLabels = [
  'Joylashtirildi',
  'Tasdiqlandi',
  'Ishlab chiqarishda',
  'Tayyor',
  'Topshirildi',
] as const

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

export function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '-'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '-'
  // waste_percentage is always a 0..1 fraction (backend constrains it to [0,1])
  return `${(numeric * 100).toFixed(2)}%`
}

const CLIENT_ERROR_LABELS: Record<string, string> = {
  permission_denied: "Bu amal uchun ruxsat yo'q.",
  order_version_conflict: "Buyurtma holati o'zgardi — sahifani yangilab, qayta urinib ko'ring.",
  order_not_found: 'Buyurtma topilmadi.',
  order_cancel_not_allowed: "Bu buyurtmani hozir bekor qilib bo'lmaydi.",
  order_cancel_failed: "Buyurtmani bekor qilib bo'lmadi.",
  order_quote_failed: "Narxni hisoblab bo'lmadi. Qayta urinib ko'ring.",
  order_action_failed: "Amalni bajarib bo'lmadi. Qayta urinib ko'ring.",
  client_orders_load_failed: "Buyurtmalar ro'yxatini yuklab bo'lmadi.",
  client_order_load_failed: "Buyurtmani yuklab bo'lmadi.",
  branch_does_not_carry_panel: "Bu filialda kerakli panel materiali yo'q.",
  branch_does_not_carry_edge: "Bu filialda kerakli krom materiali yo'q.",
  part_too_large: 'Qism panel uchun juda katta.',
  part_too_small: 'Qism juda kichik.',
  draft_limit_exceeded: `Saqlangan chizmalar chegarasi (${DRAFT_LIMIT}) to'ldi — eskisini o'chiring.`,
  invalid_name: 'Ismingizni kiriting.',
  profile_update_failed: "Profilni saqlab bo'lmadi. Qayta urinib ko'ring.",
  password_change_failed: "Parolni o'zgartirib bo'lmadi. Qayta urinib ko'ring.",
}

const CLIENT_ERROR_FALLBACK = "Amal bajarilmadi. Qayta urinib ko'ring."

/**
 * Map a backend/store error code to Uzbek client copy. Unknown snake_case codes
 * fall back to a generic Uzbek message (a raw code is never shown to the user);
 * a value that is already a human sentence is returned unchanged.
 */
export function clientErrorLabel(
  code: string | null | undefined,
  fallback: string = CLIENT_ERROR_FALLBACK,
): string {
  if (!code) return fallback
  const mapped = CLIENT_ERROR_LABELS[code]
  if (mapped) return mapped
  if (/\s/.test(code)) return code
  return fallback
}

export function pluralUz(count: number, label: string): string {
  return `${new Intl.NumberFormat('uz-UZ').format(count)} ${label}`
}

/** Today's "09:00–18:00" working window, or "Bugun yopiq" when closed (CB-112). */
export function formatTodayHours(
  hours: { open: string | null; close: string | null } | null | undefined,
): string {
  if (!hours || !hours.open || !hours.close) return 'Bugun yopiq'
  return `${hours.open}–${hours.close}`
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
}

export function clientIconPath(name: string): string {
  return CLIENT_ICON_PATHS[name] ?? CLIENT_ICON_PATHS.box
}

// Notification presentation (CB-126): a per-family icon + a localized one-line
// title, so the bell never shows a raw snake/dotted event_code. Forward-compatible
// with the order.* events the backend will add (CB-02).
const NOTIFICATION_TITLES: Record<string, string> = {
  'inventory.low_stock': 'Zaxira tugayapti',
  'order.placed': 'Buyurtma joylandi',
  'order.confirmed': 'Buyurtma tasdiqlandi',
  'order.status_changed': "Buyurtma holati o'zgardi",
  'order.ready': 'Buyurtma tayyor',
  'order.cancelled': 'Buyurtma bekor qilindi',
  'order.completed': 'Buyurtma topshirildi',
}

function payloadString(payload: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = payload[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return null
}

export function clientNotificationTitle(item: NotificationItem): string {
  return (
    payloadString(item.payload, ['summary', 'title']) ??
    NOTIFICATION_TITLES[item.event_code] ??
    'Bildirishnoma'
  )
}

export function clientNotificationBody(item: NotificationItem): string | null {
  const explicit = payloadString(item.payload, ['body', 'detail', 'message'])
  if (explicit) return explicit
  // Order events (CB-02) carry a denormalized order_number but no prose body —
  // surface it so the row identifies which order changed, not just that one did.
  const orderNumber = payloadString(item.payload, ['order_number'])
  return orderNumber ? `Buyurtma № ${orderNumber}` : null
}

export function clientNotificationIconName(item: NotificationItem): string {
  const code = item.event_code
  if (code.startsWith('inventory')) return 'alert'
  if (code.startsWith('cutting')) return 'scissors'
  if (code.startsWith('order') || item.entity_type === 'order') return 'box'
  return 'inbox'
}
