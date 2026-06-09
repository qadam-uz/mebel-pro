import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '@/shared/api/client'
import { useAuthStore } from '@/shared/stores/auth'

export interface NotificationItem {
  id: string
  recipient_type: 'platform_user' | 'workshop_user' | 'client'
  recipient_id: string
  event_code: string
  entity_type: string | null
  entity_id: string | null
  payload: Record<string, unknown>
  created_at: string
  read_at: string | null
}

export const useNotificationsStore = defineStore('notifications', () => {
  const unread = ref(0)
  const items = ref<NotificationItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const auth = useAuthStore()

  function authInit() {
    return { accessToken: auth.accessToken }
  }

  async function loadUnreadCount() {
    if (!auth.accessToken) return
    try {
      unread.value = (
        await api.get<{ unread: number }>('/notifications/unread-count', authInit())
      ).unread
      error.value = null
    } catch {
      unread.value = 0
      error.value = 'notifications_count_failed'
    }
  }

  async function loadList(limit = 10) {
    if (!auth.accessToken) return
    loading.value = true
    error.value = null
    try {
      items.value = await api.get<NotificationItem[]>(`/notifications?limit=${limit}`, authInit())
    } catch {
      error.value = 'notifications_load_failed'
    } finally {
      loading.value = false
    }
  }

  async function markRead(id: string) {
    const updated = await api.post<NotificationItem>(
      `/notifications/${id}/read`,
      undefined,
      authInit(),
    )
    items.value = items.value.map((item) => (item.id === id ? updated : item))
    unread.value = Math.max(0, unread.value - 1)
    return updated
  }

  async function markAllRead() {
    await api.post('/notifications/read-all', undefined, authInit())
    unread.value = 0
    items.value = items.value.map((item) => ({
      ...item,
      read_at: item.read_at ?? new Date().toISOString(),
    }))
  }

  return {
    unread,
    items,
    loading,
    error,
    loadUnreadCount,
    loadList,
    markRead,
    markAllRead,
  }
})
