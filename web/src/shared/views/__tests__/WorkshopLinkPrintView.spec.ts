import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { roleConfigKey, workshopConfig } from '@/shared/app/roleConfig'
import WorkshopLinkPrintView from '@/shared/views/WorkshopLinkPrintView.vue'
import { useAuthStore, type MeResponse } from '@/shared/stores/auth'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }
})

const { api } = await import('@/shared/api/client')

const routes = [
  {
    path: '/workshop/branches/:branch_id/client-link',
    component: WorkshopLinkPrintView,
  },
  { path: '/workshop/settings/client-link', component: WorkshopLinkPrintView },
]

const settings = {
  id: 'workshop-1',
  name: 'Mebel Master',
  logo_file_id: null,
  public_code: 'ABCD2345',
  status: 'active',
  currency: 'UZS',
  owner_user_id: 'user-1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const branch = {
  id: 'branch-1',
  workshop_id: 'workshop-1',
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
  edge_trim_mm: 5,
  edge_overhang_mm: 30,
  own_material_allowed: false,
  production_mode: 'simple',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function ownerMe(): MeResponse {
  return {
    principal_type: 'workshop_user',
    principal_id: 'user-1',
    session_id: 'session-1',
    password_reset_required: false,
    workshop_id: 'workshop-1',
    workshop_name: 'Mebel Master',
    is_owner: true,
    grants: [],
    login: 'owner',
    full_name: 'Owner',
    phone: '+998901112233',
    name: null,
    preferred_branch_id: null,
    status: 'active',
  }
}

let wrapper: VueWrapper | null = null

async function mountSheet(path: string) {
  const auth = useAuthStore()
  auth.accessToken = 'access-1'
  auth.me = ownerMe()
  auth.status = 'authenticated'

  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  wrapper = mount(WorkshopLinkPrintView, {
    global: {
      plugins: [router],
      provide: { [roleConfigKey as symbol]: workshopConfig },
      stubs: { AuthFileImage: true },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubEnv('DEV', false)
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { origin: 'https://workshop.mebel-pro.uz', pathname: '/branches/1/client-link' },
  })
  vi.mocked(api.get).mockReset()
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path === '/workshop/settings') return settings
    if (path.startsWith('/workshop/branches/')) return branch
    return null
  })
})

afterEach(() => {
  vi.unstubAllEnvs()
  wrapper?.unmount()
  wrapper = null
})

describe('the counter sheet', () => {
  it('carries the workshop, the branch, the QR, the tagline and the link', async () => {
    const view = await mountSheet('/workshop/branches/branch-1/client-link')

    expect(view.text()).toContain('Mebel Master')
    expect(view.text()).toContain('Chilonzor')
    expect(view.text()).toContain("Chizmangizni o'zingiz chizing — narxini darhol bilasiz")
    expect(view.text()).toContain('https://app.mebel-pro.uz/w/ABCD2345/3')

    const qr = view.get('svg[role="img"]')
    expect(qr.find('path').attributes('d')).toBeTruthy()
  })

  it('drops the branch line on the workshop-level sheet', async () => {
    const view = await mountSheet('/workshop/settings/client-link')

    expect(view.text()).toContain('Mebel Master')
    expect(view.text()).not.toContain('Chilonzor')
    expect(view.text()).toContain('https://app.mebel-pro.uz/w/ABCD2345')
    // Only the settings read is needed — there is no branch to fetch.
    expect(api.get).toHaveBeenCalledWith('/workshop/settings', expect.anything())
  })

  it('keeps the print control off the paper', async () => {
    const view = await mountSheet('/workshop/settings/client-link')

    const printButton = view.findAll('button').find((node) => node.text() === 'Chop etish')
    expect(printButton).toBeTruthy()
    // `print:hidden` — the browser's own dialog is the action once printing starts.
    expect(printButton?.element.parentElement?.className).toContain('print:hidden')
  })
})
