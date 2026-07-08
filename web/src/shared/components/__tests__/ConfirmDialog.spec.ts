import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'

const baseProps = {
  open: true,
  title: 'Yozuvni bekor qilish',
  message: 'Sababni yozing.',
  confirmLabel: 'Bekor qilish',
  cancelLabel: 'Orqaga',
}

describe('ConfirmDialog', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('includes slot fields in the focus trap and focuses the first one on open', async () => {
    // Regression: a buttons-only trap made a reason input keyboard-unreachable —
    // Shift+Tab from Cancel wrapped to Confirm, skipping the field entirely.
    const wrapper = mount(ConfirmDialog, {
      props: baseProps,
      slots: { default: '<input class="reason" aria-label="Sabab" />' },
      attachTo: document.body,
    })
    await nextTick()
    const input = document.querySelector('input.reason') as HTMLInputElement
    expect(document.activeElement).toBe(input)

    const buttons = Array.from(document.querySelectorAll('[role="dialog"] button'))
    const cancel = buttons[0] as HTMLButtonElement
    cancel.focus()
    cancel.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }),
    )
    // Shift+Tab from the first BUTTON must not wrap — the input precedes it, so
    // the trap only wraps at the true first focusable (the input itself).
    expect(document.activeElement).toBe(cancel)
    input.focus()
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }))
    const confirm = buttons[buttons.length - 1] as HTMLButtonElement
    expect(document.activeElement).toBe(confirm)
    wrapper.unmount()
  })

  it('confirms on Enter in a slot input unless disabled', async () => {
    const wrapper = mount(ConfirmDialog, {
      props: { ...baseProps, confirmDisabled: true },
      slots: { default: '<input class="reason" aria-label="Sabab" />' },
      attachTo: document.body,
    })
    await nextTick()
    const input = document.querySelector('input.reason') as HTMLInputElement
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    expect(wrapper.emitted('confirm')).toBeUndefined()

    await wrapper.setProps({ confirmDisabled: false })
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    expect(wrapper.emitted('confirm')).toHaveLength(1)
    wrapper.unmount()
  })

  it('falls back to focusing Cancel when there is no slot content', async () => {
    const wrapper = mount(ConfirmDialog, { props: baseProps, attachTo: document.body })
    await nextTick()
    const cancel = document.querySelector('[role="dialog"] button') as HTMLButtonElement
    expect(document.activeElement).toBe(cancel)
    expect(cancel.textContent).toContain('Orqaga')
    wrapper.unmount()
  })
})
