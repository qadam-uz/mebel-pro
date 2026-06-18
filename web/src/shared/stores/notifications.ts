import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiTraceId } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
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
  const traceId = ref<string | null>(null)
  const actionError = ref<string | null>(null)
  const auth = useAuthStore()

  async function loadUnreadCount() {
    if (!auth.accessToken) return
    try {
      unread.value = (
        await api.get<{ unread: number }>('/notifications/unread-count', authInit())
      ).unread
      error.value = null
    } catch (caught) {
      unread.value = 0
      error.value = 'notifications_count_failed'
      traceId.value = apiTraceId(caught)
    }
  }

  async function loadList(limit = 10) {
    if (!auth.accessToken) return
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      items.value = await api.get<NotificationItem[]>(`/notifications?limit=${limit}`, authInit())
    } catch (caught) {
      error.value = 'notifications_load_failed'
      traceId.value = apiTraceId(caught)
    } finally {
      loading.value = false
    }
  }

  async function markRead(id: string) {
    // Decrement the badge only for a genuinely-unread item, so a double-tap or a
    // re-read never drives the count below the true value.
    const wasUnread = items.value.find((item) => item.id === id)?.read_at === null
    actionError.value = null
    try {
      const updated = await api.post<NotificationItem>(
        `/notifications/${id}/read`,
        undefined,
        authInit(),
      )
      items.value = items.value.map((item) => (item.id === id ? updated : item))
      if (wasUnread) unread.value = Math.max(0, unread.value - 1)
    } catch (caught) {
      actionError.value = 'notifications_read_failed'
      traceId.value = apiTraceId(caught)
    }
  }

  async function markAllRead() {
    actionError.value = null
    try {
      await api.post('/notifications/read-all', undefined, authInit())
      unread.value = 0
      items.value = items.value.map((item) => ({
        ...item,
        read_at: item.read_at ?? new Date().toISOString(),
      }))
    } catch (caught) {
      actionError.value = 'notifications_read_all_failed'
      traceId.value = apiTraceId(caught)
    }
  }

  return {
    unread,
    items,
    loading,
    error,
    traceId,
    actionError,
    loadUnreadCount,
    loadList,
    markRead,
    markAllRead,
  }
})
