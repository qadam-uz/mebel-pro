import { parseSomToTiyin } from '@/shared/formatters'
import { translate, translatePlural } from '@/shared/i18n'
import { workshopStatusUz } from '@/shared/app/workshopUi'
import {
  activeWorkshopStatuses,
  type OrderPriceLine,
  type OrderStatus,
} from '@/shared/stores/orders'
import { metres } from '@/shared/stores/cutting'
import type { ProductionMode } from '@/shared/stores/workshop'

// A manual price adjustment — a discount (chegirma) or a surcharge (ustama).
// Both share the same input shape: a fixed sum entered in so'm, or a whole
// percent (1-100). The parse resolves the fixed sum to tiyin here (the so'm↔tiyin
// boundary), so the API always receives tiyin for `fixed`.
export type WorkshopAdjustmentKind = 'fixed' | 'percent'

export type WorkshopAdjustmentParseResult =
  | {
      ok: true
      payload: { kind: WorkshopAdjustmentKind; value: number; reason: string }
    }
  | { ok: false; message: string }

export function parseOrderAdjustmentDraft(
  kind: string,
  valueText: string,
  reasonText: string,
): WorkshopAdjustmentParseResult {
  const reason = reasonText.trim()
  if (kind === 'percent') {
    const percent = Number(valueText)
    if (!Number.isInteger(percent) || percent <= 0 || percent > 100) {
      return { ok: false, message: translate('orders.adjustment.percentError') }
    }
    if (!reason) return { ok: false, message: translate('orders.adjustment.reasonError') }
    return { ok: true, payload: { kind: 'percent', value: percent, reason } }
  }
  // Fixed sum is entered in so'm and stored as tiyin — parseSomToTiyin rejects
  // zero, blanks, and unparseable input (returns null).
  const tiyin = parseSomToTiyin(valueText)
  if (tiyin === null) {
    return { ok: false, message: translate('orders.adjustment.valueError') }
  }
  if (!reason) return { ok: false, message: translate('orders.adjustment.reasonError') }
  return { ok: true, payload: { kind: 'fixed', value: tiyin, reason } }
}

export type WorkshopOrderListActionKind =
  | 'approve'
  | 'assign'
  | 'start_cutting'
  | 'start_banding'
  | 'complete_cutting'
  | 'complete_banding'
  | 'mark_collected'
  | 'revert'
  | 'cancel'
  | 'detail'

export interface WorkshopOrderListAction {
  kind: WorkshopOrderListActionKind
  label: string
  danger?: boolean
}

export interface WorkshopOrderActionOrder {
  status: OrderStatus
  has_banding: boolean
  assigned_cutter_user_id: string | null
  assigned_edger_user_id: string | null
  banding_started_at: string | null
}

export interface WorkshopOrderActionAccess {
  canManageOrders: boolean
  canCompleteCutting: boolean
  canCompleteBanding: boolean
}

export interface WorkshopTimelineEvent {
  from_status: OrderStatus | null
  to_status: OrderStatus
  metadata: Record<string, unknown> | null
}

export function revertTargetLabelForOrder(order: {
  status: OrderStatus
  has_banding: boolean
}): string {
  if (order.status === 'cutting') return translate('orders.revertTarget.confirmed')
  if (order.status === 'edge_banding') return translate('orders.revertTarget.cutting')
  if (order.status === 'ready')
    return order.has_banding
      ? translate('orders.revertTarget.banding')
      : translate('orders.revertTarget.cutting')
  return ''
}

/** "kesishga qaytarish" — the revert action named by where it lands. */
function revertActionLabel(order: { status: OrderStatus; has_banding: boolean }): string {
  return translate('orders.action.revertTo', { target: revertTargetLabelForOrder(order) })
}

