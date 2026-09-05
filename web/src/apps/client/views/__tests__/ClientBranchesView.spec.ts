import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/shared/api/client'
import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import ClientBranchesView from '@/apps/client/views/ClientBranchesView.vue'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { get: vi.fn(), post: vi.fn() } }
})

const { api } = await import('@/shared/api/client')

const routes = [
  { path: '/c/branches', name: 'client-branches', component: ClientBranchesView },
  { path: '/c/cutting/new', name: 'client-cutting-new', component: { template: '<div />' } },
  { path: '/c/workshops/:workshopId', name: 'client-workshop', component: { template: '<div />' } },
  {
    path: '/c/workshops/:workshopId/catalog',
    name: 'client-workshop-catalog',
    component: { template: '<div />' },
  },
]

function branch(overrides: Record<string, unknown> = {}) {
  return {
    id: 'branch-1',
    branch_no: 1,
    name: 'Chilonzor',
    address: 'Chilonzor 12',
    phone: '+998901234567',
    status: 'active',
    closed_reason: null,
    is_pinned: false,
    ...overrides,
  }
}

function workshop(overrides: Record<string, unknown> = {}) {
  return {
    workshop_id: 'workshop-1',
    name: 'Mebel Master',
    logo_file_id: null,
    public_code: 'ABCD2345',
    is_pinned: false,
    branches: [branch()],
    ...overrides,
  }
}

let router: Router
let wrapper: VueWrapper | null = null

async function mountPage() {
  router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/c/branches')
  await router.isReady()
  wrapper = mount(ClientBranchesView, {
    global: {
      plugins: [router],
      provide: { [roleConfigKey as symbol]: clientConfig },
      stubs: { AuthFileImage: true },
    },
  })
  await flushPromises()
  return wrapper
}

