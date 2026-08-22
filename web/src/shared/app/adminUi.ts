import { decorTypeLabel as sharedDecorTurLabel } from '@/shared/app/materialLabel'
import type { DropdownOption, NavGroupId, NavItem } from '@/shared/app/roleConfig'
import type {
  ActionLog,
  ErrorRecordStatus,
  DecorType,
  JobRunStatus,
  MaterialStatus,
  PlatformUserStatus,
  StatusChangeLog,
  WorkshopSummary,
} from '@/shared/stores/admin'
import type { NotificationItem } from '@/shared/stores/notifications'

// AB-51: pure audit-filter helpers, extracted so the substring-match predicate
// is unit-testable without mounting the view.
export function auditActionFields(row: ActionLog): string[] {
  return [row.action, row.entity_type ?? '', row.entity_id ?? '', row.summary ?? '', row.trace_id]
}

export function auditStatusFields(row: StatusChangeLog): string[] {
  return [row.entity_type, row.entity_id, row.from_status ?? '', row.to_status, row.reason ?? '']
}

export function matchesNeedle(fields: string[], needle: string): boolean {
  const trimmed = needle.trim().toLowerCase()
  if (!trimmed) return true
  return fields.join(' ').toLowerCase().includes(trimmed)
}

export type AdminNavMetricKey =
  | 'workshops'
  | 'manufacturers'
  | 'decors'
  | 'failedJobs'
  | 'openErrors'
  | 'operators'

export interface AdminNavMetric {
  key: AdminNavMetricKey
  value: number
  danger?: boolean
}