export function workshopOrderListActions(
  order: WorkshopOrderActionOrder,
  access: WorkshopOrderActionAccess,
): WorkshopOrderListAction[] {
  const actions: WorkshopOrderListAction[] = []

  // Assignment is metadata; the status moves when the assigned cutter starts.
  // The start action is the queued order's primary forward action for whoever
  // may perform it (the assigned master, or the office on-behalf).
  if (order.status === 'confirmed' && access.canCompleteCutting && order.assigned_cutter_user_id) {
    actions.push({ kind: 'start_cutting', label: translate('orders.action.startCutting') })
  }

  if (access.canManageOrders) {
    if (order.status === 'new') {
      actions.push({ kind: 'approve', label: translate('orders.action.approve') })
      actions.push({ kind: 'cancel', label: translate('orders.action.cancel'), danger: true })
    } else if (order.status === 'confirmed') {
      actions.push({ kind: 'assign', label: translate('orders.action.assign') })
      actions.push({ kind: 'cancel', label: translate('orders.action.cancel'), danger: true })
    }
  }

  if (order.status === 'cutting') {
    if (access.canCompleteCutting && order.assigned_cutter_user_id) {
      actions.push({ kind: 'complete_cutting', label: translate('orders.action.completeCutting') })
    }
    if (access.canManageOrders) {
      if (!order.assigned_cutter_user_id) {
        actions.push({ kind: 'assign', label: translate('orders.action.pickCutter') })
      }
      actions.push({ kind: 'revert', label: revertActionLabel(order), danger: true })
    }
  }

  if (order.status === 'edge_banding') {
    if (access.canCompleteBanding && order.assigned_edger_user_id) {
      if (!order.banding_started_at) {
        actions.push({ kind: 'start_banding', label: translate('orders.action.startBanding') })
      }
      actions.push({ kind: 'complete_banding', label: translate('orders.action.completeBanding') })
    }
    if (access.canManageOrders) {
      if (!order.assigned_edger_user_id) {
        actions.push({ kind: 'assign', label: translate('orders.action.pickEdger') })
      }
      actions.push({ kind: 'revert', label: revertActionLabel(order), danger: true })
    }
  }

  if (order.status === 'ready' && access.canManageOrders) {
    actions.push({ kind: 'mark_collected', label: translate('orders.action.markCollected') })
    actions.push({ kind: 'revert', label: revertActionLabel(order), danger: true })
  }

  if (
    access.canManageOrders &&
    !['completed', 'cancelled'].includes(order.status) &&
    !actions.some((action) => action.kind === 'cancel')
  ) {
    actions.push({ kind: 'cancel', label: translate('orders.action.cancel'), danger: true })
  }

  actions.push({ kind: 'detail', label: translate('orders.action.detail') })
  return actions
}

// --- The board's columns -----------------------------------------------------
//
// Full mode draws one column per active status. Simple mode draws three, and
// they are named as the three statuses that branch has — Yangi /
// Tayyorlanmoqda / Tayyor — not with a separate board vocabulary: the middle
// one groups `confirmed`, `cutting` and `edge_banding` (the same grouping the
// client track uses, so a full→simple leftover lands there naturally) and reads
// exactly as those cards' own pills do. Every label therefore comes from
// `workshopStatusUz` in the column's own mode; there is no `orders.board.*`
// copy any more. Cards in a grouped column still carry their own status pill,
// which the header can no longer supply on its own.

export interface WorkshopBoardColumn<T> {
  /** Stable key; in full mode it is the column's own status. */
  key: string
  label: string
  statuses: OrderStatus[]
  orders: T[]
}

const SIMPLE_BOARD_GROUPS: ReadonlyArray<{ key: string; statuses: OrderStatus[] }> = [
  { key: 'new', statuses: ['new'] },
  { key: 'inProduction', statuses: ['confirmed', 'cutting', 'edge_banding'] },
  { key: 'ready', statuses: ['ready'] },
]

export function workshopBoardColumns<T extends { status: OrderStatus }>(
  orders: T[],
  mode: ProductionMode,
): WorkshopBoardColumn<T>[] {
  const groups =
    mode === 'simple'
      ? SIMPLE_BOARD_GROUPS
      : activeWorkshopStatuses.map((status) => ({ key: status, statuses: [status] }))
  return groups.map((group) => ({
    key: group.key,
    // The group's first status stands for the whole column; in simple mode
    // `confirmed` resolves to «Tayyorlanmoqda», which is what its cards say too.
    label: workshopStatusUz(group.statuses[0], mode),
    statuses: [...group.statuses],
    orders: orders.filter((order) => group.statuses.includes(order.status)),
  }))
}

// --- The order detail's action matrix ----------------------------------------

export type WorkshopOrderPrimaryKey =
  | 'approve'
  | 'startCutting'
  | 'completeCutting'
  | 'startBanding'
  | 'completeBanding'
  /** Simple mode's composite **Tayyor** — the remaining spine in one tap. */
  | 'completeProduction'
  | 'markCollected'

export type WorkshopOrderMenuKey =
  | 'edit'
  | 'discount'
  | 'surcharge'
  | 'revert'
  /** Simple mode's composite **Orqaga** — the whole undo, one reason. */
  | 'undoProduction'
  | 'cancel'

export interface WorkshopOrderModeOrder {
  status: OrderStatus
  /** The ORDER's branch mode, off the payload — never the sidebar's selection. */
  mode: ProductionMode
  banding_started_at: string | null
  revision_draft_id?: string | null
}

export interface WorkshopOrderModeAccess {
  canManageOrders: boolean
  canCompleteCutting: boolean
  canCompleteBanding: boolean
}

