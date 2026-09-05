import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/shared/api/client'
import { readClientEntry, takeEntryToast } from '@/shared/app/clientEntry'
import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import ClientEntryView from '@/apps/client/views/ClientEntryView.vue'
import { useAuthStore, type MeResponse } from '@/shared/stores/auth'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { get: vi.fn(), post: vi.fn() } }
})

const { api } = await import('@/shared/api/client')

const routes = [
  { path: '/w/:code', name: 'client-entry', component: ClientEntryView },
  { path: '/w/:code/:branchNo', name: 'client-entry-branch', component: ClientEntryView },
  { path: '/c', name: 'client-home', component: { template: '<div />' } },
  { path: '/auth/login', name: 'client-login', component: { template: '<div />' } },
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

function branch(overrides: Record<string, unknown> = {}) {
  return {
    id: 'branch-1',
    branch_no: 1,
    name: 'Chilonzor',
    address: 'Chilonzor 12',
    phone: '+998901234567',
    status: 'active',
    closed_reason: null,
    ...overrides,
  }
}

function linkPayload(overrides: Record<string, unknown> = {}) {
  return {
    code: 'ABCD2345',
    workshop_name: 'Mebel Master',
    workshop_logo_file_id: null,
    branches: [branch()],
    requested_branch_id: null,
    branch_no_fallback: false,
    ...overrides,
  }
}

let router: Router
let wrapper: VueWrapper | null = null

async function mountEntry(path = '/w/ABCD2345') {
  router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  wrapper = mount(ClientEntryView, {
    global: {
      plugins: [router],
      provide: { [roleConfigKey as symbol]: clientConfig },
    },
  })
  await flushPromises()
  return wrapper
}

/** Sign the client in, the way `auth.restore()` would have before this route. */
function signIn(overrides: Partial<MeResponse> = {}) {
  const auth = useAuthStore()
  auth.accessToken = 'access-1'
  auth.me = clientMe(overrides)
  auth.status = 'authenticated'
}

beforeEach(() => {
  setActivePinia(createPinia())
  window.localStorage.clear()
  vi.mocked(api.get).mockReset()
  vi.mocked(api.post).mockReset()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('ClientEntryView — resolved single branch, signed out', () => {
  it('shows the greeting, the branch and the Kirish action, and parks the entry', async () => {
    vi.mocked(api.get).mockResolvedValue(linkPayload())

    const view = await mountEntry()

    expect(view.text()).toContain('Mebel Master sizni taklif qilmoqda')
    expect(view.text()).toContain('Chilonzor')
    expect(view.text()).toContain('Chilonzor 12')
    expect(view.text()).toContain('Kirish')
    // A single visible branch is not a choice — the link means that counter.
    expect(view.text()).not.toContain('Qaysi filialdan olib ketasiz?')
    // Step 2 of §3.1: parked before the login round-trip.
    expect(readClientEntry()).toEqual({ code: 'ABCD2345', branch_id: 'branch-1' })
    // Nothing was pinned — there is no session to pin to.
    expect(api.post).not.toHaveBeenCalled()
  })

  it('sends Kirish into the existing Telegram sign-in', async () => {
    vi.mocked(api.get).mockResolvedValue(linkPayload())
    const view = await mountEntry()

    await view
      .findAll('button')
      .find((node) => node.text() === 'Kirish')
      ?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/auth/login')
  })

  it('passes the branch_no of a branch link to the resolve endpoint', async () => {
    vi.mocked(api.get).mockResolvedValue(
      linkPayload({
        branches: [branch(), branch({ id: 'branch-2', name: 'Yunusobod' })],
        requested_branch_id: 'branch-1',
      }),
    )

    const view = await mountEntry('/w/ABCD2345/1')

    expect(api.get).toHaveBeenCalledWith('/public/workshop-links/ABCD2345?branch_no=1')
    // A branch link never shows the choice, even with several branches behind it.
    expect(view.text()).not.toContain('Qaysi filialdan olib ketasiz?')
    expect(readClientEntry()?.branch_id).toBe('branch-1')
  })
})

describe('ClientEntryView — the branch choice (§3.2)', () => {
  const multi = () =>
    linkPayload({
      branches: [
        branch(),
        branch({
          id: 'branch-2',
          branch_no: 2,
          name: 'Yunusobod',
          status: 'temporarily_closed',
          closed_reason: 'Ta’mirlash ishlari',
        }),
      ],
    })

  it('asks which branch, listing only that workshop, closed ones included', async () => {
    vi.mocked(api.get).mockResolvedValue(multi())

    const view = await mountEntry()

    expect(view.text()).toContain('Qaysi filialdan olib ketasiz?')
    expect(view.text()).toContain('Chilonzor')
    expect(view.text()).toContain('Yunusobod')
    // A temporarily closed branch renders its reason and stays choosable.
    expect(view.text()).toContain('Ta’mirlash ishlari')
    const closed = view.findAll('button').find((node) => node.text().includes('Yunusobod'))
    expect(closed?.attributes('disabled')).toBeUndefined()
    // Nothing is parked until a branch is actually chosen.
    expect(readClientEntry()).toBeNull()
  })

  it('parks the chosen branch on one tap when signed out', async () => {
    vi.mocked(api.get).mockResolvedValue(multi())
    const view = await mountEntry()

    await view
      .findAll('button')
      .find((node) => node.text().includes('Yunusobod'))
      ?.trigger('click')
    await flushPromises()

    expect(readClientEntry()).toEqual({ code: 'ABCD2345', branch_id: 'branch-2' })
    expect(view.text()).toContain('Kirish')
  })

  it('shows the choice a branch link fell back from (§8)', async () => {
    // The printed QR named a branch_no that is gone; the code still resolves.
    vi.mocked(api.get).mockResolvedValue(
      linkPayload({
        branches: multi().branches,
        requested_branch_id: null,
        branch_no_fallback: true,
      }),
    )

    const view = await mountEntry('/w/ABCD2345/7')

    expect(view.text()).toContain('Qaysi filialdan olib ketasiz?')
  })
})

describe('ClientEntryView — the logged-in fast path', () => {
  it('applies the pin immediately and lands on home with the toast queued', async () => {
    signIn()
    vi.mocked(api.get).mockImplementation(async (path: string) =>
      path.startsWith('/public/workshop-links')
        ? linkPayload()
        : clientMe({ pinned_workshop_name: 'Mebel Master', pinned_branch_name: 'Chilonzor' }),
    )
    vi.mocked(api.post).mockResolvedValue({
      workshop_id: 'workshop-1',
      workshop_name: 'Mebel Master',
      branch_id: 'branch-1',
      branch_name: 'Chilonzor',
    })

    await mountEntry()
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith(
      '/client/entry',
      { code: 'ABCD2345', branch_id: 'branch-1' },
      expect.anything(),
    )
    expect(router.currentRoute.value.path).toBe('/c')
    // Never leaves the applied entry behind to be re-applied.
    expect(readClientEntry()).toBeNull()
    expect(takeEntryToast()).toBe('Mebel Master')
  })

  it('says so, without touching the session, when the apply is refused', async () => {
    signIn()
    vi.mocked(api.get).mockResolvedValue(linkPayload())
    vi.mocked(api.post).mockRejectedValue(new ApiError(404, { code: 'workshop_link_not_found' }))

    const view = await mountEntry()
    await flushPromises()

    expect(view.text()).toContain("Ustaxonaga ulanib bo'lmadi")
    expect(router.currentRoute.value.path).toBe('/w/ABCD2345')
    expect(useAuthStore().isAuthenticated).toBe(true)
  })
})

describe('ClientEntryView — dead and throttled links', () => {
  it('shows one friendly dead-link screen, never a raw 404', async () => {
    vi.mocked(api.get).mockRejectedValue(new ApiError(404, { code: 'workshop_link_not_found' }))

    const view = await mountEntry()

    expect(view.text()).toContain('Havola topilmadi')
    expect(view.text()).toContain('QR kodni qaytadan skanerlang')
    expect(view.text()).toContain('Ilovani ochish')
    expect(view.text()).not.toContain('404')
  })

  it('opens the app from the dead-link screen', async () => {
    vi.mocked(api.get).mockRejectedValue(new ApiError(404, { code: 'workshop_link_not_found' }))
    const view = await mountEntry()

    await view
      .findAll('button')
      .find((node) => node.text() === 'Ilovani ochish')
      ?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/c')
  })

  it('renders the transient variant with a retry on a rate limit, never a raw 429', async () => {
    vi.mocked(api.get).mockRejectedValue(new ApiError(429, { code: 'workshop_link_rate_limited' }))

    const view = await mountEntry()

    expect(view.text()).toContain('Havola hozir ochilmadi')
    expect(view.text()).not.toContain('Havola topilmadi')
    expect(view.text()).not.toContain('429')

    vi.mocked(api.get).mockResolvedValue(linkPayload())
    await view
      .findAll('button')
      .find((node) => node.text() === 'Qayta urinish')
      ?.trigger('click')
    await flushPromises()

    expect(view.text()).toContain('Mebel Master sizni taklif qilmoqda')
  })
})
