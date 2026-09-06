import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import ClientOrderDetailView from '@/apps/client/views/ClientOrderDetailView.vue'
import { DEFAULT_LOCALE, setLocale } from '@/shared/i18n'
import { useAuthStore } from '@/shared/stores/auth'
import type { OrderDetail } from '@/shared/stores/orders'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { get: vi.fn(), post: vi.fn() } }
})

const { api } = await import('@/shared/api/client')

const routes = [
  { path: '/c', name: 'client-home', component: { template: '<div />' } },
  { path: '/c/orders', name: 'client-orders', component: { template: '<div />' } },
  { path: '/c/orders/:order_id', name: 'client-order', component: ClientOrderDetailView },
]

/**
 * Only the receipt's own fields matter here: the cutting-service line reads
 * `planned_panels`, and one material row is built per `panel` price line from
 * its `panels_used`. Everything else is the minimum that keeps the populated
 * branch of the template rendering — no cutting result, so the drawing tab and
 * the parts table stay out of the way.
 */
function orderWith(panels: number, overrides: Partial<OrderDetail> = {}): OrderDetail {
  return {
    id: 'order-1',
    order_number: '100001',
    draft_name: null,
    workshop_name: 'Mebel Master',
    branch_name: 'Chilonzor',
    branch_address: 'Chilonzor 12',
    branch_phone: '+998901234567',
    branch_additional_phones: [],
    branch_latitude: null,
    branch_longitude: null,
    status: 'new',
    version: 1,
    item_count: panels,
    planned_panels: panels,
    subtotal_cutting_tiyin: 50_000,
    subtotal_materials_tiyin: 300_000,
    subtotal_edge_banding_tiyin: 0,
    surcharge_tiyin: 0,
    surcharge_reason: null,
    discount_tiyin: 0,
    discount_reason: null,
    total_tiyin: 350_000,
    created_at: '2026-09-01T10:00:00Z',
    items: [],
    events: [],
    price_lines: [
      {
        material_id: 'material-1',
        material_name: 'LDSP Belyy 16mm',
        kind: 'panel',
        panels_used: panels,
        consumed_mm: null,
        unit_price_tiyin: 300_000,
        own_panels: 0,
        own_mm: 0,
        line_total_tiyin: 300_000,
      },
    ],
    cutting_result: null,
    settlement: null,
    workshop_branch_count: 1,
    ...overrides,
  } as unknown as OrderDetail
}

let router: Router
let wrapper: VueWrapper | null = null

async function mountDetail(panels: number, overrides: Partial<OrderDetail> = {}) {
  const auth = useAuthStore()
  auth.accessToken = 'access-1'
  auth.status = 'authenticated'

  vi.mocked(api.get).mockResolvedValue(orderWith(panels, overrides) as never)

  router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/c/orders/order-1')
  await router.isReady()
  wrapper = mount(ClientOrderDetailView, {
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
})

afterEach(async () => {
  wrapper?.unmount()
  wrapper = null
  await setLocale(DEFAULT_LOCALE)
})

// Decision 24 — the Ustaxona card reaches the counter on every line it
// publishes, not only the first.
describe('ClientOrderDetailView — every branch phone is dialable (decision 24)', () => {
  it('lists the primary first and then the extras, each its own tel: link', async () => {
    const view = await mountDetail(1, {
      branch_additional_phones: ['+998902222222', '+998903333333'],
    } as Partial<OrderDetail>)

    expect(view.findAll('a[href^="tel:"]').map((link) => link.attributes('href'))).toEqual([
      'tel:+998901234567',
      'tel:+998902222222',
      'tel:+998903333333',
    ])
  })

  it('renders one link when the branch publishes one number', async () => {
    const view = await mountDetail(1)

    expect(view.findAll('a[href^="tel:"]')).toHaveLength(1)
  })
})

// Decision 23 — the Ustaxona card names the counter the same way the orders
// list does. The workshop is always the title; the branch earns a second line
// only where there is more than one branch to tell apart. The branch name in
// these fixtures is deliberately unlike the address, so an assertion about the
// name cannot pass on the address line.
describe('ClientOrderDetailView — the Ustaxona card names the workshop (decision 23)', () => {
  const named = { branch_name: 'Yunusobod filiali' } as Partial<OrderDetail>

  it('shows the workshop alone when it has one visible branch', async () => {
    const view = await mountDetail(1, { ...named, workshop_branch_count: 1 })

    const text = view.text()
    expect(text).toContain('Mebel Master')
    expect(text).not.toContain('Yunusobod filiali')
    // The address stays: it is how the client finds the door.
    expect(text).toContain('Chilonzor 12')
  })

  it('adds the branch line once the workshop has several', async () => {
    const view = await mountDetail(1, { ...named, workshop_branch_count: 3 })

    const text = view.text()
    expect(text).toContain('Mebel Master')
    expect(text).toContain('Yunusobod filiali')
  })
})

/**
 * The receipt counts sheets twice — under «Xizmat» for the whole order, and
 * under every material row — and both come from `client.unit.sheets`. That key
 * carried a single Russian form («{n} лист»), so an order of two sheets read
 * «2 лист» however many sheets it had. Both call sites already hand the count
 * over as the plural choice; the forms were what was missing.
 */
describe('ClientOrderDetailView — the receipt agrees with its sheet counts', () => {
  it.each([
    [1, '1 лист'],
    [2, '2 листа'],
    [5, '5 листов'],
  ])('inflects лист for %i in Russian', async (panels, expected) => {
    await setLocale('ru')
    const view = await mountDetail(panels)

    const rows = view.findAll('.client-row-item')
    // First row is the cutting service, second the one material line.
    expect(rows[0].text()).toContain(expected)
    expect(rows[1].text()).toContain(expected)
  })

  it('keeps the single Uzbek form at every count', async () => {
    for (const panels of [1, 2, 5]) {
      const view = await mountDetail(panels)
      const rows = view.findAll('.client-row-item')
      expect(rows[0].text()).toContain(`${panels} list`)
      expect(rows[1].text()).toContain(`${panels} list`)
      view.unmount()
      wrapper = null
    }
  })
})

/**
 * Decision 22, amended 2026-09-06 — the header card names the day the order was
 * placed, in the one client date format, under the number and the drawing name.
 * What «no dates» still means here is no phase dates and no timeline. The
 * fixture timestamp is zone-less on purpose so it parses as local time and the
 * assertion is about the shape, not about the runner's timezone.
 */
describe('ClientOrderDetailView — the header card date (decision 22)', () => {
  it('spells the date out in Uzbek, inside the header card', async () => {
    const view = await mountDetail(1, {
      created_at: '2026-04-26T09:32:00',
    } as Partial<OrderDetail>)

    const header = view.find('section.client-card')
    expect(header.text().replace(/\s+/g, ' ')).toContain('26-aprel 2026, 09:32')
    // The numeric shape the client never uses must be absent, not merely unused.
    expect(view.text()).not.toContain('26.04.2026')
    expect(view.text()).not.toMatch(/kecha|kun oldin/)
  })

  it('uses the Russian genitive month', async () => {
    await setLocale('ru')

    const view = await mountDetail(1, {
      created_at: '2026-04-26T09:32:00',
    } as Partial<OrderDetail>)

    expect(view.text().replace(/\s+/g, ' ')).toContain('26 апреля 2026, 09:32')
  })
})