/**
 * The single status-appropriate primary action, or `null` for a read-only state.
 *
 * Simple mode is `manage_orders` throughout: there is no assignment, so no
 * worker ever holds a forward action, and the two composite endpoints are gated
 * on that permission alone.
 */
export function workshopOrderPrimaryKey(
  order: WorkshopOrderModeOrder,
  access: WorkshopOrderModeAccess,
): WorkshopOrderPrimaryKey | null {
  if (order.mode === 'simple') {
    if (!access.canManageOrders) return null
    if (order.status === 'new') return 'approve'
    if (
      order.status === 'confirmed' ||
      order.status === 'cutting' ||
      order.status === 'edge_banding'
    )
      return 'completeProduction'
    if (order.status === 'ready') return 'markCollected'
    return null
  }
  if (order.status === 'new' && access.canManageOrders) return 'approve'
  if (order.status === 'confirmed' && (access.canManageOrders || access.canCompleteCutting))
    return 'startCutting'
  if (order.status === 'cutting' && access.canCompleteCutting) return 'completeCutting'
  if (order.status === 'edge_banding' && access.canCompleteBanding)
    return order.banding_started_at ? 'completeBanding' : 'startBanding'
  if (order.status === 'ready' && access.canManageOrders) return 'markCollected'
  return null
}

/** The overflow menu, in render order. Mode only moves one entry: the
 *  single-step `revert` is replaced by the whole-action `undoProduction`, which
 *  simple mode offers from `ready` only (there is no partial undo). */
export function workshopOrderMenuKeys(
  order: WorkshopOrderModeOrder,
  access: WorkshopOrderModeAccess,
): WorkshopOrderMenuKey[] {
  const keys: WorkshopOrderMenuKey[] = []
  const preProduction = order.status === 'new' || order.status === 'confirmed'
  if (access.canManageOrders && preProduction) {
    if (!order.revision_draft_id) keys.push('edit')
    keys.push('discount')
    keys.push('surcharge')
  }
  if (access.canManageOrders) {
    if (order.mode === 'simple') {
      if (order.status === 'ready') keys.push('undoProduction')
    } else if (['cutting', 'edge_banding', 'ready'].includes(order.status)) {
      keys.push('revert')
    }
  }
  if (access.canManageOrders && !['completed', 'cancelled'].includes(order.status)) {
    keys.push('cancel')
  }
  return keys
}

// --- The Tayyor dialog -------------------------------------------------------

export interface ProductionStockLine {
  materialId: string
  kind: 'panel' | 'edge'
  name: string
  /** Already formatted for display — sheets for a panel, metres for an edge. */
  amount: string
}

/**
 * What the composite Tayyor will take out of the warehouse, named before the
 * button. Straight off the order's own `price_lines`, which already carry the
 * SHOP share only (`own_panels` / `own_mm` are the client's and are not
 * decremented) — the same figures the money card prints, so the dialog can
 * never disagree with the receipt beside it.
 */
export function productionStockLines(priceLines: OrderPriceLine[]): ProductionStockLine[] {
  const lines: ProductionStockLine[] = []
  for (const line of priceLines) {
    if (line.kind === 'panel') {
      const sheets = line.panels_used ?? 0
      if (sheets > 0) {
        lines.push({
          materialId: line.material_id,
          kind: 'panel',
          name: line.material_name,
          amount: translatePlural('orders.unit.sheets', sheets),
        })
      }
      continue
    }
    const consumedMm = line.consumed_mm ?? 0
    if (consumedMm > 0) {
      lines.push({
        materialId: line.material_id,
        kind: 'edge',
        name: line.material_name,
        // `metres`, not the inventory formatter: the money card next to this
        // dialog prints the same figure through `metres`, and the two rounding
        // rules disagree at the third decimal (6.08 m vs 6.084 m). One screen,
        // one number.
        amount: metres(consumedMm),
      })
    }
  }
  return lines
}

/** Where a branch's last worker pick is remembered. A convenience preselect
 *  only — per branch, because the people at the saw are a branch's people. */
export function lastProductionWorkerKey(branchId: string, role: 'cutter' | 'edger') {
  return `mp:last-production-worker:${role}:${branchId}`
}

function summedRecordValue(value: unknown): number | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const total = Object.values(value).reduce((sum, item) => {
    const next = typeof item === 'number' && Number.isFinite(item) ? item : 0
    return sum + next
  }, 0)
  return total > 0 ? total : null
}

// Bare number — the unit sits in the message, which is where a locale can move
// or respell it.
function metresValue(mm: number) {
  return String(mm / 1000).replace(',', '.')
}

// A same-status `edited` event (orders.md "Revising a placed order") — the
// timeline names the revision instead of rendering "tasdiqlangan → tasdiqlangan".
export function isRevisionEvent(event: WorkshopTimelineEvent): boolean {
  return event.metadata?.edited === true
}

