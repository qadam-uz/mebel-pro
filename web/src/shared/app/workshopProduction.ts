import { formatStockQuantity } from '@/shared/formatters'

export interface WorkshopQueuePanelSummary {
  item_count: number
  planned_panels: number
  panels_used_snapshot: number | null
}

export interface WorkshopEdgeMaterialDemand {
  material_label: string
  thickness_mm: string | null
  color: string | null
  consumed_mm: number
}

export interface WorkshopProductionQueueOrder {
  status: string
  assigned_cutter_user_id: string | null
  assigned_edger_user_id: string | null
}

export function workshopQueuePartsLine(order: WorkshopQueuePanelSummary) {
  const panels = order.planned_panels || order.panels_used_snapshot
  return `${order.item_count} qism${panels ? ` · ${panels} panel` : ''}`
}

export function workshopEdgeMaterialLabel(line: WorkshopEdgeMaterialDemand) {
  return [line.material_label, line.thickness_mm ? `${line.thickness_mm} mm` : null, line.color]
    .filter(Boolean)
    .join(' · ')
}

export function workshopQueueEdgeLine(lines: WorkshopEdgeMaterialDemand[]) {
  if (lines.length === 0) return 'krom rejasi'
  return lines
    .map(
      (line) => `${workshopEdgeMaterialLabel(line)}: ${formatStockQuantity(line.consumed_mm, 'm')}`,
    )
    .join(' · ')
}

export function workshopProductionQueueCounts(
  orders: WorkshopProductionQueueOrder[],
  userId: string | null | undefined,
) {
  if (!userId) return { cutting: 0, banding: 0, total: 0 }
  const cutting = orders.filter(
    (order) =>
      ['confirmed', 'cutting'].includes(order.status) && order.assigned_cutter_user_id === userId,
  ).length
  const banding = orders.filter(
    (order) => order.status === 'edge_banding' && order.assigned_edger_user_id === userId,
  ).length
  return { cutting, banding, total: cutting + banding }
}

export function resolveProductionCreditUser(
  assignedUserId: string | null | undefined,
  selectedUserId: string | null | undefined,
  canChooseWorker: boolean,
) {
  return (canChooseWorker ? selectedUserId || assignedUserId : assignedUserId) ?? null
}
