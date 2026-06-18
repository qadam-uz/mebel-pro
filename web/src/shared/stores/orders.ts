import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  ApiError,
  api,
  apiErrorCode,
  apiTraceId,
  captureApiError,
  withQuery,
} from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import { downloadBlob } from '@/shared/app/downloadBlob'
import type { CuttingResult, MaterialSource } from '@/shared/stores/cutting'

export type OrderStatus =
  | 'new'
  | 'confirmed'
  | 'cutting'
  | 'edge_banding'
  | 'ready'
  | 'completed'
  | 'cancelled'

export interface OrderQuote {
  draft_id: string
  branch_id: string
  branch_name: string
  branch_address: string
  branch_phone: string
  today_hours: { open: string | null; close: string | null }
  subtotal_cutting_tiyin: number
  subtotal_materials_tiyin: number
  subtotal_edge_banding_tiyin: number
  total_tiyin: number
}

export interface OrderItem {
  id: string
  material_id: string
  material_source: MaterialSource
  material_snapshot: Record<string, unknown>
  part_ref: string
  length_mm: number
  width_mm: number
  quantity: number
  edge_top: Record<string, unknown> | null
  edge_bottom: Record<string, unknown> | null
  edge_left: Record<string, unknown> | null
  edge_right: Record<string, unknown> | null
  unit_cutting_price_tiyin: number
  unit_material_price_tiyin: number
  edge_cost_tiyin: number
  line_total_tiyin: number
}

export interface OrderEvent {
  id: string
  from_status: OrderStatus | null
  to_status: OrderStatus
  actor_type: 'client' | 'workshop_user' | 'system' | 'platform_user'
  actor_user_id: string | null
  actor_client_id: string | null
  reason: string | null
  metadata: Record<string, unknown> | null
  changed_at: string
}

export interface OrderStockWarning {
  material_id: string
  material_name: string
  kind: string
  on_hand: number
  required: number
  projected_after: number
}

export interface OrderSettlement {
  total_tiyin: number
  recorded_tiyin: number
  balance_tiyin: number
}

export interface WorkshopWorkerOption {
  id: string
  full_name: string
  is_owner: boolean
  home_branch_id: string | null
}

export interface OrderSummary {
  id: string
  order_number: string
  client_id: string
  client_name: string
  client_phone: string
  contact_name: string
  contact_phone: string
  workshop_id: string
  workshop_name: string
  branch_id: string
  branch_name: string
  branch_address: string
  branch_phone: string
  today_hours: { open: string | null; close: string | null }
  cutting_result_id: string
  status: OrderStatus
  version: number
  note_client: string | null
  note_workshop: string | null
  subtotal_cutting_tiyin: number
  subtotal_materials_tiyin: number
  subtotal_edge_banding_tiyin: number
  discount_tiyin: number
  discount_reason: string | null
  discount_applied_by_user_id: string | null
  total_tiyin: number
  currency: 'UZS'
  assigned_cutter_user_id: string | null
  assigned_edger_user_id: string | null
  cutter_user_id: string | null
  cut_completed_at: string | null
  panels_used_snapshot: number | null
  cut_count_snapshot: number | null
  edger_user_id: string | null
  edge_completed_at: string | null
  edge_length_snapshot: Record<string, number> | null
  picked_up_at: string | null
  confirmed_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  created_at: string
  updated_at: string
  item_count: number
  has_banding: boolean
  stock_warnings: OrderStockWarning[]
}

export interface OrderDetail extends OrderSummary {
  items: OrderItem[]
  events: OrderEvent[]
  cutting_result: CuttingResult | null
  settlement: OrderSettlement | null
}

export const activeWorkshopStatuses: OrderStatus[] = [
  'new',
  'confirmed',
  'cutting',
  'edge_banding',
  'ready',
]

