import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, captureApiError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import type { CuttingResult, MaterialSource } from '@/shared/stores/cutting'
import type { OrderStatus } from '@/shared/stores/orders'

// The shop-floor terminal reads. Server-trimmed payloads: no prices, no client
// phone — mirror of the backend Production* schemas, kept separate from the
// office OrderSummary on purpose.

export type ProductionStation = 'cutting' | 'banding'

export interface ProductionWorkerRef {
  id: string
  full_name: string
}

export interface ProductionEdgeSide {
  material_label: string
  thickness_mm: string | null
  color: string | null
  source: MaterialSource
}

export interface ProductionJobItem {
  id: string
  part_ref: string
  length_mm: number
  width_mm: number
  quantity: number
  material_label: string
  edge_top: ProductionEdgeSide | null
  edge_bottom: ProductionEdgeSide | null
  edge_left: ProductionEdgeSide | null
  edge_right: ProductionEdgeSide | null
}

export interface ProductionEdgeDemand {
  material_id: string
  material_label: string
  thickness_mm: string | null
  color: string | null
  consumed_mm: number
}

export interface ProductionJobCard {
  id: string
  order_number: string
  status: OrderStatus
  version: number
  client_first_name: string
  branch_id: string
  branch_name: string
  item_count: number
  has_banding: boolean
  planned_panels: number
  planned_edge_lines: ProductionEdgeDemand[]
  material_labels: string[]
  assigned_cutter: ProductionWorkerRef | null
  assigned_edger: ProductionWorkerRef | null
  cutter_assigned_at: string | null
  edger_assigned_at: string | null
  cutting_started_at: string | null
  banding_started_at: string | null
  cut_completed_at: string | null
  edge_completed_at: string | null
  created_at: string
}

export interface ProductionQueue {
  station: ProductionStation
  jobs: ProductionJobCard[]
  completed_today: ProductionJobCard[]
}

export interface ProductionJobDetail extends ProductionJobCard {
  items: ProductionJobItem[]
  cutting_result: CuttingResult | null
}

export const useProductionStore = defineStore('production', () => {
  const queues = ref<Partial<Record<ProductionStation, ProductionQueue>>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const job = ref<ProductionJobDetail | null>(null)
  const jobLoading = ref(false)
  const jobError = ref<string | null>(null)
  const jobTraceId = ref<string | null>(null)

  // One fetch per station; the workspace shows both tab counts, so it calls
  // this for both stations and reads `queues` reactively.
  async function loadQueues(stations: ProductionStation[], branchId?: string | null) {
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      const pages = await Promise.all(
        stations.map((station) =>
          api.get<ProductionQueue>(
            withQuery('/workshop/production/queue', { station, branch_id: branchId }),
            authInit(),
          ),
        ),
      )
      const next = { ...queues.value }
      for (const page of pages) next[page.station] = page
      queues.value = next
    } catch (errorValue) {
      const captured = captureApiError(errorValue, 'production_queue_load_failed')
      error.value = captured.code
      traceId.value = captured.traceId
    } finally {
      loading.value = false
    }
  }

  async function loadJob(orderId: string) {
    jobLoading.value = true
    jobError.value = null
    jobTraceId.value = null
    try {
      job.value = await api.get<ProductionJobDetail>(
        `/workshop/production/jobs/${orderId}`,
        authInit(),
      )
    } catch (errorValue) {
      job.value = null
      const captured = captureApiError(errorValue, 'production_job_load_failed')
      jobError.value = captured.code
      jobTraceId.value = captured.traceId
    } finally {
      jobLoading.value = false
    }
  }

  function reset() {
    queues.value = {}
    loading.value = false
    error.value = null
    traceId.value = null
    job.value = null
    jobLoading.value = false
    jobError.value = null
    jobTraceId.value = null
  }

  return {
    queues,
    loading,
    error,
    traceId,
    job,
    jobLoading,
    jobError,
    jobTraceId,
    loadQueues,
    loadJob,
    reset,
  }
})
