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
  if (isOwner) return 'Egasi · barcha ruxsatlar'
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
