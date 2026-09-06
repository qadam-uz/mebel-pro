import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AdminClientLinksCard from '@/shared/components/AdminClientLinksCard.vue'
import { useToast } from '@/shared/composables/useToast'

const branches = [
  { id: 'b-1', branch_no: 1, name: 'Chilonzor', status: 'active' },
  { id: 'b-2', branch_no: 7, name: 'Yunusobod', status: 'temporarily_closed' },
]

function mountCard() {
  return mount(AdminClientLinksCard, {
    props: { code: 'ABCD2345', branches },
  })
}

function copyButton(view: ReturnType<typeof mountCard>, label: string) {
  return view.findAll('button').find((node) => node.attributes('aria-label') === label)
}

beforeEach(() => {
  setActivePinia(createPinia())
  useToast().toasts.value = []
  // Production hosts: the card lives in the platform app, the links point at the
  // client app on a different subdomain. Vitest runs with `DEV` on, which would
  // otherwise take the dev role-base branch (covered in `workshopLink.spec.ts`).
  vi.stubEnv('DEV', false)
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { origin: 'https://admin.mebel-pro.uz', pathname: '/workshops/w-1' },
  })
})

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('Mijoz havolalari — the platform operator card', () => {
  it('builds the workshop link and one link per branch from the public code', async () => {
    const view = mountCard()
    await flushPromises()

    expect(view.text()).toContain('Mijoz havolalari')
    expect(view.get('#admin-client-link-workshop').attributes('value')).toBe(
      'https://app.mebel-pro.uz/w/ABCD2345',
    )
    expect(view.text()).toContain('https://app.mebel-pro.uz/w/ABCD2345/1')
    expect(view.text()).toContain('https://app.mebel-pro.uz/w/ABCD2345/7')
  })

  it('keeps a closed branch copyable and says what state it is in', async () => {
    const view = mountCard()
    await flushPromises()

    expect(view.text()).toContain('Vaqtincha yopiq')
    expect(copyButton(view, 'Yunusobod havolasini nusxalash')?.attributes('disabled')).toBe(
      undefined,
    )
  })

  it('copies a branch link and says so', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })

    const view = mountCard()
    await flushPromises()
    await copyButton(view, 'Chilonzor havolasini nusxalash')?.trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith('https://app.mebel-pro.uz/w/ABCD2345/1')
    expect(useToast().toasts.value[0].message).toBe('Havola nusxalandi')
  })

  it('copies the workshop-level link too', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })

    const view = mountCard()
    await flushPromises()
    await copyButton(view, 'Ustaxona havolasini nusxalash')?.trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith('https://app.mebel-pro.uz/w/ABCD2345')
  })

  it('annotates only the row whose clipboard refused', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    })

    const view = mountCard()
    await flushPromises()
    await copyButton(view, 'Chilonzor havolasini nusxalash')?.trigger('click')
    await flushPromises()

    expect(view.findAll('[role="status"]')).toHaveLength(1)
    expect(view.get('[role="status"]').text()).toContain("Nusxalab bo'lmadi")
    expect(useToast().toasts.value).toHaveLength(0)
  })
})
