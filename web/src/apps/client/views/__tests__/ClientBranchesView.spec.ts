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
  it('groups by workshop and badges the pinned one', async () => {
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
    expect(view.text()).toContain('Ustaxonalarim')
    expect(view.text()).toContain('Mebel Master')
    expect(view.text()).toContain('Yog’och Pro')
    // Exactly one Asosiy badge, on the pinned workshop.
    expect(view.text().match(/Asosiy(?! qilish)/g)).toHaveLength(1)
    // Pickup and contact information, and nothing that leads to a catalog.
    expect(view.text()).toContain('Chilonzor 12')
    expect(view.find('a[href="tel:+998901234567"]').exists()).toBe(true)
  })

  it('offers Asosiy qilish only on workshops that are not the pin', async () => {
    vi.mocked(api.get).mockResolvedValue([
      workshop({ is_pinned: true }),
      workshop({ workshop_id: 'workshop-2', name: 'Yog’och Pro', public_code: 'EFGH6789' }),
    ])

    const view = await mountPage()

    const pinButtons = view.findAll('button').filter((node) => node.text() === 'Asosiy qilish')
    expect(pinButtons).toHaveLength(1)
  })

  it('pins a single-branch workshop straight through the entry endpoint', async () => {
    vi.mocked(api.get).mockResolvedValue([
      workshop({ workshop_id: 'workshop-2', name: 'Yog’och Pro', public_code: 'EFGH6789' }),
    ])
    vi.mocked(api.post).mockResolvedValue({
      workshop_id: 'workshop-2',
      workshop_name: 'Yog’och Pro',
      branch_id: 'branch-1',
      branch_name: 'Chilonzor',
    })

    const view = await mountPage()
    await view
      .findAll('button')
      .find((node) => node.text() === 'Asosiy qilish')
      ?.trigger('click')
    await flushPromises()

    // The code — never a bare branch id — is what names the workshop.
    expect(api.post).toHaveBeenCalledWith(
      '/client/entry',
      { code: 'EFGH6789', branch_id: 'branch-1' },
      expect.anything(),
    )
  })

  it('asks which branch when the workshop has several', async () => {
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
    await view
      .findAll('button')
      .find((node) => node.text() === 'Asosiy qilish')
      ?.trigger('click')
    await flushPromises()

    expect(view.text()).toContain('Qaysi filialdan olib ketasiz?')

    const choice = view
      .findAll('button')
      .filter((node) => node.text().includes('Yunusobod'))
      .at(-1)
    await choice?.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith(
      '/client/entry',
      { code: 'ABCD2345', branch_id: 'branch-2' },
      expect.anything(),
    )
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

  it('invites through a workshop link when nothing is connected yet', async () => {
    vi.mocked(api.get).mockResolvedValue([])

    const view = await mountPage()

    expect(view.text()).toContain('Hali ustaxona ulanmagan')
    expect(view.text()).toContain('Ustaxonangiz bergan havola yoki QR kod orqali kiring')
    // The organic path stays open.
    expect(view.text()).toContain('Yangi chizma')
  })

  it('names the failure and retries', async () => {
    vi.mocked(api.get).mockRejectedValue(new ApiError(500, { code: 'server_error' }))

    const view = await mountPage()

    expect(view.text()).toContain("Ustaxonalarni yuklab bo'lmadi")
    expect(view.findAll('button').some((node) => node.text().includes('Qayta urinish'))).toBe(true)
  })
})
