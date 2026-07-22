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
import { ORDERS_PAGE_LIMIT } from '@/shared/app/constants'
import { downloadBlob } from '@/shared/app/downloadBlob'
import type { CuttingDraft, CuttingResult, MaterialSource } from '@/shared/stores/cutting'

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
  panels_used: number
  cutting_rate_tiyin: number
  material_lines: MaterialPriceLine[]
  edge_lines: EdgePriceLine[]
}

export interface MaterialPriceLine {
  material_id: string
  material_name: string
  panels_used: number
  unit_price_tiyin: number
  line_total_tiyin: number
}

export interface EdgePriceLine {
  material_id: string
  material_name: string
  consumed_mm: number
  material_cost_tiyin: number
  service_cost_tiyin: number
  line_total_tiyin: number
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

export interface OrderEdgeMaterialDemand {
  material_id: string
  material_label: string
  thickness_mm: string | null
  color: string | null
  consumed_mm: number
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
  home_branch_id: string
}

// Walk-in order placed by staff on the client's behalf: same shape as the
// client create, plus the explicit draft/branch pair the checkout quoted.
export interface WorkshopOrderCreatePayload {
  draft_id: string
  branch_id: string
  contact_name: string
  contact_phone: string
  // Matches the backend field so a staff note isn't silently dropped.
  note_client?: string | null
}

export interface WorkshopOrderFilters {
  branch_id?: string | null
  status?: string
  search?: string
  date_from?: string | null
  date_to?: string | null
  assigned_cutter_user_id?: string | null
  assigned_edger_user_id?: string | null
  limit?: number
  offset?: number
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
  cutter_assigned_at: string | null
  edger_assigned_at: string | null
  cutting_started_at: string | null
  banding_started_at: string | null
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
  planned_panels: number
  planned_edge_lines: OrderEdgeMaterialDemand[]
  stock_warnings: OrderStockWarning[]
}

export interface OrderDetail extends OrderSummary {
  items: OrderItem[]
  events: OrderEvent[]
  cutting_result: CuttingResult | null
  settlement: OrderSettlement | null
  // The order's open revision draft (workshop detail only) — lets the UI offer
  // resume/discard instead of starting a fresh revision.
  revision_draft_id: string | null
}

export const activeWorkshopStatuses: OrderStatus[] = [
  'new',
  'confirmed',
  'cutting',
  'edge_banding',
  'ready',
]

const QUOTE_BRANCH_BATCH_SIZE = 50

export const useOrdersStore = defineStore('orders', () => {
  const clientOrders = ref<OrderSummary[]>([])
  const ordersHasMore = ref(false)
  const workshopOrders = ref<OrderSummary[]>([])
  const recentWorkshopOrders = ref<OrderSummary[]>([])
  const workshopOrdersHasMore = ref(false)
  const currentOrder = ref<OrderDetail | null>(null)
  const workerOptions = ref<WorkshopWorkerOption[]>([])
  const loading = ref(false)
  const actionLoading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  // Action (mutate) failures are kept separate from load failures: a cancel/approve
  // 409 must surface inline, NOT collapse the whole detail page to its load-error
  // state (the page gates on `error`). Views read these for the inline message.
  const actionError = ref<string | null>(null)
  const actionTraceId = ref<string | null>(null)
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

  function captureActionError(errorValue: unknown, fallback: string) {
    const captured = captureApiError(errorValue, fallback)
    actionError.value = captured.code
    actionTraceId.value = captured.traceId
  }

  async function quoteForDraft(draftId: string, branchId: string) {
    error.value = null
    traceId.value = null
    try {
      return await api.get<OrderQuote>(
        withQuery('/client/orders/quote', { draft_id: draftId, branch_id: branchId }),
        authInit(),
      )
    } catch (errorValue) {
      captureError(errorValue, 'order_quote_failed')
      throw errorValue
    }
  }

  // Workshop mirror of quoteForDraft for the walk-in checkout — the branch is
  // fixed there, so no batch variant is needed.
  async function quoteWorkshopBranch(draftId: string, branchId: string) {
    return await api.get<OrderQuote>(
      withQuery('/workshop/orders/quote', { draft_id: draftId, branch_id: branchId }),
      authInit(),
    )
  }

  // Quote a draft against many branches in backend-sized batches — the API
  // returns each branch's own quote or error code (branch_does_not_carry_*,
  // branch_closed, missing_*_rate), so the view can still name each failure
  // (CB-19/CB-20). On a whole-request failure (network/auth) every branch in
  // that failed batch is marked with the generic code + trace.
  async function quoteBranches(draftId: string, branchIds: string[]) {
    if (branchIds.length === 0) {
      return {
        quotes: {} as Record<string, OrderQuote>,
        errors: {},
        firstErrorTraceId: null,
        requestFailed: false,
      }
    }

    const quotes: Record<string, OrderQuote> = {}
    const errors: Record<string, string | null> = {}
    let firstErrorTraceId: string | null = null
    let requestFailed = false

    for (let index = 0; index < branchIds.length; index += QUOTE_BRANCH_BATCH_SIZE) {
      const chunk = branchIds.slice(index, index + QUOTE_BRANCH_BATCH_SIZE)
      try {
        const response = await api.post<{
          quotes: Record<string, OrderQuote>
          errors: Record<string, string | null>
        }>('/client/orders/quote/batch', { draft_id: draftId, branch_ids: chunk }, authInit())
        Object.assign(quotes, response.quotes)
        Object.assign(errors, response.errors)
      } catch (errorValue) {
        const traceId = apiTraceId(errorValue)
        firstErrorTraceId ??= traceId
        if (
          errorValue instanceof ApiError &&
          typeof errorValue.body === 'object' &&
          errorValue.body !== null &&
          'errors' in errorValue.body
        ) {
          const body = errorValue.body as {
            quotes?: Record<string, OrderQuote>
            errors?: Record<string, string | null>
          }
          Object.assign(quotes, body.quotes ?? {})
          Object.assign(errors, body.errors ?? {})
          continue
        }
        const code =
          apiErrorCode(errorValue) ??
          (errorValue instanceof ApiError && errorValue.status === 403 ? 'permission_denied' : null)
        for (const branchId of chunk) errors[branchId] = code
        requestFailed = true
      }
    }
    return { quotes, errors, firstErrorTraceId, requestFailed }
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

  // Workshop walk-in order creation (mirrors createClientOrder): the order
  // lands `confirmed` server-side and joins the workshop list like any other
  // workshop mutation. Errors propagate to the checkout view.
  async function createWorkshopOrder(payload: WorkshopOrderCreatePayload) {
    actionLoading.value = true
    try {
      const order = await api.post<OrderDetail>('/workshop/orders', payload, authInit())
      currentOrder.value = order
      patchWorkshopOrder(order)
      return order
    } finally {
      actionLoading.value = false
    }
  }

  // Paginated with append (CB-38): offset 0 replaces, a higher offset appends the
  // next page. ordersHasMore is inferred from a full page, so the "load more"
  // button hides on the last page.
  async function loadClientOrders(
    filters: { status?: string; search?: string; offset?: number } = {},
  ) {
    const offset = filters.offset ?? 0
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      const page = await api.get<OrderSummary[]>(
        withQuery('/client/orders', {
          status: filters.status,
          search: filters.search,
          limit: ORDERS_PAGE_LIMIT,
          offset,
        }),
        authInit(),
      )
      clientOrders.value = offset === 0 ? page : [...clientOrders.value, ...page]
      ordersHasMore.value = page.length === ORDERS_PAGE_LIMIT
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

  async function loadWorkshopOrders(filters: WorkshopOrderFilters = {}) {
    const limit = filters.limit ?? ORDERS_PAGE_LIMIT
    const offset = filters.offset ?? 0
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      const page = await api.get<OrderSummary[]>(
        withQuery('/workshop/orders', {
          branch_id: filters.branch_id,
          status: filters.status,
          search: filters.search,
          date_from: filters.date_from,
          date_to: filters.date_to,
          assigned_cutter_user_id: filters.assigned_cutter_user_id,
          assigned_edger_user_id: filters.assigned_edger_user_id,
          limit,
          offset,
        }),
        authInit(),
      )
      workshopOrders.value = offset === 0 ? page : [...workshopOrders.value, ...page]
      workshopOrdersHasMore.value = page.length === limit
    } catch (errorValue) {
      captureError(errorValue, 'workshop_orders_load_failed')
    } finally {
      loading.value = false
    }
  }

  async function downloadWorkshopOrdersCsv(
    filters: Omit<WorkshopOrderFilters, 'limit' | 'offset'>,
    filename = 'workshop-orders.csv',
  ) {
    await downloadBlob(
      withQuery('/workshop/orders/export.csv', {
        branch_id: filters.branch_id,
        status: filters.status,
        search: filters.search,
        date_from: filters.date_from,
        date_to: filters.date_to,
        assigned_cutter_user_id: filters.assigned_cutter_user_id,
        assigned_edger_user_id: filters.assigned_edger_user_id,
      }),
      filename,
      authInit(),
    )
  }

  async function loadRecentWorkshopOrders(
    filters: {
      branch_id?: string | null
      limit?: number
    } = {},
  ) {
    const limit = filters.limit ?? 8
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      recentWorkshopOrders.value = await api.get<OrderSummary[]>(
        withQuery('/workshop/orders', {
          branch_id: filters.branch_id,
          status: 'all',
          limit,
          offset: 0,
        }),
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

  // The worker-owned production loop: assignment is metadata, start is the
  // status trigger. Both go through mutate() so a 409 refetches the fresh row.
  async function startCutting(id: string, version: number) {
    return await mutate(`/workshop/orders/${id}/start-cutting`, { version })
  }

  async function startBanding(id: string, version: number) {
    return await mutate(`/workshop/orders/${id}/start-banding`, { version })
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

  // Revision — editing a placed order (orders.md "Revising a placed order").
  // Begin creates or resumes the order's revision draft; the editor takes over
  // from there. Apply rebinds the order atomically like any workshop mutation.
  async function beginRevision(id: string) {
    actionLoading.value = true
    actionError.value = null
    actionTraceId.value = null
    try {
      return await api.post<CuttingDraft>(`/workshop/orders/${id}/revision`, {}, authInit())
    } catch (errorValue) {
      captureActionError(errorValue, 'order_revision_failed')
      throw errorValue
    } finally {
      actionLoading.value = false
    }
  }

  async function applyRevision(id: string, payload: { version: number; reason?: string | null }) {
    return await mutate(`/workshop/orders/${id}/revision/apply`, payload)
  }

  // Plain fetch without touching currentOrder/loading — for surfaces that show
  // order context around another primary object (the revision editor/review).
  async function fetchWorkshopOrder(id: string) {
    return await api.get<OrderDetail>(`/workshop/orders/${id}`, authInit())
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
    actionError.value = null
    actionTraceId.value = null
    const scope = path.startsWith('/client/')
      ? 'client'
      : path.startsWith('/workshop/')
        ? 'workshop'
        : 'unknown'
    try {
      const order =
        method === 'post'
          ? await api.post<OrderDetail>(path, payload, authInit())
          : await api.patch<OrderDetail>(path, payload, authInit())
      currentOrder.value = order
      if (scope === 'client') patchClientOrder(order)
      else if (scope === 'workshop') patchWorkshopOrder(order)
      return order
    } catch (errorValue) {
      // On an optimistic-concurrency conflict the cached version is stale; refetch
      // the order so the next attempt carries the server's current version. The
      // refetch owns `error`/`traceId`; the conflict itself goes to actionError so
      // the page stays on the (now fresh) order instead of its load-error state.
      if (apiErrorCode(errorValue) === 'order_version_conflict') {
        const match = path.match(/\/(client|workshop)\/orders\/([^/]+)\//)
        const orderId = match?.[2]
        if (orderId) {
          if (match?.[1] === 'client') await loadClientOrder(orderId)
          else await loadWorkshopOrder(orderId)
          // Sync the refreshed order into the summary list too — a retry from a
          // list-driven surface (queues) must carry the server's current version,
          // not the stale row it captured before the conflict.
          const fresh = currentOrder.value
          if (fresh && fresh.id === orderId) {
            if (match?.[1] === 'client') patchClientOrder(fresh)
            else patchWorkshopOrder(fresh)
          }
        }
      }
      captureActionError(errorValue, 'order_action_failed')
      throw errorValue
    } finally {
      actionLoading.value = false
    }
  }

  function replaceOrPrependOrder(list: OrderSummary[], order: OrderSummary) {
    const index = list.findIndex((item) => item.id === order.id)
    if (index === -1) return [order, ...list]
    const next = [...list]
    next[index] = order
    return next
  }

  function patchClientOrder(order: OrderSummary) {
    clientOrders.value = replaceOrPrependOrder(clientOrders.value, order)
  }

  function patchWorkshopOrder(order: OrderSummary) {
    workshopOrders.value = replaceOrPrependOrder(workshopOrders.value, order)
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

  function reset() {
    clientOrders.value = []
    ordersHasMore.value = false
    workshopOrders.value = []
    recentWorkshopOrders.value = []
    workshopOrdersHasMore.value = false
    currentOrder.value = null
    workerOptions.value = []
    loading.value = false
    actionLoading.value = false
    error.value = null
    traceId.value = null
    actionError.value = null
    actionTraceId.value = null
    downloadingId.value = null
    downloadError.value = null
    downloadTraceId.value = null
  }

  return {
    clientOrders,
    workshopOrders,
    recentWorkshopOrders,
    workshopOrdersHasMore,
    currentOrder,
    workerOptions,
    loading,
    actionLoading,
    error,
    traceId,
    actionError,
    actionTraceId,
    downloadingId,
    downloadError,
    downloadTraceId,
    quoteForDraft,
    quoteWorkshopBranch,
    quoteBranches,
    createClientOrder,
    createWorkshopOrder,
    ordersHasMore,
    loadClientOrders,
    loadClientOrder,
    cancelClientOrder,
    loadWorkshopOrders,
    downloadWorkshopOrdersCsv,
    loadRecentWorkshopOrders,
    loadWorkshopOrder,
    loadWorkers,
    approve,
    assign,
    startCutting,
    startBanding,
    cuttingDone,
    bandingDone,
    markCollected,
    revert,
    cancelWorkshopOrder,
    beginRevision,
    applyRevision,
    fetchWorkshopOrder,
    discount,
    updateNote,
    downloadClientPdf,
    downloadWorkshopPdf,
    reset,
  }
})