export const useOrdersStore = defineStore('orders', () => {
  const clientOrders = ref<OrderSummary[]>([])
  const workshopOrders = ref<OrderSummary[]>([])
  const currentOrder = ref<OrderDetail | null>(null)
  const workerOptions = ref<WorkshopWorkerOption[]>([])
  const loading = ref(false)
  const actionLoading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  // PDF download feedback (CB-17): id of the order currently downloading, plus a
  // transient error + trace for the last failed download.
  const downloadingId = ref<string | null>(null)
  const downloadError = ref<string | null>(null)
  const downloadTraceId = ref<string | null>(null)

  function captureError(errorValue: unknown, fallback: string) {
    const captured = captureApiError(errorValue, fallback)
    error.value = captured.code
    traceId.value = captured.traceId
  }

  async function quoteForDraft(draftId: string, branchId: string) {
    return await api.get<OrderQuote>(
      withQuery('/client/orders/quote', { draft_id: draftId, branch_id: branchId }),
      authInit(),
    )
  }

  // Quote a draft against many branches concurrently, capturing each branch's
  // OWN error code in the result rather than reading the shared `error`
  // singleton a sibling request may have overwritten (the CB-20 race). Returns
  // a quote per successful branch and a code (or null = generic) per failed one.
  async function quoteBranches(draftId: string, branchIds: string[]) {
    const quotes: Record<string, OrderQuote> = {}
    const errors: Record<string, string | null> = {}
    let firstErrorTraceId: string | null = null
    await Promise.all(
      branchIds.map(async (branchId) => {
        try {
          quotes[branchId] = await quoteForDraft(draftId, branchId)
        } catch (errorValue) {
          // Preserve the real per-branch code (branch_does_not_carry_*,
          // branch_closed, missing_*_rate) so the view can name the problem
          // (CB-19/CB-20); fall back to the 403 mapping, then null.
          errors[branchId] =
            apiErrorCode(errorValue) ??
            (errorValue instanceof ApiError && errorValue.status === 403
              ? 'permission_denied'
              : null)
          if (firstErrorTraceId === null) firstErrorTraceId = apiTraceId(errorValue)
        }
      }),
    )
    return { quotes, errors, firstErrorTraceId }
  }

  async function createClientOrder(payload: unknown) {
    actionLoading.value = true
    try {
      const order = await api.post<OrderDetail>('/client/orders', payload, authInit())
      currentOrder.value = order
      clientOrders.value = [order, ...clientOrders.value.filter((item) => item.id !== order.id)]
      return order
    } finally {
      actionLoading.value = false
    }
  }

  async function loadClientOrders(filters: { status?: string; search?: string } = {}) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      clientOrders.value = await api.get<OrderSummary[]>(
        withQuery('/client/orders', filters),
        authInit(),
      )
    } catch (errorValue) {
      captureError(errorValue, 'client_orders_load_failed')
    } finally {
      loading.value = false
    }
  }

  async function loadClientOrder(id: string) {
    await loadOrder(`/client/orders/${id}`, 'client_order_load_failed')
  }

  async function cancelClientOrder(id: string, version: number, reason: string) {
    return await mutate(`/client/orders/${id}/cancel`, { version, reason })
  }

  async function loadWorkshopOrders(
    filters: { branch_id?: string | null; status?: string; search?: string } = {},
  ) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      workshopOrders.value = await api.get<OrderSummary[]>(
        withQuery('/workshop/orders', filters),
        authInit(),
      )
    } catch (errorValue) {
      captureError(errorValue, 'workshop_orders_load_failed')
    } finally {
      loading.value = false
    }
  }

  async function loadWorkshopOrder(id: string) {
    await loadOrder(`/workshop/orders/${id}`, 'workshop_order_load_failed')
  }

  async function loadWorkers(branchId: string) {
    workerOptions.value = await api.get<WorkshopWorkerOption[]>(
      withQuery('/workshop/orders/workers', { branch_id: branchId }),
      authInit(),
    )
  }

  async function approve(id: string, version: number) {
    return await mutate(`/workshop/orders/${id}/approve`, { version })
  }

  async function assign(id: string, payload: unknown) {
    return await mutate(`/workshop/orders/${id}/assign`, payload)
  }

  async function cuttingDone(id: string, payload: unknown) {
    return await mutate(`/workshop/orders/${id}/cutting-done`, payload)
  }

  async function bandingDone(id: string, payload: unknown) {
    return await mutate(`/workshop/orders/${id}/banding-done`, payload)
  }

  async function markCollected(id: string, version: number) {
    return await mutate(`/workshop/orders/${id}/mark-collected`, { version })
  }

  async function revert(id: string, version: number, reason: string) {
    return await mutate(`/workshop/orders/${id}/revert`, { version, reason })
  }

  async function cancelWorkshopOrder(id: string, version: number, reason: string) {
    return await mutate(`/workshop/orders/${id}/cancel`, { version, reason })
  }

  async function discount(id: string, payload: unknown) {
    return await mutate(`/workshop/orders/${id}/discount`, payload)
  }

  async function updateNote(id: string, note: string | null) {
    return await mutate(`/workshop/orders/${id}/note`, { note_workshop: note }, 'patch')
  }

  async function downloadClientPdf(orderId: string) {
    await downloadPdf(
      `/client/orders/${orderId}/cutting/pdf`,
      `order-${orderId}-cutting.pdf`,
      orderId,
    )
  }

  async function downloadWorkshopPdf(orderId: string) {
    await downloadPdf(
      `/workshop/orders/${orderId}/cutting/pdf`,
      `order-${orderId}-cutting.pdf`,
      orderId,
    )
  }

  async function loadOrder(path: string, fallback: string) {
    loading.value = true
    error.value = null
    traceId.value = null
    currentOrder.value = null
    try {
      currentOrder.value = await api.get<OrderDetail>(path, authInit())
    } catch (errorValue) {
      captureError(errorValue, fallback)
    } finally {
      loading.value = false
    }
  }

  async function mutate(path: string, payload: unknown, method: 'post' | 'patch' = 'post') {
    actionLoading.value = true
    error.value = null
    traceId.value = null
    try {
      const order =
        method === 'post'
          ? await api.post<OrderDetail>(path, payload, authInit())
          : await api.patch<OrderDetail>(path, payload, authInit())
      currentOrder.value = order
      patchOrder(order)
      return order
    } catch (errorValue) {
      // On an optimistic-concurrency conflict the cached version is stale; refetch
      // the order so the next attempt carries the server's current version.
      if (apiErrorCode(errorValue) === 'order_version_conflict') {
        const match = path.match(/\/(client|workshop)\/orders\/([^/]+)\//)
        const orderId = match?.[2]
        if (orderId) {
          if (match?.[1] === 'client') await loadClientOrder(orderId)
          else await loadWorkshopOrder(orderId)
        }
      }
      captureError(errorValue, 'order_action_failed')
      throw errorValue
    } finally {
      actionLoading.value = false
    }
  }

  function patchOrder(order: OrderSummary) {
    clientOrders.value = [order, ...clientOrders.value.filter((item) => item.id !== order.id)]
    workshopOrders.value = [order, ...workshopOrders.value.filter((item) => item.id !== order.id)]
  }

  async function downloadPdf(path: string, filename: string, id: string) {
    downloadingId.value = id
    downloadError.value = null
    downloadTraceId.value = null
    try {
      await downloadBlob(path, filename, authInit())
    } catch (errorValue) {
      downloadError.value = "PDF'ni yuklab bo'lmadi. Qayta urinib ko'ring."
      downloadTraceId.value = apiTraceId(errorValue)
    } finally {
      downloadingId.value = null
    }
  }

  return {
    clientOrders,
    workshopOrders,
    currentOrder,
    workerOptions,
    loading,
    actionLoading,
    error,
    traceId,
    downloadingId,
    downloadError,
    downloadTraceId,
    quoteForDraft,
    quoteBranches,
    createClientOrder,
    loadClientOrders,
    loadClientOrder,
    cancelClientOrder,
    loadWorkshopOrders,
    loadWorkshopOrder,
    loadWorkers,
    approve,
    assign,
    cuttingDone,
    bandingDone,
    markCollected,
    revert,
    cancelWorkshopOrder,
    discount,
    updateNote,
    downloadClientPdf,
    downloadWorkshopPdf,
  }
})
