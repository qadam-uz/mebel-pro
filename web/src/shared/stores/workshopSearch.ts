import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiTraceId, withQuery } from '@/shared/api/client'
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

function userMatches(user: WorkshopUser, query: string) {
  const value = query.toLowerCase()
  return (
    user.full_name.toLowerCase().includes(value) ||
    user.login.toLowerCase().includes(value) ||
    user.phone.toLowerCase().includes(value)
  )
}

export const useWorkshopSearchStore = defineStore('workshopSearch', () => {
  const results = ref<WorkshopSearchResults>(emptyResults())
  const loading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  let requestId = 0

  async function search(input: WorkshopSearchInput) {
    const query = input.query.trim()
    const branchId = normalizedBranchId(input.branchId)
    requestId += 1
    const currentRequest = requestId

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
            authInit(),
          )
          .then((rows) => {
            next.orders = rows.slice(0, RESULT_LIMIT)
          }),
      )
    }

    if (input.includeUsers) {
      jobs.push(
        api.get<WorkshopUser[]>('/workshop/users', authInit()).then((rows) => {
          next.users = rows.filter((user) => userMatches(user, query)).slice(0, RESULT_LIMIT)
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
            }),
            authInit(),
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
            }),
            authInit(),
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
    error.value = failed ? 'workshop_search_failed' : null
    traceId.value = failed && failed.status === 'rejected' ? apiTraceId(failed.reason) : null
    loading.value = false
  }

  function reset() {
    requestId += 1
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