/** The outline star button — the row's "pin this branch" affordance (§6.1). */
function pinButtons(view: VueWrapper) {
  return view.findAll('button[aria-label="Asosiy qilish"]')
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(api.get).mockReset()
  vi.mocked(api.post).mockReset()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('Ustaxonalarim', () => {
  it('lists one card per related workshop, with pickup information per branch', async () => {
    vi.mocked(api.get).mockResolvedValue([
      workshop({ is_pinned: true, branches: [branch({ is_pinned: true })] }),
      workshop({
        workshop_id: 'workshop-2',
        name: 'Yog’och Pro',
        public_code: 'EFGH6789',
        branches: [branch({ id: 'branch-3', name: 'Sergeli', address: 'Sergeli 4' })],
      }),
    ])

    const view = await mountPage()

    expect(api.get).toHaveBeenCalledWith('/client/my-workshops', expect.anything())
    expect(view.text()).toContain('Mebel Master')
    expect(view.text()).toContain('Yog’och Pro')
    expect(view.text()).toContain('Chilonzor 12')
    expect(view.find('a[href="tel:+998901234567"]').exists()).toBe(true)
  })

  // The pin is a BRANCH (decisions 6, 15): a filled star marks the pinned row,
  // every other row carries the outline star button — and there is exactly one
  // of each across the whole page, however many workshops are listed.
  it('marks the pinned branch with a filled star and offers the button on the rest', async () => {
    vi.mocked(api.get).mockResolvedValue([
      workshop({ is_pinned: true, branches: [branch({ is_pinned: true })] }),
      workshop({ workshop_id: 'workshop-2', name: 'Yog’och Pro', public_code: 'EFGH6789' }),
    ])

    const view = await mountPage()

    expect(view.findAll('[aria-label="Asosiy"]')).toHaveLength(1)
    expect(pinButtons(view)).toHaveLength(1)
    // No «Asosiy» pill and no «Asosiy qilish» text label — the star says it.
    expect(view.text()).not.toContain('Asosiy qilish')
  })

  // No branch-choice step anywhere any more (§2.2): the row IS the branch, so
  // the star pins that one directly through the audited entry endpoint.
  it('pins the branch of the row whose star is tapped', async () => {
    vi.mocked(api.get).mockResolvedValue([
      workshop({
        branches: [branch(), branch({ id: 'branch-2', name: 'Yunusobod', address: 'Yunusobod 8' })],
      }),
    ])
    vi.mocked(api.post).mockResolvedValue({
      workshop_id: 'workshop-1',
      workshop_name: 'Mebel Master',
      branch_id: 'branch-2',
      branch_name: 'Yunusobod',
    })

    const view = await mountPage()
    await pinButtons(view).at(1)?.trigger('click')
    await flushPromises()

    // The code — never a bare branch id — is what names the workshop.
    expect(api.post).toHaveBeenCalledWith(
      '/client/entry',
      { code: 'ABCD2345', branch_id: 'branch-2' },
      expect.anything(),
    )
    expect(view.text()).not.toContain('Qaysi filialdan olib ketasiz?')
  })

  // Decision 25: tapping «Yangi chizma» is a look, not a choice — the branch
  // rides the URL and the pin stays where it is until an order is placed.
  it('opens the editor at a non-pinned branch without pinning it', async () => {
    vi.mocked(api.get).mockResolvedValue([
      workshop({
        branches: [branch({ is_pinned: true }), branch({ id: 'branch-2', name: 'Yunusobod' })],
      }),
    ])

    const view = await mountPage()
    const draw = view.findAll('a').filter((node) => node.text() === 'Yangi chizma')
    expect(draw.at(1)?.attributes('href')).toBe('/c/cutting/new?branch=branch-2')

    await draw.at(1)?.trigger('click')
    await flushPromises()

    expect(api.post).not.toHaveBeenCalled()
    expect(router.currentRoute.value.fullPath).toBe('/c/cutting/new?branch=branch-2')
  })

  it('carries the branch even when it is already the pin', async () => {
    vi.mocked(api.get).mockResolvedValue([
      workshop({ is_pinned: true, branches: [branch({ is_pinned: true })] }),
    ])

    const view = await mountPage()
    const draw = view.findAll('a').find((node) => node.text() === 'Yangi chizma')
    await draw?.trigger('click')
    await flushPromises()

    expect(api.post).not.toHaveBeenCalled()
    expect(router.currentRoute.value.fullPath).toBe('/c/cutting/new?branch=branch-1')
  })

  it('links each branch to that branch of the workshop catalog', async () => {
    vi.mocked(api.get).mockResolvedValue([workshop()])

    const view = await mountPage()

    const catalog = view.findAll('a').find((node) => node.text() === 'Katalog')
    expect(catalog?.attributes('href')).toBe('/c/workshops/workshop-1/catalog?branch=branch-1')
  })

  it('shows a temporarily closed branch with its reason', async () => {
    vi.mocked(api.get).mockResolvedValue([
      workshop({
        branches: [branch({ status: 'temporarily_closed', closed_reason: 'Ta’mirlash ishlari' })],
      }),
    ])

    const view = await mountPage()

    expect(view.text()).toContain('Vaqtincha yopiq')
    expect(view.text()).toContain('Ta’mirlash ishlari')
  })

  // Nothing on this page can invent a workshop, so the empty state explains the
  // one way in (a link or a QR) and offers no action that would dead-end.
  it('explains the workshop link when nothing is connected yet', async () => {
    vi.mocked(api.get).mockResolvedValue([])

    const view = await mountPage()

    expect(view.text()).toContain('Hali ustaxona ulanmagan')
    expect(view.text()).toContain('Ustaxonangiz bergan havola yoki QR kod orqali kiring')
    expect(view.text()).not.toContain('Yangi chizma')
  })

  it('names the failure and retries', async () => {
    vi.mocked(api.get).mockRejectedValue(new ApiError(500, { code: 'server_error' }))

    const view = await mountPage()

    expect(view.text()).toContain("Ustaxonalarni yuklab bo'lmadi")
    expect(view.findAll('button').some((node) => node.text().includes('Qayta urinish'))).toBe(true)
  })
})
