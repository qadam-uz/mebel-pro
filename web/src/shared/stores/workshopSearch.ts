import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import type { OrderSummary } from '@/shared/stores/orders'
import type { BranchMaterial, StockItem, WorkshopUser } from '@/shared/stores/workshop'

export interface WorkshopSearchInput {
  query: string
  branchId?: string | null
  includeOrders?: boolean
  includeUsers?: boolean
  includeCatalog?: boolean
  includeInventory?: boolean
}

export interface WorkshopSearchResults {
  orders: OrderSummary[]
  users: WorkshopUser[]
  materials: BranchMaterial[]
  stock: StockItem[]
}

const RESULT_LIMIT = 5

function emptyResults(): WorkshopSearchResults {
  return { orders: [], users: [], materials: [], stock: [] }
}

function normalizedBranchId(value: string | null | undefined) {
  if (!value || value === 'all' || value === 'none') return null
  return value
}

export const useWorkshopSearchStore = defineStore('workshopSearch', () => {
  const results = ref<WorkshopSearchResults>(emptyResults())
  const loading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  let requestId = 0
  // Each round owns a controller so the next keystroke can cancel the last. The
  // sequence guard below already discarded stale *results*; this stops the stale
  // *requests* from occupying a link the fresh ones need — four per round, over
  // the slow mobile connections this app is used on.
  let inFlight: AbortController | null = null

  async function search(input: WorkshopSearchInput) {
    const query = input.query.trim()
    const branchId = normalizedBranchId(input.branchId)
    requestId += 1
    const currentRequest = requestId
    inFlight?.abort()
    const controller = new AbortController()
    inFlight = controller

    if (query.length < 2) {
      results.value = emptyResults()
      loading.value = false
      error.value = null
      traceId.value = null
      return
    }

    loading.value = true
    error.value = null
    traceId.value = null
    const next = emptyResults()
    const jobs: Array<Promise<void>> = []

    if (input.includeOrders !== false) {
      jobs.push(
        api
          .get<OrderSummary[]>(
            withQuery('/workshop/orders', {
              branch_id: branchId,
              status: 'all',
              search: query,
              limit: RESULT_LIMIT,
              offset: 0,
            }),
            { ...authInit(), signal: controller.signal },
          )
          .then((rows) => {
            next.orders = rows.slice(0, RESULT_LIMIT)
          }),
      )
    }

    if (input.includeUsers) {
      jobs.push(
        api
          .get<WorkshopUser[]>(
            // `search` server-side, not the whole roster filtered here: every
            // row costs an extra permission-grant query on the backend, so
            // fetching all of them to show at most five was N+1 for nothing.
            withQuery('/workshop/users', { search: query }),
            { ...authInit(), signal: controller.signal },
          )
          .then((rows) => {
            next.users = rows.slice(0, RESULT_LIMIT)
          }),
      )
    }

    if (branchId && input.includeCatalog) {
      jobs.push(
        api
          .get<BranchMaterial[]>(
            withQuery(`/workshop/branches/${branchId}/materials`, {
              search: query,
              status: 'active',
              limit: RESULT_LIMIT,
            }),
            { ...authInit(), signal: controller.signal },
          )
          .then((rows) => {
            next.materials = rows.slice(0, RESULT_LIMIT)
          }),
      )
    }

    if (branchId && input.includeInventory) {
      jobs.push(
        api
          .get<StockItem[]>(
            withQuery(`/workshop/branches/${branchId}/stock`, {
              search: query,
              limit: RESULT_LIMIT,
            }),
            { ...authInit(), signal: controller.signal },
          )
          .then((rows) => {
            next.stock = rows.slice(0, RESULT_LIMIT)
          }),
      )
    }

    const settled = await Promise.allSettled(jobs)
    if (currentRequest !== requestId) return

    const failed = settled.find((job) => job.status === 'rejected')
    results.value = next
    if (failed && failed.status === 'rejected') {
      // A timeout keeps its own code so the panel can say "the connection is
      // slow" instead of the generic failure — the difference between a user
      // retrying and a user thinking the feature is broken.
      const captured = captureApiError(failed.reason, 'workshop_search_failed')
      error.value = captured.code
      traceId.value = captured.traceId
    } else {
      error.value = null
      traceId.value = null
    }
    loading.value = false
  }

  function reset() {
    requestId += 1
    // Closing the panel or clearing the box must also stop the work it started;
    // without this the abandoned round keeps four requests on the wire.
    inFlight?.abort()
    inFlight = null
    results.value = emptyResults()
    loading.value = false
    error.value = null
    traceId.value = null
  }

  return {
    results,
    loading,
    error,
    traceId,
    search,
    reset,
  }
})
