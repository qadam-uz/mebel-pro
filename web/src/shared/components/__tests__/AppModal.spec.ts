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

  it('scrolls the body only — the head and the footer are fixed chrome', async () => {
    // A modal that scrolls as one block takes its own buttons off screen the
    // moment its content is long (owner review, 2026-09-08). So the panel is a
    // column and exactly ONE of its regions is a scroller.
    const wrapper = mount(AppModal, {
      props: { open: true, title: 'Dekor tanlash' },
      slots: {
        head: '<div class="head-slot">filtrlar</div>',
        default: '<p class="body-slot">ro‘yxat</p>',
        footer: '<button class="footer-slot">Bekor</button>',
      },
      attachTo: document.body,
    })
    await nextTick()
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement
    const scrollers = dialog.querySelectorAll('.overflow-y-auto')
    expect(scrollers).toHaveLength(1)

    const scroller = scrollers[0]
    expect(scroller.querySelector('.body-slot')).not.toBeNull()
    // Both extra regions live OUTSIDE the scroller, so neither can move.
    expect(scroller.querySelector('.head-slot')).toBeNull()
    expect(scroller.querySelector('.footer-slot')).toBeNull()
    expect(dialog.querySelector('.head-slot')).not.toBeNull()
    expect(dialog.querySelector('.footer-slot')).not.toBeNull()
    // Reachable from the keyboard without being a tab stop of its own.
    expect(scroller.getAttribute('tabindex')).toBe('-1')
    wrapper.unmount()
  })

  it('renders no head or footer region for a modal that fills neither', async () => {
    const wrapper = mount(AppModal, {
      props: { open: true, title: 'Tuzatish' },
      slots: { default: '<p class="body-slot">forma</p>' },
      attachTo: document.body,
    })
    await nextTick()
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement
    // header + scroller, and nothing else: every modal that predates the head /
    // footer slots keeps exactly the frame it had.
    expect(dialog.children).toHaveLength(2)
    wrapper.unmount()
  })
})
