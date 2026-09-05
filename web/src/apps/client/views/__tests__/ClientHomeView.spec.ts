import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { queueEntryToast, takeEntryToast } from '@/shared/app/clientEntry'
import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import { useToast } from '@/shared/composables/useToast'
import ClientHomeView from '@/apps/client/views/ClientHomeView.vue'
import { useAuthStore, type MeResponse } from '@/shared/stores/auth'
import type { OrderSummary } from '@/shared/stores/orders'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { get: vi.fn(), post: vi.fn() } }
})

const { api } = await import('@/shared/api/client')

const routes = [
  { path: '/c', name: 'client-home', component: ClientHomeView },
  { path: '/c/branches', name: 'client-branches', component: { template: '<div />' } },
  { path: '/c/cutting/new', name: 'client-cutting-new', component: { template: '<div />' } },
  { path: '/c/cutting/drafts', name: 'client-drafts', component: { template: '<div />' } },
  { path: '/c/orders', name: 'client-orders', component: { template: '<div />' } },
  { path: '/c/orders/:id', name: 'client-order', component: { template: '<div />' } },
]

function clientMe(overrides: Partial<MeResponse> = {}): MeResponse {
  return {
    principal_type: 'client',
    principal_id: 'client-1',
    session_id: 'session-1',
    password_reset_required: false,
    workshop_id: null,
    workshop_name: null,
    is_owner: false,
    grants: [],
    login: null,
    full_name: null,
    phone: '+998901112233',
    name: 'Dilshod',
    preferred_branch_id: null,
    pinned_workshop_name: null,
    pinned_branch_name: null,
    status: 'active',
    ...overrides,
  }
}

/**
 * Just enough of an order for the header: the counts line only reads statuses,
 * and the rest of the dashboard renders off the same two lists.
 */
function activeOrder(id: string): OrderSummary {
  return {
    id,
    order_number: `ORD-${id}`,
    branch_name: 'Chilonzor',
    status: 'new',
    total_tiyin: 100_000,
    created_at: '2026-09-01T10:00:00Z',
  } as unknown as OrderSummary
}

/** The dashboard with content, so the counts subtitle is on screen at all. */
function withActiveOrders(count: number) {
  const orders = Array.from({ length: count }, (_, index) => activeOrder(`order-${index + 1}`))
  vi.mocked(api.get).mockImplementation(async (path: string) =>
    path.startsWith('/client/orders') ? orders : [],
  )
}

let router: Router
let wrapper: VueWrapper | null = null

async function mountHome(me: MeResponse) {
  const auth = useAuthStore()
  auth.accessToken = 'access-1'
  auth.me = me
  auth.status = 'authenticated'

  router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/c')
  await router.isReady()
  wrapper = mount(ClientHomeView, {
    global: {
      plugins: [router],
      provide: { [roleConfigKey as symbol]: clientConfig },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  window.localStorage.clear()
  useToast().toasts.value = []
  vi.mocked(api.get).mockReset()
  vi.mocked(api.get).mockResolvedValue([])
  vi.mocked(api.post).mockReset()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('ClientHomeView — the Ustaxonangiz card (§3)', () => {
  // Decision 16: with the branch list not yet in hand the card still has both
  // names off `/auth/me`, so it renders «Workshop · Branch» rather than waiting.
  it('titles the card by the naming rule and links to the workshop', async () => {
    const view = await mountHome(
      clientMe({ pinned_workshop_name: 'Mebel Master', pinned_branch_name: 'Chilonzor' }),
    )

    const card = view.find('a[href="/c/branches"]')
    expect(card.exists()).toBe(true)
    expect(card.text()).toContain('Ustaxonangiz')
    expect(card.text()).toContain('Mebel Master · Chilonzor')
  })

  it('falls back to the workshop alone when the pinned branch has no name', async () => {
    const view = await mountHome(
      clientMe({ pinned_workshop_name: 'Mebel Master', pinned_branch_name: null }),
    )

    expect(view.find('a[href="/c/branches"]').text()).toContain('Mebel Master')
  })

  // §3 item 2: the page's one primary action sits UNDER the card, outside it —
  // a card that is itself a link must not hold a second tap target.
  it('offers «Yangi chizma» outside the card when the client is pinned', async () => {
    const view = await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    const action = view.findAll('button').find((node) => node.text().includes('Yangi chizma'))
    expect(action).toBeDefined()
    expect(view.find('a[href="/c/branches"]').element.contains(action!.element)).toBe(false)
  })

  // Decision 15: un-pinned means no card and no drawing action at all — a
  // drawing needs a branch, so the one action opens Ustaxonalarim.
  it('replaces the card with «Ustaxona tanlang» and no drawing action when un-pinned', async () => {
    withActiveOrders(2)

    const view = await mountHome(clientMe())

    expect(view.text()).toContain('Ustaxonangizni tanlang')
    expect(view.text()).toContain('Ustaxona tanlang')
    expect(view.text()).not.toContain('Yangi chizma')
    expect(view.find('a[href="/c/branches"]').exists()).toBe(true)
  })

  // §3: the count strip and the greeting's counts line are gone; the greeting
  // is the client's name and nothing else.
  it('greets by name alone, with no counts line and no count strip', async () => {
    withActiveOrders(2)

    const view = await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    expect(view.text()).toContain('Salom, Dilshod')
    expect(view.text()).not.toContain('2 ta faol buyurtmangiz bor.')
    expect(view.text()).not.toContain('Saqlangan chizma')
  })

  // §3 item 3: at most four rows, and no progress bar or "Keyingi" line on any
  // of them — the whole row is the link to the order.
  it('caps the active list at four rows and drops the progress bars', async () => {
    withActiveOrders(6)

    const view = await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    expect(view.findAll('a[href^="/c/orders/order-"]')).toHaveLength(4)
    expect(view.text()).not.toContain('Keyingi:')
    expect(view.text()).not.toContain('Joriy:')
  })
})

describe('ClientHomeView — the connected toast', () => {
  it('fires once after an entry is applied, naming the workshop', async () => {
    queueEntryToast('Mebel Master')

    await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    const toast = useToast()
    expect(toast.toasts.value).toHaveLength(1)
    expect(toast.toasts.value[0].message).toBe('Siz Mebel Master ustaxonasiga ulandingiz')
    // Consumed: nothing is left for the next home load.
    expect(takeEntryToast()).toBeNull()
  })

  it('does not fire on a plain home load', async () => {
    await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    expect(useToast().toasts.value).toHaveLength(0)
  })

  it('does not repeat on a remount — it is one-time, not per render', async () => {
    queueEntryToast('Mebel Master')
    await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))
    expect(useToast().toasts.value).toHaveLength(1)

    wrapper?.unmount()
    wrapper = null
    await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    expect(useToast().toasts.value).toHaveLength(1)
  })
})
