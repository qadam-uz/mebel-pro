import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import BranchContact from '@/shared/components/BranchContact.vue'

function mountContact(props: Record<string, unknown> = {}) {
  return mount(BranchContact, {
    props: {
      address: 'Toshkent, Amir Temur 108',
      phone: '+998712007878',
      ...props,
    },
    global: {
      stubs: { Icon: true },
      mocks: { $t: (key: string) => key },
    },
  })
}

describe('BranchContact', () => {
  it('lists the primary number first, then the extras, all tap-to-call', () => {
    const wrapper = mountContact({ additionalPhones: ['+998901112233', '+998935556677'] })

    const hrefs = wrapper.findAll('a[href^="tel:"]').map((node) => node.attributes('href'))
    expect(hrefs).toEqual(['tel:+998712007878', 'tel:+998901112233', 'tel:+998935556677'])
  })

  it('works with no extra numbers', () => {
    const wrapper = mountContact()

    expect(wrapper.findAll('a[href^="tel:"]')).toHaveLength(1)
  })

  // Yandex takes longitude first; the branch record stores latitude first. A
  // swap here opens the map in the wrong hemisphere.
  it('links the pin to Yandex, longitude first', () => {
    const wrapper = mountContact({ latitude: '41.311081', longitude: '69.240562' })

    const href = wrapper.find('a[href*="yandex"]').attributes('href')
    expect(href).toContain('ll=69.240562%2C41.311081')
    expect(href).toContain('pt=69.240562%2C41.311081')
  })

  // Coordinates are optional on a branch — a link to nowhere is worse than one
  // that is simply absent, and a half-set pair is no pin at all.
  it('renders no map link when the branch has no pin', () => {
    expect(mountContact().find('a[href*="yandex"]').exists()).toBe(false)
    expect(
      mountContact({ latitude: '41.3', longitude: null }).find('a[href*="yandex"]').exists(),
    ).toBe(false)
  })

  // Icon-only, so the name has to come from somewhere a screen reader reaches.
  it('names the icon-only map link', () => {
    const link = mountContact({ latitude: '41.3', longitude: '69.2' }).find('a[href*="yandex"]')

    expect(link.attributes('aria-label')).toBe('client.branches.openMap')
  })

  it('always shows the address', () => {
    expect(mountContact().text()).toContain('Toshkent, Amir Temur 108')
  })
})
