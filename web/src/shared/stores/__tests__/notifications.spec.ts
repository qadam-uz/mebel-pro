import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/shared/api/client'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

vi.mock('@/shared/api/client', () => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      readonly body: unknown,
    ) {
      super(`API ${status}`)
    }
  }
  return {
    ApiError,
    apiTraceId: (error: unknown) => {
      if (error instanceof ApiError && typeof error.body === 'object' && error.body) {
        const traceId = (error.body as { trace_id?: unknown }).trace_id
        return typeof traceId === 'string' ? traceId : null
      }
      return null
    },
    api: { get: vi.fn(), post: vi.fn() },
  }
})

function item(id: string, readAt: string | null): NotificationItem {
  return {
    id,
    recipient_type: 'client',
    recipient_id: 'c1',
    event_code: 'order_ready',
    entity_type: 'order',
    entity_id: 'o1',
    payload: {},
    created_at: '2026-06-01T00:00:00Z',
    read_at: readAt,
  }
}

describe('notifications store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
  })

  it('decrements unread only for a previously-unread item (idempotent)', async () => {
    const store = useNotificationsStore()
    store.items = [item('a', null), item('b', '2026-06-01T01:00:00Z')]
    store.unread = 1

    // marking the already-read 'b' must not change the badge
    vi.mocked(api.post).mockResolvedValueOnce(item('b', '2026-06-01T02:00:00Z'))
    await store.markRead('b')
    expect(store.unread).toBe(1)

    // marking the unread 'a' decrements exactly once
    vi.mocked(api.post).mockResolvedValueOnce(item('a', '2026-06-01T03:00:00Z'))
    await store.markRead('a')
    expect(store.unread).toBe(0)

    // re-marking 'a' (now read) never goes below zero
    vi.mocked(api.post).mockResolvedValueOnce(item('a', '2026-06-01T04:00:00Z'))
    await store.markRead('a')
    expect(store.unread).toBe(0)
  })

  it('captures a markRead failure without throwing or changing the badge', async () => {
    const store = useNotificationsStore()
    store.items = [item('a', null)]
    store.unread = 1
    vi.mocked(api.post).mockRejectedValueOnce(new ApiError(500, { trace_id: 'tr-1' }))

    await expect(store.markRead('a')).resolves.toBeUndefined()
    expect(store.unread).toBe(1)
    expect(store.actionError).toBe('notifications_read_failed')
    expect(store.traceId).toBe('tr-1')
  })

  it('markAllRead zeroes unread and stamps only previously-unread items', async () => {
    const store = useNotificationsStore()
    store.items = [item('a', null), item('b', '2026-06-01T01:00:00Z')]
    store.unread = 1
    vi.mocked(api.post).mockResolvedValueOnce(undefined)

    await store.markAllRead()
    expect(store.unread).toBe(0)
    expect(store.items[0].read_at).not.toBeNull()
    expect(store.items[1].read_at).toBe('2026-06-01T01:00:00Z')
  })
})
