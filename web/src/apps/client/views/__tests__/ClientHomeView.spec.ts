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

describe('ClientHomeView — the pinned header subtitle', () => {
  it('names workshop · branch and links to Ustaxonalarim', async () => {
    const view = await mountHome(
      clientMe({ pinned_workshop_name: 'Mebel Master', pinned_branch_name: 'Chilonzor' }),
    )

    const link = view.find('a[href="/c/branches"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toBe('Mebel Master · Chilonzor')
  })

  it('stacks the pinned line above the counts line — it joins, never replaces', async () => {
    // Owner decision 2026-09-02: where the app is scoped and what is waiting are
    // two different questions, and the counts line was the one the client came for.
    withActiveOrders(2)

    const view = await mountHome(
      clientMe({ pinned_workshop_name: 'Mebel Master', pinned_branch_name: 'Chilonzor' }),
    )

    expect(view.find('a[href="/c/branches"]').text()).toBe('Mebel Master · Chilonzor')
    expect(view.text()).toContain('2 ta faol buyurtmangiz bor.')
  })

  it('leaves the counts line alone for an un-pinned client', async () => {
    withActiveOrders(2)

    const view = await mountHome(clientMe())

    expect(view.find('a[href="/c/branches"]').exists()).toBe(false)
    expect(view.text()).toContain('2 ta faol buyurtmangiz bor.')
  })

  it('falls back to the workshop alone when the pinned branch has no name', async () => {
    const view = await mountHome(
      clientMe({ pinned_workshop_name: 'Mebel Master', pinned_branch_name: null }),
    )

    expect(view.find('a[href="/c/branches"]').text()).toBe('Mebel Master')
  })

  it('leaves an un-pinned client’s header exactly as it was', async () => {
    const view = await mountHome(clientMe())

    expect(view.find('a[href="/c/branches"]').exists()).toBe(false)
    expect(view.text()).toContain('Salom, Dilshod')
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
