import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import ClientShell from '@/apps/client/ClientShell.vue'
import { useAuthStore } from '@/shared/stores/auth'
import { useClientEntryStore, type ClientWorkshop } from '@/shared/stores/clientEntry'

vi.mock('@/shared/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/client')>('@/shared/api/client')
  return { ...actual, api: { get: vi.fn().mockResolvedValue([]), post: vi.fn() } }
})

const blank = { template: '<div />' }
const routes = [
  { path: '/c', name: 'client-home', component: blank, meta: { titleKey: 'routes.clientHome' } },
  { path: '/c/branches', name: 'client-branches', component: blank },
  { path: '/c/workshops/:id', name: 'client-workshop', component: blank },
  { path: '/c/cutting/drafts', name: 'client-drafts', component: blank },
  { path: '/c/orders', name: 'client-orders', component: blank },
  { path: '/c/profile', name: 'client-profile', component: blank },
  { path: '/c/notifications', name: 'client-notifications', component: blank },
]

function workshop(id: string): ClientWorkshop {
  return {
    workshop_id: id,
    name: `Workshop ${id}`,
    logo_file_id: null,
    public_code: id,
    is_pinned: true,
    branches: [],
  }
}

async function mountShell(workshops: ClientWorkshop[]) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/c')
  await router.isReady()

  // No token: `primeWorkshops` must not fire a fetch over the rows the test set.
  useAuthStore().accessToken = null
  useClientEntryStore().workshops = workshops

  const wrapper = mount(ClientShell, {
    global: {
      plugins: [router],
      provide: { [roleConfigKey as symbol]: clientConfig },
    },
  })
  await flushPromises()
  return wrapper
}

function ustaxonaHrefs(wrapper: Awaited<ReturnType<typeof mountShell>>) {
  const links = wrapper.findAll('a')
  return {
    nav: links.find((link) => link.text().trim() === 'Ustaxonalarim')?.attributes('href'),
    tab: links.find((link) => link.text().trim() === 'Ustaxona')?.attributes('href'),
  }
}

/**
 * Spec §2.1 defined the shortcut for the phone tab; the desktop nav renders the
 * same item and used to always land on Ustaxonalarim. Both now read
 * `clientEntry.workshopPath` — assert the two hrefs together, never one alone,
 * because a single-surface assertion is exactly what let them drift.
 */
describe('ClientShell — the Ustaxona entry point', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('sends both surfaces to the one workshop when there is only one', async () => {
    const wrapper = await mountShell([workshop('w-1')])
    expect(ustaxonaHrefs(wrapper)).toEqual({
      nav: '/c/workshops/w-1',
      tab: '/c/workshops/w-1',
    })
  })

  it('sends both surfaces to Ustaxonalarim when there is a choice to make', async () => {
    const wrapper = await mountShell([workshop('w-1'), workshop('w-2')])
    expect(ustaxonaHrefs(wrapper)).toEqual({ nav: '/c/branches', tab: '/c/branches' })
  })

  it('sends both surfaces to Ustaxonalarim before the list has loaded', async () => {
    const wrapper = await mountShell([])
    expect(ustaxonaHrefs(wrapper)).toEqual({ nav: '/c/branches', tab: '/c/branches' })
  })
})
