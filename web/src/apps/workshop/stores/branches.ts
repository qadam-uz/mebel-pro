// Workshop branches store — loads the branch list once and exposes a
// name lookup (used by the branch picker, order cards, finance, etc.).
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ApiError } from '@/shared/api'
import * as workshopApi from '../api'
import type { BranchSummary } from '../api/types'

export const useBranchesStore = defineStore('workshop:branches', () => {
  const branches = ref<BranchSummary[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  const byId = computed(() => {
    const map = new Map<string, BranchSummary>()
    for (const b of branches.value) map.set(b.id, b)
    return map
  })

  function nameOf(id: string | null | undefined): string {
    if (!id) return '—'
    return byId.value.get(id)?.name ?? id
  }

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) return
    loading.value = true
    try {
      branches.value = await workshopApi.listBranches()
      loaded.value = true
    } catch (e) {
      if (!(e instanceof ApiError)) throw e
    } finally {
      loading.value = false
    }
  }

  return { branches, loaded, loading, byId, nameOf, load }
})
