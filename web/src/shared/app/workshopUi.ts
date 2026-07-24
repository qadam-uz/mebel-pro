import type { OrderStatus } from '@/shared/stores/orders'
import type { BranchStatus, StockTransactionType } from '@/shared/stores/workshop'

export const workshopStatusUz: Record<OrderStatus, string> = {
  new: 'Yangi',
  confirmed: 'Tasdiqlangan',
  cutting: 'Kesilmoqda',
  edge_banding: 'Kromkada',
  ready: 'Tayyor',
  completed: 'Tugatilgan',
  cancelled: 'Bekor qilingan',
}

export const workshopStatusHint: Record<OrderStatus, string> = {
  new: 'koʻrib chiqish kerak',
  confirmed: 'kesuvchi kutilmoqda',
  cutting: 'arra oldida',
  edge_banding: 'kromka yopishtirilmoqda',
  ready: 'olib ketishni kutmoqda',
  completed: 'mijoz olib ketgan',
  cancelled: 'toʻxtatilgan',
}

export function orderPillClass(status: OrderStatus) {
  if (status === 'completed') return 'pill p-dn'
  if (status === 'cancelled') return 'pill p-bad'
  if (status === 'ready') return 'pill p-rdy'
  if (status === 'cutting') return 'pill p-cut'
  if (status === 'edge_banding') return 'pill p-eb'
  if (status === 'confirmed') return 'pill p-conf'
  return 'pill p-new'
}

// A saved walk-in draft carries no DB status; its readiness is derived from
// whether a cutting result has been chosen. `has_result` → ready for checkout;
// otherwise the operator still has parts to finish.
export function workshopDraftStatus(hasResult: boolean): { label: string; pill: string } {
  return hasResult
    ? { label: 'Tayyor — buyurtma berish mumkin', pill: 'pill p-rdy' }
    : { label: 'Tahrirlanmoqda', pill: 'pill p-new' }
}

export const branchStatusUz: Record<BranchStatus, string> = {
  active: 'Faol',
  temporarily_closed: 'Vaqtincha yopiq',
  inactive: 'Faol emas',
}

export function branchPillClass(status: BranchStatus) {
  if (status === 'active') return 'pill p-ok'
  if (status === 'temporarily_closed') return 'pill p-warn'
  return 'pill p-dn'
}

export const stockTransactionTypeUz: Record<StockTransactionType, string> = {
  stock_in: 'Kirim',
  consume: 'Sarf',
  restore: 'Qaytarish',
  adjust: 'Tuzatish',
}

export function stockTransactionTypeLabel(type: StockTransactionType) {
  return stockTransactionTypeUz[type] ?? type
}

export const permissionLabels: Record<string, string> = {
  view_dashboard: 'Asosiy panel',
  manage_orders: 'Buyurtmalar',
  process_production: 'Ishlab chiqarish',
  manage_catalog: 'Material katalogi',
  manage_inventory: 'Ombor',
  manage_finance: 'Moliya yozuvlari',
  view_finance_reports: 'Moliya hisobotlari',
}

export function grantSummary(
  isOwner: boolean,
  grants: Array<{ permission: string; branch_id: string }>,
) {
  if (isOwner) return 'Rahbar · barcha ruxsatlar'
  if (grants.length === 0) return 'Ruxsat berilmagan'
  const branches = new Set(grants.map((grant) => grant.branch_id))
  const permissions = new Set(grants.map((grant) => grant.permission))
  return `${permissions.size} grant · ${branches.size} filial`
}

export function initials(name: string | null | undefined, fallback = 'MP') {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return fallback
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export const workshopErrorMessages: Record<string, string> = {
  permission_denied: "Bu amal uchun ruxsatingiz yo'q.",
  order_action_failed: "Buyurtma amali bajarilmadi. Qayta urinib ko'ring.",
  order_version_conflict:
    "Buyurtma boshqa joyda o'zgargan. Ma'lumot yangilandi, qayta urinib ko'ring.",
  order_edit_not_allowed:
    "Bu buyurtmani endi tahrirlab bo'lmaydi — ishlab chiqarish boshlangan yoki buyurtma yopilgan.",
  order_revision_not_found: 'Bu buyurtmada ochiq tahrir topilmadi.',
  order_revision_branch_locked:
    "Tahrir buyurtmaning filialida qoladi — filialni o'zgartirib bo'lmaydi.",
  order_revision_failed: "Tahrirni boshlab bo'lmadi. Qayta urinib ko'ring.",
  cutting_already_started: "Kesish allaqachon boshlangan — kesuvchini o'zgartirib bo'lmaydi.",
  banding_already_started: "Kromka ishi allaqachon boshlangan — ustani o'zgartirib bo'lmaydi.",
  cutting_complete_failed: "Kesishni tugatib bo'lmadi. Qayta urinib ko'ring.",
  banding_complete_failed: "Kromka ishini tugatib bo'lmadi. Qayta urinib ko'ring.",
  expense_save_failed: "Xarajatni yozib bo'lmadi. Ma'lumotlarni tekshirib, qayta urinib ko'ring.",
  income_save_failed: "Tushumni yozib bo'lmadi. Ma'lumotlarni tekshirib, qayta urinib ko'ring.",
  ledger_void_failed: "Yozuvni bekor qilib bo'lmadi. Qayta urinib ko'ring.",
  grants_save_failed: "Ruxsatlarni saqlab bo'lmadi. Qayta urinib ko'ring.",
  password_reset_failed: "Parolni qaytarib bo'lmadi. Qayta urinib ko'ring.",
  user_save_failed:
    "Xodim profilini saqlab bo'lmadi. Ma'lumotlarni tekshirib, qayta urinib ko'ring.",
  user_block_failed: "Xodimni bloklab bo'lmadi. Qayta urinib ko'ring.",
  user_unblock_failed: "Xodimni faollashtirib bo'lmadi. Qayta urinib ko'ring.",
  sessions_revoke_failed: "Sessiyalarni yopib bo'lmadi. Qayta urinib ko'ring.",
  session_revoke_failed: "Sessiyani yopib bo'lmadi. Qayta urinib ko'ring.",
}

export function workshopErrorMessage(code: string | null | undefined) {
  if (!code) return "Amal bajarilmadi. Qayta urinib ko'ring."
  return workshopErrorMessages[code] ?? "Amal bajarilmadi. Qayta urinib ko'ring."
}

export interface DashboardSectionFailure {
  /** Uzbek section label shown to the operator; also the per-section dedupe key. */
  section: string
  code: string
  traceId: string | null
}

const dashboardFailureCauses: Record<string, string> = {
  permission_denied: "ruxsat yo'q",
  internal_error: 'serverda ichki xatolik',
  validation_error: "so'rov xato tuzilgan",
  not_found: "ma'lumot topilmadi",
}

/**
 * One diagnostic line per failed dashboard section: the named cause plus the
 * raw code and trace_id support needs to find the incident. The backend stamps
 * trace_id on every error body, so a missing trace means the response never
 * came from the app — reported as a connection failure rather than a
 * meaningless "trace_id: unavailable".
 */
export function dashboardFailureLine(failure: DashboardSectionFailure): string {
  if (failure.traceId === null) {
    return `${failure.section} — serverga ulanib bo'lmadi`
  }
  const cause = dashboardFailureCauses[failure.code] ?? 'kutilmagan xatolik'
  return `${failure.section} — ${cause} (${failure.code} · trace: ${failure.traceId})`
}