export function revisionTimelineDetails(
  event: WorkshopTimelineEvent,
  formatMoney: (tiyin: number) => string,
): string[] {
  const metadata = event.metadata
  if (!metadata || metadata.edited !== true) return []
  const details: string[] = []
  const previous =
    typeof metadata.previous_total_tiyin === 'number' ? metadata.previous_total_tiyin : null
  const next = typeof metadata.total_tiyin === 'number' ? metadata.total_tiyin : null
  if (previous !== null && next !== null && previous !== next) {
    details.push(
      translate('orders.timeline.price', {
        from: formatMoney(previous),
        to: formatMoney(next),
      }),
    )
  }
  if (typeof metadata.discount_cleared_tiyin === 'number') {
    details.push(
      translate('orders.timeline.discountCleared', {
        amount: formatMoney(metadata.discount_cleared_tiyin),
      }),
    )
  }
  if (metadata.edger_assignment_cleared === true) {
    details.push(translate('orders.timeline.edgerCleared'))
  }
  return details
}

export function productionTimelineDetails(
  event: WorkshopTimelineEvent,
  workerName: (id: string) => string,
): string[] {
  const metadata = event.metadata
  if (!metadata) return []
  const details: string[] = []
  const creditedUserId =
    typeof metadata.credited_user_id === 'string' ? metadata.credited_user_id : null
  if (creditedUserId)
    details.push(translate('orders.timeline.completedBy', { name: workerName(creditedUserId) }))

  const panelCount = summedRecordValue(metadata.panel_demands)
  if (panelCount !== null) details.push(translatePlural('orders.timeline.panelUsage', panelCount))

  const edgeMillimetres = summedRecordValue(metadata.edge_demands)
  if (edgeMillimetres !== null)
    details.push(translate('orders.timeline.edgeUsage', { value: metresValue(edgeMillimetres) }))

  return details
}

// Canonical forward lifecycle, used to lay out the header phase stepper and to
// detect rework (a transition that moves backwards along this order).
const PHASE_ORDER: OrderStatus[] = [
  'new',
  'confirmed',
  'cutting',
  'edge_banding',
  'ready',
  'completed',
]

// What the stepper draws on a SIMPLE-mode branch: Yangi → Tayyorlanmoqda →
// Tayyor → Olib ketildi. The spine underneath is unchanged — the composite
// Tayyor still writes every event — but a strip listing four steps nobody on
// that branch can move separately describes a machine, not the order. The
// middle step stands in for `confirmed`/`cutting`/`edge_banding`, and
// `workshopStatusUz(_, 'simple')` gives it the grouped word.
const SIMPLE_PHASE_ORDER: OrderStatus[] = ['new', 'confirmed', 'ready', 'completed']

export type OrderPhaseState = 'done' | 'current' | 'upcoming'

export interface OrderPhaseStep {
  status: OrderStatus
  state: OrderPhaseState
}

// The phases to draw for an order (skips edge_banding when it has no banding),
// each tagged done/current/upcoming. 'cancelled' is off-path — callers render a
// dedicated badge instead of a stepper. A completed order shows every step done.
//
// On a simple-mode branch the six collapse to four and the three production
// statuses all mark the middle step current, so a full→simple leftover in
// `cutting` reads as «Tayyorlanmoqda» rather than falling off the strip.
export function orderPhaseSteps(
  order: {
    status: OrderStatus
    has_banding: boolean
  },
  mode: ProductionMode = 'full',
): OrderPhaseStep[] {
  const simple = mode === 'simple'
  const path = simple
    ? SIMPLE_PHASE_ORDER
    : PHASE_ORDER.filter((status) => status !== 'edge_banding' || order.has_banding)
  const current =
    simple && (order.status === 'cutting' || order.status === 'edge_banding')
      ? 'confirmed'
      : order.status
  const currentIndex = path.indexOf(current)
  return path.map((status, index) => {
    let state: OrderPhaseState
    if (order.status === 'completed' || (currentIndex >= 0 && index < currentIndex)) {
      state = 'done'
    } else if (index === currentIndex) {
      state = 'current'
    } else {
      state = 'upcoming'
    }
    return { status, state }
  })
}

// How many times the order moved backwards (revert / rework). Cancellation is
// not a revert (it leaves the forward path), so it is ignored.
export function orderReworkCount(
  events: Array<{ from_status: OrderStatus | null; to_status: OrderStatus }>,
): number {
  return events.reduce((count, event) => {
    if (!event.from_status) return count
    const from = PHASE_ORDER.indexOf(event.from_status)
    const to = PHASE_ORDER.indexOf(event.to_status)
    return from >= 0 && to >= 0 && to < from ? count + 1 : count
  }, 0)
}
