import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { api } from '@/shared/api/client'
import { useAuthStore } from '@/shared/stores/auth'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

/**
 * The bell and the notifications page read the same store (CB-131). They used to
 * read the same *array* too, so the bell's 10-row load replaced whatever page the
 * full feed held — a 50-row page collapsed to 10 the moment the dropdown opened.
 * The rows are now two slices; the unread count and the read actions stay shared.
 * Only the API client is faked, so the split is asserted through the store's own
 * public surface rather than through a double.
 */
vi.mock('@/shared/app/authInit', () => ({
  authInit: () => ({ accessToken: 'access-token' }),
}))

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { ...actual.api, get: vi.fn(), post: vi.fn() } }
})

function notification(id: string, readAt: string | null = null): NotificationItem {
  return {
    id,
    recipient_type: 'client',
    recipient_id: 'client-1',
    event_code: 'order_ready',
    entity_type: 'order',
    entity_id: 'order-1',
    payload: {},
    created_at: '2026-09-01T00:00:00Z',
    read_at: readAt,
  }
}

const page = (count: number, prefix = 'n') =>
  Array.from({ length: count }, (_, index) => notification(`${prefix}-${index + 1}`))

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(api.get).mockReset()
  vi.mocked(api.post).mockReset()
  useAuthStore().accessToken = 'access-token'
})

describe('notifications — the bell and the page hold separate rows (CB-131)', () => {
  it('leaves the page feed untouched when the bell loads its ten rows', async () => {
    const notifications = useNotificationsStore()
    vi.mocked(api.get).mockResolvedValueOnce(page(14))
    await notifications.loadList(50, 0, false)
    expect(notifications.items).toHaveLength(14)

    vi.mocked(api.get).mockResolvedValueOnce(page(10, 'bell'))
    await notifications.loadRecent()

    expect(notifications.items).toHaveLength(14)
    expect(notifications.recent).toHaveLength(10)
    expect(notifications.hasMore).toBe(false)
  })

  it('asks for ten rows from offset zero, unfiltered', async () => {
    const notifications = useNotificationsStore()
    vi.mocked(api.get).mockResolvedValueOnce(page(10))
    await notifications.loadRecent()

    expect(vi.mocked(api.get).mock.calls[0]?.[0]).toBe(
      '/notifications?limit=10&offset=0&unread_only=false',
    )
  })

  it('keeps the loading and error flags apart, so one surface never blanks the other', async () => {
    const notifications = useNotificationsStore()
    vi.mocked(api.get).mockRejectedValueOnce(new Error('boom'))
    await notifications.loadRecent()

    expect(notifications.recentError).toBe('notifications_load_failed')
    expect(notifications.error).toBeNull()
    expect(notifications.recentLoading).toBe(false)
    expect(notifications.loading).toBe(false)
  })

  it('shows a row marked read from the bell on the page behind it', async () => {
    const notifications = useNotificationsStore()
    vi.mocked(api.get).mockResolvedValueOnce(page(14))
    await notifications.loadList(50, 0, false)
    vi.mocked(api.get).mockResolvedValueOnce(page(10))
    await notifications.loadRecent()
    notifications.unread = 14

    vi.mocked(api.post).mockResolvedValueOnce(notification('n-3', '2026-09-06T10:00:00Z'))
    await notifications.markRead('n-3')

    expect(notifications.items.find((item) => item.id === 'n-3')?.read_at).toBe(
      '2026-09-06T10:00:00Z',
    )
    expect(notifications.recent.find((item) => item.id === 'n-3')?.read_at).toBe(
      '2026-09-06T10:00:00Z',
    )
    expect(notifications.unread).toBe(13)
  })

  it('decrements the badge for a row only the bell holds', async () => {
    const notifications = useNotificationsStore()
    vi.mocked(api.get).mockResolvedValueOnce(page(10, 'bell'))
    await notifications.loadRecent()
    notifications.unread = 10

    vi.mocked(api.post).mockResolvedValueOnce(notification('bell-2', '2026-09-06T10:00:00Z'))
    await notifications.markRead('bell-2')

    expect(notifications.recent.find((item) => item.id === 'bell-2')?.read_at).not.toBeNull()
    expect(notifications.unread).toBe(9)
  })

  it('marks every row of both slices read at once', async () => {
    const notifications = useNotificationsStore()
    vi.mocked(api.get).mockResolvedValueOnce(page(14))
    await notifications.loadList(50, 0, false)
    vi.mocked(api.get).mockResolvedValueOnce(page(10))
    await notifications.loadRecent()
    notifications.unread = 14

    vi.mocked(api.post).mockResolvedValueOnce(undefined)
    await notifications.markAllRead()

    expect(notifications.items.every((item) => item.read_at !== null)).toBe(true)
    expect(notifications.recent.every((item) => item.read_at !== null)).toBe(true)
    expect(notifications.unread).toBe(0)
  })

  it('clears both slices on sign-out', async () => {
    const notifications = useNotificationsStore()
    vi.mocked(api.get).mockResolvedValueOnce(page(14))
    await notifications.loadList(50, 0, false)
    vi.mocked(api.get).mockResolvedValueOnce(page(10))
    await notifications.loadRecent()

    notifications.reset()

    expect(notifications.items).toEqual([])
    expect(notifications.recent).toEqual([])
    expect(notifications.recentError).toBeNull()
    expect(notifications.recentLoading).toBe(false)
  })
})
