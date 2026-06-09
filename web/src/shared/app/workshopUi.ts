import type { DropdownOption } from '@/shared/app/roleConfig'
import type { OrderStatus } from '@/shared/stores/orders'
import type { BranchStatus } from '@/shared/stores/workshop'

export const workshopStatusUz: Record<OrderStatus, string> = {
  new: 'Yangi',
  confirmed: 'Tasdiqlangan',
  cutting: 'Kesilmoqda',
  edge_banding: 'Kromda',
  ready: 'Tayyor',
  completed: 'Tugatilgan',
  cancelled: 'Bekor qilingan',
}

export const workshopStatusHint: Record<OrderStatus, string> = {
  new: 'koʻrib chiqish kerak',
  confirmed: 'kesuvchi kutilmoqda',
  cutting: 'arra oldida',
  edge_banding: 'krom yopishtirilmoqda',
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

export function branchOptions(
  branches: Array<{ id: string; name: string; address: string; status: string }>,
  allLabel = 'Barcha filiallar',
): DropdownOption[] {
  return [
    ...(branches.length > 1
      ? [
          {
            value: 'all',
            label: allLabel,
            meta: `${branches.length} filial`,
            status: 'active' as const,
          },
        ]
      : []),
    ...branches.map((branch) => ({
      value: branch.id,
      label: branch.name,
      meta: branch.status === 'temporarily_closed' ? 'vaqtincha yopiq' : branch.address,
      status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
    })),
  ]
}
