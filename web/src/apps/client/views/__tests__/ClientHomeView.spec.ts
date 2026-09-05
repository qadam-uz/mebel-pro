import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { queueEntryToast, takeEntryToast } from '@/shared/app/clientEntry'
import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import { useToast } from '@/shared/composables/useToast'
import { DEFAULT_LOCALE, setLocale } from '@/shared/i18n'
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

/** Saved drawings and no orders — the other half the dashboard renders off. */
function withSavedDrafts(count: number) {
  const drafts = Array.from({ length: count }, (_, index) => ({
    id: `draft-${index + 1}`,
    name: `Chizma ${String.fromCharCode(65 + index)}`,
    parts_snapshot: [],
    results: [],
    chosen_result_id: null,
    updated_at: '2026-09-01T10:00:00Z',
  }))
  vi.mocked(api.get).mockImplementation(async (path: string) =>
    path.startsWith('/client/cutting-drafts') ? drafts : [],
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

/**
 * Stale-while-revalidate (client audit 2026-09-03). Home is the tab the client
 * returns to constantly; it used to blank to a skeleton on every return, so the
 * skeleton-vs-content decision is the behaviour worth pinning.
 */
describe('ClientHomeView — returning to a home that already has data', () => {
  // The skeleton used to be gated on the ORDERS list alone, so a client with
  // saved drawings and no open order got a full skeleton over drawings the
  // store was already holding — on every single return to this tab.
  it('paints the drawings straight away and revalidates behind them', async () => {
    withSavedDrafts(2)
    await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))
    expect(wrapper!.text()).toContain('Chizma A')

    wrapper?.unmount()
    wrapper = null
    // The second visit's reads never answer, so whatever is on screen now is
    // what the client would look at for the whole of a slow refresh.
    vi.mocked(api.get).mockImplementation(() => new Promise(() => {}))

    const view = await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    expect(view.text()).toContain('Chizma A')
    expect(view.find('.client-skeleton').exists()).toBe(false)
  })

  it('still shows the skeleton on a cold home, with nothing cached', async () => {
    vi.mocked(api.get).mockImplementation(() => new Promise(() => {}))

    const view = await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    expect(view.find('.client-skeleton').exists()).toBe(true)
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

/**
 * A drawing's meta line is `N деталь · N лист · когда`, and Russian agrees both
 * nouns with the number in front of them. The line used to call
 * `t('client.unit.part')` with no count, so vue-i18n never reached the plural
 * rule and a drawing of two parts read «2 деталь». One drawing per Russian
 * class: 1 → one, 2 → few, 5 → many.
 */
describe('ClientHomeView — the drawing meta line agrees with its numbers', () => {
  /** Three drawings sized 1, 2 and 5 — one per Russian plural class — each with
   *  as many sheets as parts, so one line exercises both units. */
  function withPluralDrafts() {
    const drafts = [1, 2, 5].map((size, index) => ({
      id: `draft-${size}`,
      name: `Chizma ${size}`,
      parts_snapshot: [{ quantity: size }],
      results: [{ id: `result-${size}`, panels_used_by_material: { 'panel-a': size } }],
      chosen_result_id: `result-${size}`,
      updated_at: `2026-09-0${index + 1}T10:00:00Z`,
    }))
    vi.mocked(api.get).mockImplementation(async (path: string) =>
      path.startsWith('/client/cutting-drafts') ? drafts : [],
    )
  }

  afterEach(async () => {
    await setLocale(DEFAULT_LOCALE)
  })

  it('inflects both деталь and лист in Russian', async () => {
    withPluralDrafts()
    await setLocale('ru')

    const view = await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    const text = view.text()
    expect(text).toContain('1 деталь · 1 лист')
    expect(text).toContain('2 детали · 2 листа')
    expect(text).toContain('5 деталей · 5 листов')
    // The first form is what an un-counted call renders for every number.
    expect(text).not.toContain('2 деталь')
    expect(text).not.toContain('5 деталь')
  })

  it('leaves Uzbek on its single form at every count', async () => {
    withPluralDrafts()
    await setLocale('uz')

    const view = await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    const text = view.text()
    expect(text).toContain('1 detal · 1 list')
    expect(text).toContain('2 detal · 2 list')
    expect(text).toContain('5 detal · 5 list')
  })

  // uz-Cyrl is transliterated from uz, so it carries the same one form.
  it('gives uz-Cyrl the same single transliterated form', async () => {
    withPluralDrafts()
    await setLocale('uz-Cyrl')

    const view = await mountHome(clientMe({ pinned_workshop_name: 'Mebel Master' }))

    const text = view.text()
    expect(text).toContain('1 детал · 1 лист')
    expect(text).toContain('2 детал · 2 лист')
    expect(text).toContain('5 детал · 5 лист')
  })
})
