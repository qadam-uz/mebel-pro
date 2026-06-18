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
  draft_limit_exceeded: "Saqlangan chizmalar chegarasi (50) to'ldi — eskisini o'chiring.",
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
