import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'

interface Health {
  status: string
  env: string
}

// Example store — mirrors the backend GET /api/v1/healthz endpoint.
export const useHealthStore = defineStore('health', () => {
  const health = ref<Health | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchHealth() {
    loading.value = true
    error.value = null
    try {
      health.value = await api.get<Health>('/healthz')
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return { health, loading, error, fetchHealth }
})
