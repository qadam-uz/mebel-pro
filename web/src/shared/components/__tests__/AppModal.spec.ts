import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import AppModal from '@/shared/components/AppModal.vue'

describe('AppModal', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders its title and slot only while open', async () => {
    const wrapper = mount(AppModal, {
      props: { open: false, title: 'Kirim' },
      slots: { default: '<p class="body-slot">form</p>' },
      attachTo: document.body,
    })
    expect(document.querySelector('[role="dialog"]')).toBeNull()

    await wrapper.setProps({ open: true })
    await nextTick()
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement
    expect(dialog).not.toBeNull()
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(dialog.textContent).toContain('Kirim')
    expect(document.querySelector('.body-slot')).not.toBeNull()
    wrapper.unmount()
  })

  it('emits close on Escape and on the close button', async () => {
    const wrapper = mount(AppModal, {
      props: { open: true, title: 'Tuzatish' },
      attachTo: document.body,
    })
    await nextTick()
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement
    dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(wrapper.emitted('close')).toHaveLength(1)

    const closeButton = dialog.querySelector('button[aria-label="Yopish"]') as HTMLButtonElement
    closeButton.click()
    expect(wrapper.emitted('close')).toHaveLength(2)
    wrapper.unmount()
  })
})
