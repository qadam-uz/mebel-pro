import type { OrderStatus } from '@/shared/stores/orders'

export type WorkshopDiscountKind = 'fixed' | 'percent'

export interface WorkshopDiscountDraft {
  kind: WorkshopDiscountKind
  value: string
  reason: string
}

export type WorkshopDiscountParseResult =
  | {
      ok: true
      payload: { kind: WorkshopDiscountKind; value: number; reason: string }
    }
  | { ok: false; message: string }

export function discountDraftFromOrder(order: {
  discount_reason: string | null
}): WorkshopDiscountDraft {
  return {
    kind: 'fixed',
    value: '',
    reason: order.discount_reason ?? '',
  }
}

export function parseDiscountDraft(
  kind: string,
  valueText: string,
  reasonText: string,
): WorkshopDiscountParseResult {
  const value = Number(valueText)
  if (!Number.isInteger(value) || value < 0) {
    return { ok: false, message: "Chegirma qiymatini manfiy bo'lmagan butun son qilib kiriting." }
  }
  if (kind === 'percent' && value > 100) {
    return { ok: false, message: "Foiz 0 dan 100 gacha bo'lishi kerak." }
  }
  const reason = reasonText.trim()
  if (!reason) return { ok: false, message: 'Chegirma sababini kiriting.' }
  return {
    ok: true,
    payload: {
      kind: kind === 'percent' ? 'percent' : 'fixed',
      value,
      reason,
    },
  }
}

export type WorkshopOrderListActionKind =
  | 'approve'
  | 'assign'
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
  if (order.status === 'cutting') return 'tasdiqlangan holatiga'
  if (order.status === 'edge_banding') return 'kesishga'
  if (order.status === 'ready') return order.has_banding ? 'kromga' : 'kesishga'
  return ''
}

export function workshopOrderListActions(
  order: WorkshopOrderActionOrder,
  access: WorkshopOrderActionAccess,
): WorkshopOrderListAction[] {
  const actions: WorkshopOrderListAction[] = []

  if (access.canManageOrders) {
    if (order.status === 'new') {
      actions.push({ kind: 'approve', label: 'Tasdiqlash' })
      actions.push({ kind: 'cancel', label: 'Bekor qilish', danger: true })
    } else if (order.status === 'confirmed') {
      actions.push({ kind: 'assign', label: 'Tayinlash va boshlash' })
      actions.push({ kind: 'cancel', label: 'Bekor qilish', danger: true })
    }
  }

  if (order.status === 'cutting') {
    if (access.canCompleteCutting && order.assigned_cutter_user_id) {
      actions.push({ kind: 'complete_cutting', label: 'Kesish tugadi' })
    }
    if (access.canManageOrders) {
      if (!order.assigned_cutter_user_id) {
        actions.push({ kind: 'assign', label: 'Kesuvchini tanlash' })
      }
      actions.push({
        kind: 'revert',
        label: `${revertTargetLabelForOrder(order)} qaytarish`,
        danger: true,
      })
    }
  }

  if (order.status === 'edge_banding') {
    if (access.canCompleteBanding && order.assigned_edger_user_id) {
      actions.push({ kind: 'complete_banding', label: 'Krom tugadi' })
    }
    if (access.canManageOrders) {
      if (!order.assigned_edger_user_id) {
        actions.push({ kind: 'assign', label: 'Kromchini tanlash' })
      }
      actions.push({
        kind: 'revert',
        label: `${revertTargetLabelForOrder(order)} qaytarish`,
        danger: true,
      })
    }
  }

  if (order.status === 'ready' && access.canManageOrders) {
    actions.push({ kind: 'mark_collected', label: 'Mijoz olib ketdi' })
    actions.push({
      kind: 'revert',
      label: `${revertTargetLabelForOrder(order)} qaytarish`,
      danger: true,
    })
  }

  if (
    access.canManageOrders &&
    !['completed', 'cancelled'].includes(order.status) &&
    !actions.some((action) => action.kind === 'cancel')
  ) {
    actions.push({ kind: 'cancel', label: 'Bekor qilish', danger: true })
  }

  actions.push({ kind: 'detail', label: 'Tafsilotlar' })
  return actions
}

function summedRecordValue(value: unknown): number | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const total = Object.values(value).reduce((sum, item) => {
    const next = typeof item === 'number' && Number.isFinite(item) ? item : 0
    return sum + next
  }, 0)
  return total > 0 ? total : null
}

function formatMetres(mm: number) {
  return `${String(mm / 1000).replace(',', '.')} m`
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
  if (creditedUserId) details.push(`Bajardi: ${workerName(creditedUserId)}`)

  const panelCount = summedRecordValue(metadata.panel_demands)
  if (panelCount !== null) details.push(`Panel sarfi: ${panelCount} panel`)

  const edgeMillimetres = summedRecordValue(metadata.edge_demands)
  if (edgeMillimetres !== null) details.push(`Krom sarfi: ${formatMetres(edgeMillimetres)}`)

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

export type OrderPhaseState = 'done' | 'current' | 'upcoming'

export interface OrderPhaseStep {
  status: OrderStatus
  state: OrderPhaseState
}

// The phases to draw for an order (skips edge_banding when it has no banding),
// each tagged done/current/upcoming. 'cancelled' is off-path — callers render a
// dedicated badge instead of a stepper. A completed order shows every step done.
export function orderPhaseSteps(order: {
  status: OrderStatus
  has_banding: boolean
}): OrderPhaseStep[] {
  const path = PHASE_ORDER.filter((status) => status !== 'edge_banding' || order.has_banding)
  const currentIndex = path.indexOf(order.status)
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
