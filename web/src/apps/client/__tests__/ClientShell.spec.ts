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
  {
    path: '/c/cutting/:id',
    name: 'client-editor',
    component: blank,
    meta: { titleKey: 'routes.draft', chromeless: true },
  },
  { path: '/auth/login', name: 'client-login', component: blank, meta: { layout: 'auth' } },
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

async function mountShell(workshops: ClientWorkshop[], path = '/c') {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
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

/** Both surfaces are labelled «Ustaxona», so they are told apart by their
 *  container rather than their text: `.client-nav` is the desktop header nav,
 *  the other `<nav>` is the phone tab bar. */
function ustaxonaHrefs(wrapper: Awaited<ReturnType<typeof mountShell>>) {
  const hrefIn = (selector: string) =>
    wrapper
      .findAll(`${selector} a`)
      .find((link) => link.text().trim() === 'Ustaxona')
      ?.attributes('href')
  return { nav: hrefIn('nav.client-nav'), tab: hrefIn('nav:not(.client-nav)') }
}

/**
 * Spec §2.1 defined the shortcut for the phone tab; the desktop nav renders the
 * same item and used to always land on Ustaxonalarim. Both now read
 * `clientEntry.workshopPath` — and share one label key — so assert the two
 * hrefs together, never one alone: a single-surface assertion is exactly what
 * let them drift.
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

/**
 * Both halves of `isChromelessRoute` render without header or tab bar, and they
 * used to render identically — which left the editor, the result stage and the
 * order confirmation with no page gutter at all: on a phone the back link, the
 * title and the cards sat on the viewport edge (the ⋯ button's 44px tap target
 * pushed `scrollWidth` 4px past `clientWidth`), and on a desktop the title
 * started at x=0 while every other client page was centred.
 *
 * A `meta.chromeless` route is still a page of the app, so it gets the column.
 * A `layout: 'auth'` route is a card that centres itself in the viewport, so it
 * must not — assert the pair together, since only the contrast is the rule.
 */
describe('ClientShell — the chromeless page column', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('gives a signed-in chromeless route the client page column', async () => {
    const wrapper = await mountShell([workshop('w-1')], '/c/cutting/draft-1')
    const main = wrapper.find('main')
    expect(main.exists()).toBe(true)
    expect(main.classes()).toContain('client-container')
    expect(main.classes()).toContain('client-focus-page')
    // Still chromeless: no header, no tab bar.
    expect(wrapper.find('header').exists()).toBe(false)
    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('leaves a `layout: auth` route to lay itself out', async () => {
    const wrapper = await mountShell([workshop('w-1')], '/auth/login')
    expect(wrapper.find('.client-container').exists()).toBe(false)
    expect(wrapper.find('.client-focus-page').exists()).toBe(false)
    expect(wrapper.find('header').exists()).toBe(false)
  })
})
