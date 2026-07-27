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
  new: "ko'rib chiqish kerak",
  confirmed: 'kesuvchi kutilmoqda',
  cutting: 'arra oldida',
  edge_banding: 'kromka yopishtirilmoqda',
  ready: 'olib ketishni kutmoqda',
  completed: 'mijoz olib ketgan',
  cancelled: "to'xtatilgan",
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

// The job is done — the books just went below zero because an arrival was never
// recorded. Informational only: raised as a `warn` toast next to the success
// one, never as danger, and never in place of completing the transition (QAD-150).
export const STOCK_SHORTFALL_MESSAGE = 'Omborda qoldiq yetarli emas'

export const permissionLabels: Record<string, string> = {
  view_orders: "Buyurtmalarni ko'rish (faqat o'qish)",
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

/**
 * The workshop's own name for chrome that shows the tenant, or `null` when
 * neither source has one and the caller should fall back to the generic label.
 *
 * Two sources, in this order: the owner-only settings row (so a rename shows
 * without a reload) and the `me` principal, which carries the name for staff —
 * the settings read 403s for them (QAD-168).
 */
export function workshopTenantName(...candidates: Array<string | null | undefined>) {
  for (const candidate of candidates) {
    const trimmed = candidate?.trim()
    if (trimmed) return trimmed
  }
  return null
}

export function initials(name: string | null | undefined, fallback = 'MP') {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return fallback
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

/** Longest slug we prefill; a prefix that eats the field helps nobody. */
const LOGIN_PREFIX_MAX = 12

/**
 * Suggest a login prefix from the workshop name — "Mebel Pro" → `mebelpro_`.
 * Logins are unique across the whole platform, so an unprefixed `admin` is
 * usually already taken; steering the owner toward a workshop-shaped name
 * avoids the collision. Purely a suggestion: the field stays fully editable.
 */
export function loginPrefix(workshopName: string | null | undefined) {
  if (!workshopName) return ''
  const slug = workshopName
    .toLowerCase()
    // Decompose so an accented letter keeps its ASCII base once the marks go;
    // everything else non-alphanumeric (spaces, punctuation, the turned comma
    // in o‘/g‘) simply drops.
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]/g, '')
    .slice(0, LOGIN_PREFIX_MAX)
  return slug ? `${slug}_` : ''
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
  cutter_required: 'Avval kesuvchini tayinlang.',
  edger_required: 'Avval kromka yopishtiruvchini tayinlang.',
  cutting_complete_failed: "Kesishni tugatib bo'lmadi. Qayta urinib ko'ring.",
  banding_complete_failed: "Kromka ishini tugatib bo'lmadi. Qayta urinib ko'ring.",
  expense_save_failed: "Xarajatni yozib bo'lmadi. Ma'lumotlarni tekshirib, qayta urinib ko'ring.",
  income_save_failed: "Tushumni yozib bo'lmadi. Ma'lumotlarni tekshirib, qayta urinib ko'ring.",
  ledger_void_failed: "Yozuvni bekor qilib bo'lmadi. Qayta urinib ko'ring.",
  statement_pdf_failed: "Akt sverkani yuklab bo'lmadi. Qayta urinib ko'ring.",
  grants_save_failed: "Ruxsatlarni saqlab bo'lmadi. Qayta urinib ko'ring.",
  password_reset_failed: "Parolni qaytarib bo'lmadi. Qayta urinib ko'ring.",
  user_save_failed:
    "Xodim profilini saqlab bo'lmadi. Ma'lumotlarni tekshirib, qayta urinib ko'ring.",
  user_block_failed: "Xodimni bloklab bo'lmadi. Qayta urinib ko'ring.",
  user_unblock_failed: "Xodimni faollashtirib bo'lmadi. Qayta urinib ko'ring.",
  sessions_revoke_failed: "Sessiyalarni yopib bo'lmadi. Qayta urinib ko'ring.",
  session_revoke_failed: "Sessiyani yopib bo'lmadi. Qayta urinib ko'ring.",
  // Finance ledger codes (QAD-123). The generic fallback is for genuinely
  // unexpected failures — a rejected save the operator can fix must say what
  // to fix, in the words the form uses.
  order_required: "Buyurtma to'lovi uchun buyurtma tanlang.",
  order_not_allowed: "Faqat buyurtma to'loviga buyurtma biriktiriladi.",
  scope_mismatch: 'Tushum filiali buyurtma filialiga mos emas.',
  order_payment_exceeds_total: "Summa buyurtma qoldig'idan oshib ketdi.",
  order_not_found: "Buyurtma topilmadi — ro'yxatdan qaytadan tanlang.",
  branch_required: 'Filialni tanlang — yozuv qaysi filialga tegishli ekani kerak.',
  forbidden: "Bu amal uchun ruxsatingiz yo'q.",
  invalid_amount: "Summa noldan katta bo'lishi kerak.",
  invalid_amount_range: 'Eng kichik summa eng kattasidan oshib ketmasin.',
  invalid_status: "Faqat yozilgan yozuvni o'zgartirish mumkin.",
  ledger_not_recorded: "Bu yozuv allaqachon bekor qilingan — uni o'zgartirib bo'lmaydi.",
  future_date_not_allowed: "Sana kelajakda bo'lishi mumkin emas.",
  description_required: 'Tavsifni yozing.',
  note_required: 'Izohni yozing — tuzatish sababsiz saqlanmaydi.',
  reason_required: 'Sababni yozing.',
  income_not_found: "Tushum topilmadi — ro'yxatni yangilang.",
  expense_not_found: "Xarajat topilmadi — ro'yxatni yangilang.",
  supplier_not_found: "Ta'minotchi topilmadi — ro'yxatdan qaytadan tanlang.",
  client_not_found: "Mijoz topilmadi — ro'yxatdan qaytadan tanlang.",
  adjustment_not_found: "Tuzatish topilmadi — ro'yxatni yangilang.",
  invalid_party: "Tuzatish bitta tomonga yoziladi: yo ta'minotchi, yo mijoz.",
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
