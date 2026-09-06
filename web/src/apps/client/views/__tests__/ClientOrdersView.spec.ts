import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import ClientOrdersView from '@/apps/client/views/ClientOrdersView.vue'
import { DEFAULT_LOCALE, setLocale } from '@/shared/i18n'
import { useAuthStore } from '@/shared/stores/auth'
import type { OrderSummary } from '@/shared/stores/orders'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { get: vi.fn(), post: vi.fn() } }
})

const { api } = await import('@/shared/api/client')

const routes = [
  { path: '/c', name: 'client-home', component: { template: '<div />' } },
  { path: '/c/orders', name: 'client-orders', component: ClientOrdersView },
  { path: '/c/orders/:id', name: 'client-order', component: { template: '<div />' } },
  { path: '/c/cutting/new', name: 'client-cutting-new', component: { template: '<div />' } },
  { path: '/c/cutting/drafts', name: 'client-drafts', component: { template: '<div />' } },
]

/** Only the card's own fields matter here: the counts line reads `item_count`
 *  and `planned_panels`, and the rest of the card reads names and a status. */
function order(parts: number, panels: number): OrderSummary {
  return {
    id: `order-${parts}`,
    order_number: String(100_000 + parts),
    workshop_name: 'Mebel Master',
    branch_name: 'Yunusobod filiali',
    workshop_branch_count: 3,
    status: 'new',
    item_count: parts,
    planned_panels: panels,
    total_tiyin: 100_000,
    created_at: '2026-09-01T10:00:00Z',
  } as unknown as OrderSummary
}

/** One order per Russian plural class — 1 → one, 2 → few, 5 → many — each with
 *  as many sheets as parts, so a single card line exercises both units. */
function withPluralOrders() {
  const list = [order(1, 1), order(2, 2), order(5, 5)]
  vi.mocked(api.get).mockImplementation(async () => list as never)
}

let router: Router
let wrapper: VueWrapper | null = null

