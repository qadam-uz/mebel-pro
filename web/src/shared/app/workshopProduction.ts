import { formatStockQuantity } from '@/shared/formatters'
import { translate, translatePlural } from '@/shared/i18n'

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
  const parts = translatePlural('finance.unit.parts', order.item_count)
  return panels ? `${parts} · ${translatePlural('finance.unit.panels', panels)}` : parts
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

export interface WorkshopStationOrder {
  status: string
  assigned_cutter_user_id: string | null
  assigned_edger_user_id: string | null
}

export interface WorkshopStationLoad {
  cutting: number
  banding: number
  /** Distinct staff currently holding work at each station. */
  cutters: string[]
  edgers: string[]
}

/**
 * Station-wide load for the dashboard's Stansiyalar panel: how much work sits at
 * each station right now, whoever it belongs to, plus who is holding it.
 *
 * Deliberately **not** `workshopProductionQueueCounts` and deliberately not the
 * `/workshop/production/queue` endpoint: both answer the *personal* question the
 * station terminal asks ("what is assigned to me"), and that endpoint is
 * personal for everyone — the owner included. The office view is the other
 * question, so it is derived from the order rows the dashboard already holds.
 *
 * The status sets mirror `list_production_queue` in the backend so the two never
 * disagree: the saw holds `confirmed` and `cutting`, the bander `edge_banding`.
 */
export function workshopStationLoad(orders: WorkshopStationOrder[]): WorkshopStationLoad {
  const cutting = orders.filter(
    (order) => order.status === 'confirmed' || order.status === 'cutting',
  )
  const banding = orders.filter((order) => order.status === 'edge_banding')
  const distinct = (ids: Array<string | null>) => [
    ...new Set(ids.filter((id): id is string => id !== null)),
  ]
  return {
    cutting: cutting.length,
    banding: banding.length,
    cutters: distinct(cutting.map((order) => order.assigned_cutter_user_id)),
    edgers: distinct(banding.map((order) => order.assigned_edger_user_id)),
  }
}

/**
 * "Aziz Tursunov" → "Aziz T." — the station card lists two or three people in a
 * one-third column, where full names wrap it into three lines. Initials would
 * fit too but read as an acronym rather than as a person, so the given name
 * stays whole and only the family name shortens.
 */
export function workerShortName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return ''
  if (parts.length === 1) return parts[0]
  return `${parts[0]} ${parts[1][0].toUpperCase()}.`
}

// The job sheet names parts by their detail name from the cutting result,
// falling back to the editor's D-numbering — never the raw part_ref (a uuid).
export function productionPartNames(
  partsSnapshot: { part_ref: string; name: string | null }[],
): Map<string, string> {
  const names = new Map<string, string>()
  partsSnapshot.forEach((part, index) => {
    names.set(part.part_ref, part.name?.trim() || `D${index + 1}`)
  })
  return names
}

// After a worker marks a panel as cut, which panel should the drawing show:
// the next uncut one in order, wrapping to the first uncut — or null when the
// order is fully marked (the drawing stays where it is).
export function nextUncutPanelId(
  panels: { id: string }[],
  marked: ReadonlySet<string>,
  justMarkedId: string,
): string | null {
  const uncut = panels.filter((panel) => !marked.has(panel.id))
  const after = panels.findIndex((panel) => panel.id === justMarkedId)
  const target = uncut.find((panel) => panels.indexOf(panel) > after) ?? uncut[0]
  return target?.id ?? null
}

// --- Station workspace (Kesish / Krom) ---------------------------------------

export type ProductionStationKey = 'cutting' | 'banding'

export interface ProductionStationJob {
  status: string
  cutting_started_at: string | null
  banding_started_at: string | null
  assigned_cutter: { id: string; full_name: string } | null
  assigned_edger: { id: string; full_name: string } | null
  item_count: number
  planned_panels: number
  planned_edge_lines: WorkshopEdgeMaterialDemand[]
}

// A cutting job is "running" once its status is `cutting` (legacy in-flight
// orders may predate the start stamp, so the status is the truth there); a
// banding job runs only once the edger's start stamp is set — `edge_banding`
// itself just means "arrived at the station".
export function isProductionJobStarted(job: ProductionStationJob, station: ProductionStationKey) {
  if (station === 'cutting') return job.status === 'cutting'
  return job.status === 'edge_banding' && job.banding_started_at !== null
}

export function partitionProductionJobs<T extends ProductionStationJob>(
  jobs: T[],
  station: ProductionStationKey,
) {
  const current: T[] = []
  const queued: T[] = []
  for (const job of jobs) {
    if (isProductionJobStarted(job, station)) current.push(job)
    else queued.push(job)
  }
  return { current, queued }
}

export function productionJobAssignee(job: ProductionStationJob, station: ProductionStationKey) {
  return station === 'cutting' ? job.assigned_cutter : job.assigned_edger
}

// One line of card meta: how big the job is, in the station's own units —
// parts + panels for the saw, metres of tape (plus parts) for the bander.
// Material names live on the Chizma sheet, one tap away.
export function productionJobMetaLine(job: ProductionStationJob, station: ProductionStationKey) {
  const counts = workshopQueuePartsLine({
    item_count: job.item_count,
    planned_panels: job.planned_panels,
    panels_used_snapshot: null,
  })
  if (station !== 'banding') return counts
  const totalMm = job.planned_edge_lines.reduce((sum, line) => sum + line.consumed_mm, 0)
  if (totalMm <= 0) return counts
  const edge = translate('finance.unit.edgeMetres', { length: formatStockQuantity(totalMm, 'm') })
  return `${edge} · ${translatePlural('finance.unit.parts', job.item_count)}`
}