export function adminInitials(value: string | null | undefined, fallback = 'PL') {
  const parts = (value ?? '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return fallback
  if (parts.length === 1) return parts[0]?.slice(0, 2).toUpperCase() ?? fallback
  return `${parts[0]?.[0] ?? ''}${parts[1]?.[0] ?? ''}`.toUpperCase()
}

export function adminNavMetrics(input: {
  workshops: number
  manufacturers: number
  decors: number
  failedJobs: number
  openErrors: number
  operators: number
}) {
  return new Map<string, AdminNavMetric>([
    ['/admin/workshops', { key: 'workshops', value: input.workshops }],
    ['/admin/catalog/manufacturers', { key: 'manufacturers', value: input.manufacturers }],
    ['/admin/catalog/decors', { key: 'decors', value: input.decors }],
    [
      '/admin/platform/jobs',
      {
        key: 'failedJobs',
        value: input.failedJobs,
        danger: input.failedJobs > 0,
      },
    ],
    [
      '/admin/platform/errors',
      {
        key: 'openErrors',
        value: input.openErrors,
        danger: input.openErrors > 0,
      },
    ],
    ['/admin/platform/users', { key: 'operators', value: input.operators }],
  ])
}

/** Groups by the stable `NavGroupId`, not by the rendered label — grouping on
 *  display text would split or merge sections the moment a locale changed. The
 *  caller resolves `nav.group.<id>` for the heading. */
export function groupedNav(items: NavItem[]) {
  const groups: Array<{ id: NavGroupId; items: NavItem[] }> = []
  for (const item of items) {
    const id = item.group ?? 'platform'
    let group = groups.find((current) => current.id === id)
    if (!group) {
      group = { id, items: [] }
      groups.push(group)
    }
    group.items.push(item)
  }
  return groups
}

export function workshopStatusTone(status: WorkshopSummary['status']) {
  return status === 'active' ? 'admin-pill-success' : 'admin-pill-danger'
}

export function materialStatusTone(status: MaterialStatus) {
  return status === 'active' ? 'admin-pill-success' : 'admin-pill-muted'
}

export function platformUserStatusTone(status: PlatformUserStatus) {
  return status === 'active' ? 'admin-pill-success' : 'admin-pill-danger'
}

export function jobStatusTone(status: JobRunStatus | null | undefined) {
  if (status === 'ok') return 'admin-pill-success'
  if (status === 'failed') return 'admin-pill-danger'
  if (status === 'running') return 'admin-pill-info'
  if (status === 'skipped') return 'admin-pill-warning'
  return 'admin-pill-muted'
}

export function errorStatusTone(status: ErrorRecordStatus) {
  return status === 'open' ? 'admin-pill-danger' : 'admin-pill-success'
}

// AB-12: localized status labels so pills render Uzbek text (paired with the
// colour tone above), instead of the raw English enum value.
export function workshopStatusLabel(status: WorkshopSummary['status']) {
  return status === 'active' ? 'Faol' : 'Bloklangan'
}

export function platformUserStatusLabel(status: PlatformUserStatus) {
  return status === 'active' ? 'Faol' : 'Bloklangan'
}

export function materialStatusLabel(status: MaterialStatus) {
  return status === 'active' ? 'Faol' : 'Faol emas'
}

export function branchStatusLabel(status: string) {
  if (status === 'active') return 'Faol'
  if (status === 'temporarily_closed') return 'Vaqtincha yopiq'
  if (status === 'inactive') return 'Faol emas'
  return status
}

export function jobStatusLabel(status: JobRunStatus | null | undefined) {
  if (status === 'ok') return 'OK'
  if (status === 'failed') return 'Muvaffaqiyatsiz'
  if (status === 'running') return 'Ishlamoqda'
  if (status === 'skipped') return "O'tkazib yuborildi"
  return 'Ishga tushmagan'
}

export function errorStatusLabel(status: ErrorRecordStatus) {
  return status === 'open' ? 'Ochiq' : 'Hal qilingan'
}

const ADMIN_ENTITY_LABELS: Record<string, string> = {
  platform_user: 'Platforma admini',
  workshop_user: 'Ustaxona xodimi',
  client: 'Mijoz',
  workshop: 'Ustaxona',
  branch: 'Filial',
  manufacturer: 'Ishlab chiqaruvchi',
  material: 'Material',
  order: 'Buyurtma',
  error_record: 'Xatolik yozuvi',
  job_run: 'Fon vazifa yozuvi',
  session: 'Sessiya',
}

const ADMIN_ACTOR_LABELS: Record<string, string> = {
  platform_user: 'Platforma admini',
  workshop_user: 'Ustaxona xodimi',
  client: 'Mijoz',
  system: 'Tizim',
}

const ADMIN_STATUS_LABELS: Record<string, string> = {
  active: 'Faol',
  blocked: 'Bloklangan',
  inactive: 'Faol emas',
  temporarily_closed: 'Vaqtincha yopiq',
  open: 'Ochiq',
  resolved: 'Hal qilingan',
  pending: 'Kutilmoqda',
  new: 'Yangi',
  verified: 'Tekshirilgan',
  cutting: 'Kesilmoqda',
  banding: 'Kromka yopishtirilmoqda',
  ready: 'Tayyor',
  collected: 'Topshirilgan',
  cancelled: 'Bekor qilingan',
}

const ADMIN_JOB_LABELS: Record<string, string> = {
  'cleanup-expired-sessions': "Muddati o'tgan sessiyalarni tozalash",
}

const ADMIN_JOB_SCHEDULE_LABELS: Record<string, string> = {
  hourly: 'Har soatda',
  daily: 'Har kuni',
  weekly: 'Har hafta',
  manual: "Qo'lda",
}

function fallbackDisplayLabel(value: string) {
  return value.replace(/_/g, ' ').replace(/-/g, ' ')
}

export function adminEntityLabel(value: string | null | undefined) {
  if (!value) return '-'
  return ADMIN_ENTITY_LABELS[value] ?? fallbackDisplayLabel(value)
}

export function adminActorLabel(value: string | null | undefined) {
  if (!value) return '-'
  return ADMIN_ACTOR_LABELS[value] ?? adminEntityLabel(value)
}

export function adminStatusValueLabel(value: string | null | undefined) {
  if (!value) return '-'
  return ADMIN_STATUS_LABELS[value] ?? fallbackDisplayLabel(value)
}

export function adminStatusTransitionLabel(
  fromStatus: string | null | undefined,
  toStatus: string | null | undefined,
) {
  return `${adminStatusValueLabel(fromStatus)} -> ${adminStatusValueLabel(toStatus)}`
}

export function adminJobNameLabel(value: string | null | undefined) {
  if (!value) return '-'
  return ADMIN_JOB_LABELS[value] ?? fallbackDisplayLabel(value)
}

export function adminJobScheduleLabel(value: string | null | undefined) {
  if (!value) return '-'
  return ADMIN_JOB_SCHEDULE_LABELS[value] ?? fallbackDisplayLabel(value)
}

export function adminJobLogText(value: string | null | undefined) {
  if (!value) return "Jurnal hali yo'q"
  const pruned = value.match(/^Pruned (\d+) expired sessions$/)
  if (pruned) return `Muddati o'tgan ${pruned[1]} ta sessiya tozalandi`
  return value
}

// The admin app is not internationalized (zero `$t(` calls in its views), but the
// type→label map is: it is the same map the cutting editor and the order history
// render through, so it lives once in app/materialLabel.ts. Only the "no filter"
// case is a local literal.
export function decorTypeLabel(type: DecorType | null | undefined) {
  return type ? sharedDecorTurLabel(type) : 'Hammasi'
}

// AB-119: dashboard counters are plain tallies — grouped for readability, never
// abbreviated. An operator comparing "1 204" to "1 198" needs the exact digits.
export function adminCount(value: number) {
  return new Intl.NumberFormat('uz-UZ').format(value)
}

export function adminDate(value: string | null | undefined) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return `${padDatePart(date.getDate())}.${padDatePart(date.getMonth() + 1)}.${date.getFullYear()}`
}

