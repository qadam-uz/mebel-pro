import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import NotificationsMenu from '@/shared/components/NotificationsMenu.vue'
import { useAuthStore } from '@/shared/stores/auth'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

/**
 * CB-131: the bell used to render — and refill — the same `items` array the
 * notifications page paginates, so opening the dropdown over an open page cut
 * that page's feed down to the bell's ten rows. The assertions below are on the
 * page's rows, not on which action the bell called: the wiring may change, the
 * outcome may not.
 */
vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { ...actual.api, get: vi.fn(), post: vi.fn() } }
})

const blank = { template: '<div />' }
const routes = [
  { path: '/c', name: 'client-home', component: blank },
  { path: '/c/orders/:id', name: 'client-order', component: blank },
  { path: '/c/notifications', name: 'client-notifications', component: blank },
]

function notification(id: string, readAt: string | null = null): NotificationItem {
  return {
    id,
    recipient_type: 'client',
    recipient_id: 'client-1',
    event_code: 'order_ready',
    entity_type: 'order',
    entity_id: 'order-1',
    payload: { order_number: 123456 },
    created_at: '2026-09-01T00:00:00Z',
    read_at: readAt,
  }
}

const rows = (count: number, prefix: string) =>
  Array.from({ length: count }, (_, index) => notification(`${prefix}-${index + 1}`))

/** The bell's ten rows are the first ten the page holds — as the API returns them. */
const BELL_ROWS = rows(10, 'n')
const PAGE_ROWS = rows(14, 'n')

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(api.get).mockReset()
  vi.mocked(api.post).mockReset()
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.startsWith('/notifications/unread-count')) return { unread: 14 }
    return BELL_ROWS
  })
})

/** The notification rows themselves — not the "mark all" / "see all" menu items. */
function bellRows(wrapper: VueWrapper) {
  return wrapper
    .findAll('button[role="menuitem"]')
    .filter((row) => row.find('.client-notif-icon').exists())
}

async function mountBell() {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/c/notifications')
  await router.isReady()

  useAuthStore().accessToken = 'access-token'
  const notifications = useNotificationsStore()
  // The page is open with its full feed already loaded.
  notifications.items = [...PAGE_ROWS]
  notifications.hasMore = true

  const wrapper = mount(NotificationsMenu, {
    global: { plugins: [router], provide: { [roleConfigKey as symbol]: clientConfig } },
  })
  await flushPromises()
  return { wrapper, notifications }
}

describe('NotificationsMenu — the bell over an open notifications page (CB-131)', () => {
  it('keeps the page feed intact when the dropdown loads', async () => {
    const { wrapper, notifications } = await mountBell()

    await wrapper.get('button[aria-haspopup="menu"]').trigger('click')
    await flushPromises()

    expect(notifications.items).toHaveLength(14)
    expect(notifications.hasMore).toBe(true)
    expect(bellRows(wrapper)).toHaveLength(10)
  })

  it('marks the page row read when the same row is opened from the bell', async () => {
    const { wrapper, notifications } = await mountBell()
    vi.mocked(api.post).mockResolvedValueOnce(notification('n-1', '2026-09-06T10:00:00Z'))

    await wrapper.get('button[aria-haspopup="menu"]').trigger('click')
    await flushPromises()
    await bellRows(wrapper)[0]!.trigger('click')
    await flushPromises()

    expect(notifications.items.find((item) => item.id === 'n-1')?.read_at).toBe(
      '2026-09-06T10:00:00Z',
    )
    expect(notifications.items).toHaveLength(14)
    expect(notifications.unread).toBe(13)
  })
})
