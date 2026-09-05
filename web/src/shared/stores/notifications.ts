import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiTraceId, isAbortError } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import { useAuthStore } from '@/shared/stores/auth'

// The known, presenter-relevant keys of a notification payload (CB-101). The
// index signature keeps it assignable from the raw backend JSON while giving the
// shared presenter typed access to the strings it actually reads.
export interface NotificationPayload {
  summary?: unknown
  title?: unknown
  body?: unknown
  detail?: unknown
  message?: unknown
  order_number?: unknown
  [key: string]: unknown
}

export interface NotificationItem {
  id: string
  recipient_type: 'platform_user' | 'workshop_user' | 'client'
  recipient_id: string
  event_code: string
  entity_type: string | null
  entity_id: string | null
  payload: NotificationPayload
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
  const hasMore = ref(false)
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

  // Paginated with append (CB-41): offset 0 replaces, a higher offset appends.
  // hasMore is inferred from a full page so the "load more" button hides at the end.
  // unreadOnly filters server-side so pagination stays accurate under the filter.
  //
  // Stale-while-revalidate (client audit 2026-09-03): the rows in hand are NOT
  // cleared while the next page is in flight, so re-opening the page (or
  // flipping its filter) keeps the feed on screen instead of collapsing to a
  // skeleton and back. The list owns one AbortController — a newer call aborts
  // the older, and the loser's rejection is dropped rather than painted as an
  // error, because an aborted read is this store cancelling itself.
  let listRequest: AbortController | null = null

  async function loadList(limit = 10, offset = 0, unreadOnly = false) {
    if (!auth.accessToken) return
    listRequest?.abort()
    const controller = new AbortController()
    listRequest = controller
    loading.value = true
    error.value = null
    traceId.value = null
    try {
      const page = await api.get<NotificationItem[]>(
        `/notifications?limit=${limit}&offset=${offset}&unread_only=${unreadOnly}`,
        { ...authInit(), signal: controller.signal },
      )
      items.value = offset === 0 ? page : [...items.value, ...page]
      hasMore.value = page.length === limit
    } catch (caught) {
      if (isAbortError(caught)) return
      error.value = 'notifications_load_failed'
      traceId.value = apiTraceId(caught)
    } finally {
      // Only the newest call owns the flag; an aborted one must not switch the
      // skeleton off under the request that replaced it.
      if (listRequest === controller) {
        listRequest = null
        loading.value = false
      }
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

  function reset() {
    // Cancel first: reset is a sign-out, and a late page must not repopulate
    // the feed the next session inherits.
    listRequest?.abort()
    listRequest = null
    unread.value = 0
    items.value = []
    loading.value = false
    error.value = null
    traceId.value = null
    actionError.value = null
    hasMore.value = false
  }

  return {
    unread,
    items,
    loading,
    error,
    traceId,
    actionError,
    hasMore,
    loadUnreadCount,
    loadList,
    markRead,
    markAllRead,
    reset,
  }
})
