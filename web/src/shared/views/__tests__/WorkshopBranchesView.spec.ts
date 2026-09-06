import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { roleConfigKey, workshopConfig } from '@/shared/app/roleConfig'
import WorkshopBranchesView from '@/shared/views/WorkshopBranchesView.vue'
import { useAuthStore } from '@/shared/stores/auth'
import { useToast } from '@/shared/composables/useToast'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { ...actual.api, get: vi.fn() } }
})

const { api } = await import('@/shared/api/client')

const branches = [
  {
    id: 'b-1',
    workshop_id: 'w-1',
    workshop_public_code: 'ABCD2345',
    branch_no: 3,
    name: 'Chilonzor',
    address: 'Chilonzor 12',
    phone: '+998901234567',
    additional_phones: [],
    latitude: null,
    longitude: null,
    status: 'active',
    closed_reason: null,
    kerf_mm: 4,
    edge_trim_mm: 10,
    edge_overhang_mm: 5,
    own_material_allowed: false,
    production_mode: 'simple',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: WorkshopBranchesView },
      { path: '/workshop/branches/:branch_id', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  await router.isReady()

  const auth = useAuthStore()
  auth.me = { is_owner: true } as never
  vi.mocked(api.get).mockResolvedValue(branches as never)

  const view = mount(WorkshopBranchesView, {
    global: { plugins: [router], provide: { [roleConfigKey as symbol]: workshopConfig } },
  })
  await flushPromises()
  return view
}

function copyControl(view: Awaited<ReturnType<typeof mountView>>) {
  return view
    .findAll('button')
    .find((node) => node.attributes('aria-label') === 'Chilonzor havolasini nusxalash')
}

beforeEach(() => {
  setActivePinia(createPinia())
  useToast().toasts.value = []
  // Production host: the list lives in the workshop app, the link it copies
  // points at the client app on another subdomain (`workshopLink.spec.ts` owns
  // the dev role-base branch).
  vi.stubEnv('DEV', false)
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { origin: 'https://workshop.mebel-pro.uz', pathname: '/branches' },
  })
})

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('Filiallar list — copying a branch client link from the row', () => {
  it('copies the branch link and says so, without opening the branch', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })

    const view = await mountView()
    const control = copyControl(view)
    expect(control).toBeDefined()
    await control?.trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith('https://app.mebel-pro.uz/w/ABCD2345/3')
    expect(useToast().toasts.value[0].message).toBe('Havola nusxalandi')
  })

  it('keeps the row link as the only navigation control in the row', async () => {
    const view = await mountView()

    // QAD-184: the branch name is the row's stretched open target. The copy
    // button must not become a second one, or E2E's row-link locator (and a
    // keyboard user's expectation of one open action per row) breaks.
    const links = view.findAll('tbody a')
    expect(links).toHaveLength(1)
    expect(links[0].text()).toBe('Chilonzor')
    expect(copyControl(view)?.element.tagName).toBe('BUTTON')
  })

  it('sends the owner to the branch screen when the clipboard refuses', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    })

    const view = await mountView()
    await copyControl(view)?.trigger('click')
    await flushPromises()

    const toast = useToast().toasts.value[0]
    expect(toast.tone).toBe('danger')
    expect(toast.message).toContain('filial sahifasidan')
  })
})