export function adminDateTime(value: string | null | undefined) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return `${adminDate(value)} ${padDatePart(date.getHours())}:${padDatePart(date.getMinutes())}`
}

function padDatePart(value: number) {
  return String(value).padStart(2, '0')
}

function notificationPayloadText(item: NotificationItem, key: string) {
  const value = item.payload[key]
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function adminNotificationTitle(item: NotificationItem) {
  const summary = item.payload.summary
  if (typeof summary === 'string' && summary.trim()) return summary
  const jobName = notificationPayloadText(item, 'job_name')
  const errorCode =
    notificationPayloadText(item, 'error_code') ?? notificationPayloadText(item, 'code')
  if (item.event_code.includes('job')) {
    return jobName
      ? `Fon vazifa muvaffaqiyatsiz: ${adminJobNameLabel(jobName)}`
      : `Fon vazifa muvaffaqiyatsiz: ${item.event_code}`
  }
  if (item.event_code.includes('error')) {
    return errorCode ? `Xato ko'payishi: ${errorCode}` : `Xato ko'payishi: ${item.event_code}`
  }
  return item.event_code
}

export function adminNotificationDestination(item: NotificationItem) {
  if (item.entity_type === 'workshop' && item.entity_id) return `/admin/workshops/${item.entity_id}`
  if (item.entity_type === 'error_record' && item.entity_id) {
    return `/admin/platform/errors?record=${encodeURIComponent(item.entity_id)}`
  }
  const jobName = notificationPayloadText(item, 'job_name')
  if (item.event_code.includes('job')) {
    return jobName
      ? `/admin/platform/jobs?job=${encodeURIComponent(jobName)}`
      : '/admin/platform/jobs'
  }
  const errorCode =
    notificationPayloadText(item, 'error_code') ?? notificationPayloadText(item, 'code')
  if (item.event_code.includes('error')) {
    return errorCode
      ? `/admin/platform/errors?code=${encodeURIComponent(errorCode)}`
      : '/admin/platform/errors'
  }
  return '/admin/notifications'
}

/**
 * Backend `APIError` codes an operator can trigger from the platform app, in the
 * words the screen uses (QAD-163). The admin SPA had no such map: every failed
 * action landed on a per-call-site literal like `Amal bajarilmadi`, which is the
 * exact failure QAD-123 found in the workshop finance forms — four distinct,
 * individually explainable refusals wearing one shrug.
 *
 * Field-level rejections stay with `apiValidationMessage` in `adminValidation.ts`;
 * this map is for the action-level failures that surface as a toast.
 */
const ADMIN_ERROR_MESSAGES: Record<string, string> = {
  // Refusals
  permission_denied: "Bu amal uchun ruxsatingiz yo'q.",
  forbidden: "Bu amal uchun ruxsatingiz yo'q.",
  // Platform operators
  cannot_block_self: "O'z hisobingizni bloklab bo'lmaydi.",
  last_platform_operator: "Oxirgi faol adminni bloklab bo'lmaydi — avval boshqasini qo'shing.",
  user_not_found: "Admin topilmadi — ro'yxatni yangilang.",
  login_exists: 'Bu login band. Boshqa login tanlang.',
  weak_password: 'Parol yetarlicha kuchli emas — katta/kichik harf va raqam ishlating.',
  // Workshops
  workshop_not_found: "Ustaxona topilmadi — ro'yxatni yangilang.",
  invalid_status: "Bu holat allaqachon qo'yilgan.",
  reason_required: 'Sababni yozing.',
  // Catalog
  manufacturer_not_found: "Ishlab chiqaruvchi topilmadi — ro'yxatni yangilang.",
  manufacturer_name_exists: 'Bu ishlab chiqaruvchi allaqachon bor.',
  material_not_found: "Material topilmadi — ro'yxatni yangilang.",
  decor_not_found: "Dekor topilmadi — ro'yxatni yangilang.",
  decor_name_required: 'Dekor nomini yozing.',
  decor_exists: 'Bu ishlab chiqaruvchida shu kod bilan dekor allaqachon bor.',
  // Platform monitor
  error_not_found: "Xatolik yozuvi topilmadi — ro'yxatni yangilang.",
  job_not_found: "Bunday fon vazifa ro'yxatdan o'tmagan.",
  notification_not_found: "Bildirishnoma topilmadi — ro'yxatni yangilang.",
  // File upload (material images)
  unsupported_file_type: "Bu fayl turini yuklab bo'lmaydi — JPEG yoki PNG tanlang.",
  invalid_file_type: 'Bu fayl turi rasm sifatida biriktirilmaydi.',
  file_too_large: 'Fayl juda katta — kichikroq rasm tanlang.',
  file_not_found: 'Fayl topilmadi — rasmni qaytadan yuklang.',
  file_storage_unavailable: "Fayl ombori javob bermayapti. Birozdan so'ng qayta urinib ko'ring.",
}

/**
 * Uzbek copy for a backend error code. `fallback` is the call site's own
 * specific message — the one that names the action that failed — so an unmapped
 * code still says more than "something went wrong".
 */
export function adminErrorMessage(code: string | null | undefined, fallback: string): string {
  if (!code) return fallback
  return ADMIN_ERROR_MESSAGES[code] ?? fallback
}

export const allOption: DropdownOption = {
  value: 'all',
  label: 'Hammasi',
  meta: 'filtr yoqilmagan',
  status: 'pending',
}

export function dropdownOption(value: string, label: string, meta = ''): DropdownOption {
  return { value, label, meta, status: 'active' }
}

export function iconPath(name: string | undefined) {
  const paths: Record<string, string> = {
    dashboard: '<path d="M4 13h6V4H4v9Zm10 7h6V4h-6v16ZM4 20h6v-5H4v5Z"/>',
    factory: '<path d="M3 21V9l5 3V9l5 3V7l8 4v10H3Z"/><path d="M7 17h2m3 0h2m3 0h2"/>',
    package: '<path d="m3 7 9-4 9 4-9 4-9-4Z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>',
    activity: '<path d="M4 13h4l2-7 4 13 2-6h4"/>',
    alert: '<path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v5"/><path d="M12 17h.01"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
    users:
      '<path d="M16 20v-2a4 4 0 0 0-8 0v2"/><circle cx="12" cy="8" r="4"/><path d="M20 20v-2a3 3 0 0 0-3-3"/><path d="M4 20v-2a3 3 0 0 1 3-3"/>',
    book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15Z"/>',
    lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    external: '<path d="M14 3h7v7"/><path d="M10 14 21 3"/><path d="M21 14v6H4V3h6"/>',
    arrow: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    refresh:
      '<path d="M20 6v6h-6"/><path d="M4 18v-6h6"/><path d="M19 12a7 7 0 0 0-12-5L4 10"/><path d="M5 12a7 7 0 0 0 12 5l3-3"/>',
  }
  return paths[name ?? 'dashboard'] ?? paths.dashboard
}
