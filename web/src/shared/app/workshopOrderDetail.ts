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
