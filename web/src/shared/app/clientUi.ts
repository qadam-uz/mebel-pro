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
  const digits = value.replace(/\D/g, '')
  if (digits.startsWith('998')) return `+${digits}`
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
  const percent = numeric <= 1 ? numeric * 100 : numeric
  return `${percent.toFixed(2)}%`
}

export function pluralUz(count: number, label: string): string {
  return `${new Intl.NumberFormat('uz-UZ').format(count)} ${label}`
}
