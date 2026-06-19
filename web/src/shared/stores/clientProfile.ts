import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import type { ClientBranchOption } from '@/shared/stores/cutting'

export interface ClientProfile {
  id: string
  phone: string
  name: string
  preferred_branch_id: string | null
  status: 'active' | 'blocked'
}

/**
 * Client profile fetch/patch (CB-95) — moved out of the view into a store slice so
 * the raw `/client/profile` calls live behind one seam. ClientBranchOption is
 * imported from the cutting store (one shared definition, CB-95).
 */
export const useClientProfileStore = defineStore('clientProfile', () => {
  const profile = ref<ClientProfile | null>(null)
  const branchOptions = ref<ClientBranchOption[]>([])

  async function load() {
    profile.value = await api.get<ClientProfile>('/client/profile', authInit())
    branchOptions.value = await api.get<ClientBranchOption[]>('/client/branch-options', authInit())
    return profile.value
  }

  async function patch(payload: Partial<ClientProfile>) {
    return await api.patch<ClientProfile>('/client/profile', payload, authInit())
  }

  return { profile, branchOptions, load, patch }
})
