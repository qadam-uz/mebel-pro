import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, captureApiError, isAbortError, withQuery } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

/**
 * The read behind the client's read-only branch catalog (spec §6.2).
 *
 * Deliberately its own store rather than the cutting store's `loadCatalog`:
 * that one caches per draft and per picker mode and owns the editor's
 * `panelOptions` / `edgeOptions`, and browsing a price list must not disturb
 * either. Same endpoint, no shared state.
 */
export const CLIENT_CATALOG_LIMIT = 200

export const useClientCatalogStore = defineStore('clientCatalog', () => {
  const materials = ref<ClientCatalogMaterialOption[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)

  // Typing in the search box fires a request per debounce window; the older
  // one's answer must never overwrite the newer one's (the UX bar's
  // reserve-space rule is about the same jump). A newer call aborts the older.
  let inFlight: AbortController | null = null

  async function loadMaterials(branchId: string, search = '') {
    inFlight?.abort()
    const controller = new AbortController()
    inFlight = controller
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      materials.value = await api.get<ClientCatalogMaterialOption[]>(
        withQuery('/client/catalog/materials', {
          branch_id: branchId,
          search: search || undefined,
          limit: CLIENT_CATALOG_LIMIT,
        }),
        { ...authInit(), signal: controller.signal },
      )
    } catch (errorValue) {
      // An abort is this store cancelling itself, never a failure to show.
      if (isAbortError(errorValue)) return
      const captured = captureApiError(errorValue, 'client_catalog_load_failed')
      error.value = captured.code
      traceId.value = captured.traceId
      materials.value = []
    } finally {
      if (inFlight === controller) {
        inFlight = null
        loading.value = false
      }
    }
  }

  function reset() {
    inFlight?.abort()
    inFlight = null
    materials.value = []
    loading.value = false
    error.value = null
    traceId.value = null
  }

  return { materials, loading, error, traceId, loadMaterials, reset }
})