async function mountOrders() {
  const auth = useAuthStore()
  auth.accessToken = 'access-1'
  auth.status = 'authenticated'

  router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/c/orders')
  await router.isReady()
  wrapper = mount(ClientOrdersView, {
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
  vi.mocked(api.get).mockReset()
  vi.mocked(api.get).mockResolvedValue([])
})

afterEach(async () => {
  wrapper?.unmount()
  wrapper = null
  await setLocale(DEFAULT_LOCALE)
})

// Decision 23 — the card's third line follows the naming rule off the payload's
// own branch count, so a client of a single-counter workshop never reads a
// branch name they have no use for.
describe('ClientOrdersView — the card names the workshop (decision 23)', () => {
  function withCount(count: number) {
    vi.mocked(api.get).mockImplementation(
      async () => [{ ...order(2, 1), workshop_branch_count: count }] as never,
    )
  }

  it('shows the workshop alone when it has one visible branch', async () => {
    withCount(1)

    const view = await mountOrders()

    expect(view.text()).toContain('Mebel Master')
    expect(view.text()).not.toContain('Yunusobod filiali')
  })

  it('joins workshop and branch once it has several', async () => {
    withCount(2)

    const view = await mountOrders()

    expect(view.text().replace(/\s+/g, ' ')).toContain('Mebel Master \u00b7 Yunusobod filiali')
  })
})

/**
 * Decision 22 — the card's fourth line ends in the one client date format. The
 * fixture's timestamp carries no zone so it parses as local time: the assertion
 * is about the shape, and a `Z` would make it drift a day either side of UTC.
 */
describe('ClientOrdersView — the card date (decision 22)', () => {
  function datedOrder() {
    vi.mocked(api.get).mockImplementation(
      async () => [{ ...order(2, 1), created_at: '2026-04-26T09:32:00' }] as never,
    )
  }

  it('spells the month out and keeps the 24h clock in Uzbek', async () => {
    datedOrder()
    await setLocale('uz')

    const view = await mountOrders()

    const text = view.text().replace(/\s+/g, ' ')
    expect(text).toContain('26-aprel 2026, 09:32')
    // The numeric shape this replaced must be gone, not merely unused.
    expect(text).not.toContain('26.04.2026')
  })

  // Amended 2026-09-06 evening: on a phone the date is its own line under the
  // counts, never the third «·»-joined item on them — joined, it wrapped
  // mid-date at 375px. jsdom resolves no breakpoints, so what is pinned here
  // is the markup that carries the split: the counts and the date are separate
  // paragraphs, and the «·» between them from `md` up is `md:`-gated.
  it('gives the date its own paragraph, not the counts line', async () => {
    datedOrder()
    await setLocale('uz')

    const view = await mountOrders()

    const paragraphs = view.findAll('p')
    const dateEl = paragraphs.find((el) => el.text().trim() === '26-aprel 2026, 09:32')
    expect(dateEl).toBeDefined()
    expect(dateEl?.classes()).toContain('whitespace-nowrap')

    const counts = paragraphs.find((el) => el.text().includes('detal'))
    expect(counts?.text()).toContain('list')
    expect(counts?.text()).not.toContain('2026')

    const separator = view.findAll('span').find((el) => el.text().trim() === '·')
    expect(separator?.classes()).toContain('hidden')
    expect(separator?.classes()).toContain('md:inline')
  })

  it('uses the Russian genitive month', async () => {
    datedOrder()
    await setLocale('ru')

    const view = await mountOrders()

    expect(view.text().replace(/\s+/g, ' ')).toContain('26 апреля 2026, 09:32')
  })
})

/**
 * An order card's counts line is `N деталь · N лист · дата`, and Russian agrees
 * both nouns with the number in front of them. Both used to be rendered by
 * `$t('client.unit.part')` with no count, so vue-i18n never reached the plural
 * rule and every card read «деталь» however many parts the order had.
 */
describe('ClientOrdersView — the card counts line agrees with its numbers', () => {
  it('inflects both деталь and лист in Russian', async () => {
    withPluralOrders()
    await setLocale('ru')

    const view = await mountOrders()

    // The numbers sit in their own <b>, so the rendered text is `1\n деталь`;
    // collapsing whitespace is what makes the line assertable.
    const text = view.text().replace(/\s+/g, ' ')
    expect(text).toContain('1 деталь · 1 лист')
    expect(text).toContain('2 детали · 2 листа')
    expect(text).toContain('5 деталей · 5 листов')
    // The first form is what an un-counted call renders for every number.
    expect(text).not.toContain('2 деталь')
    expect(text).not.toContain('5 деталь')
  })

  it('leaves Uzbek on its single form at every count', async () => {
    withPluralOrders()
    await setLocale('uz')

    const view = await mountOrders()

    const text = view.text().replace(/\s+/g, ' ')
    expect(text).toContain('1 detal · 1 list')
    expect(text).toContain('2 detal · 2 list')
    expect(text).toContain('5 detal · 5 list')
  })

  // uz-Cyrl is transliterated from uz, so it carries the same one form —
  // Cyrillic script, not Russian grammar.
  it('gives uz-Cyrl the same single transliterated form', async () => {
    withPluralOrders()
    await setLocale('uz-Cyrl')

    const view = await mountOrders()

    const text = view.text().replace(/\s+/g, ' ')
    expect(text).toContain('1 детал · 1 лист')
    expect(text).toContain('2 детал · 2 лист')
    expect(text).toContain('5 детал · 5 лист')
    expect(text).not.toContain('листа')
    expect(text).not.toContain('листов')
  })

  // An order the workshop has not planned yet has no sheet count; the em-dash
  // stands in for the number and the unit still has to render something.
  it('keeps the em-dash placeholder when no sheets are planned yet', async () => {
    vi.mocked(api.get).mockImplementation(async () => [order(2, 0)] as never)
    await setLocale('ru')

    const view = await mountOrders()

    expect(view.text().replace(/\s+/g, ' ')).toContain('2 детали · — листов')
  })
})
