import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useToast } from '@/shared/composables/useToast'
import WorkshopLinkCard from '@/shared/components/WorkshopLinkCard.vue'

const routes = [
  { path: '/', component: { template: '<div />' } },
  { path: '/workshop/branches/:branch_id/client-link', component: { template: '<div />' } },
  { path: '/workshop/settings/client-link', component: { template: '<div />' } },
]

async function mountCard(props: Record<string, unknown>) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(WorkshopLinkCard, {
    props: { code: 'ABCD2345', printTo: '/workshop/settings/client-link', ...props },
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  useToast().toasts.value = []
  // Production host: the card lives in the workshop app, the link points at the
  // client app on a different subdomain. Vitest runs with `DEV` on, which would
  // otherwise take the dev role-base branch — the host-swap is what this card is
  // being asserted about, and `workshopLink.spec.ts` covers the dev branch.
  vi.stubEnv('DEV', false)
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { origin: 'https://workshop.mebel-pro.uz', pathname: '/branches/1' },
  })
})

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('Mijoz havolasi card', () => {
  it('renders the branch link, its QR, and the copy + print actions', async () => {
    const view = await mountCard({
      branchNo: 3,
      printTo: '/workshop/branches/b-1/client-link',
    })

    expect(view.text()).toContain('Mijoz havolasi')
    // The absolute URL a client scans — client host, not the workshop's.
    expect(view.get('#client-link-url').attributes('value')).toBe(
      'https://app.mebel-pro.uz/w/ABCD2345/3',
    )
    // A real inline SVG, drawn in the browser — no external QR service.
    const qr = view.get('svg[role="img"]')
    expect(qr.attributes('aria-label')).toBe('Mijoz havolasining QR kodi')
    expect(qr.find('path').attributes('d')).toBeTruthy()
    expect(view.html()).not.toContain('http://api.qrserver')

    expect(view.findAll('button').some((node) => node.text() === 'Nusxalash')).toBe(true)
    expect(view.get('a[href="/workshop/branches/b-1/client-link"]').text()).toBe('Chop etish')
  })

  it('renders the workshop-level link when no branch is named', async () => {
    const view = await mountCard({})

    expect(view.get('#client-link-url').attributes('value')).toBe(
      'https://app.mebel-pro.uz/w/ABCD2345',
    )
    expect(view.text()).toContain('filialni')
  })

  it('copies the link and says so', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    const view = await mountCard({ branchNo: 1 })
    await view
      .findAll('button')
      .find((node) => node.text() === 'Nusxalash')
      ?.trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith('https://app.mebel-pro.uz/w/ABCD2345/1')
    expect(useToast().toasts.value[0].message).toBe('Havola nusxalandi')
  })

  it('tells the owner what to do instead when the clipboard refuses', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: vi.fn().mockRejectedValue(new Error('denied')),
      },
    })

    const view = await mountCard({ branchNo: 1 })
    await view
      .findAll('button')
      .find((node) => node.text() === 'Nusxalash')
      ?.trigger('click')
    await flushPromises()

    expect(view.text()).toContain("Nusxalab bo'lmadi")
    expect(useToast().toasts.value).toHaveLength(0)
    // The field is still there to select by hand.
    expect(view.get('#client-link-url').attributes('readonly')).toBeDefined()
  })
})
