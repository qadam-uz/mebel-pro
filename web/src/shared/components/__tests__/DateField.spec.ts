import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import DateField from '@/shared/components/DateField.vue'

// Mounted with a live v-model: the component only emits on a real change, so
// the parent has to feed the new value back for the next edit to be observable.
function mountField(props: Record<string, unknown> = {}) {
  const wrapper = mount(DateField, {
    props: {
      modelValue: '',
      ...props,
      'onUpdate:modelValue': (value: string) => wrapper.setProps({ modelValue: value }),
    },
    attachTo: document.body,
  })
  return wrapper
}

function panel(): HTMLElement | null {
  return document.querySelector('[role="dialog"]')
}

describe('DateField', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('shows the ISO value as dd.mm.yyyy regardless of browser locale', () => {
    const wrapper = mountField({ modelValue: '2026-01-12' })
    expect(wrapper.get('input').element.value).toBe('12.01.2026')
    wrapper.unmount()
  })

  it('masks typed digits into dd.mm.yyyy and emits ISO', async () => {
    const wrapper = mountField()
    const input = wrapper.get('input')

    await input.setValue('19')
    expect(input.element.value).toBe('19.')
    await input.setValue('19.07')
    expect(input.element.value).toBe('19.07.')
    await input.setValue('19.07.2026')

    expect(input.element.value).toBe('19.07.2026')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['2026-07-19'])
    wrapper.unmount()
  })

  it('rejects a day that does not exist in that month', async () => {
    const wrapper = mountField()
    const input = wrapper.get('input')
    await input.setValue('28.02.2026')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['2026-02-28'])

    await input.setValue('31.02.2026')
    // The impossible day clears the value rather than silently rounding it.
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([''])
    expect(wrapper.text()).toContain("kk.oo.yyyy ko'rinishida")
    wrapper.unmount()
  })

  it('refuses a date past max and blocks native submit with it', async () => {
    const wrapper = mountField({ modelValue: '2026-07-01', max: '2026-07-20' })
    const input = wrapper.get('input')
    await input.setValue('25.07.2026')

    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([''])
    // The cleared model echoing back must not wipe what the user typed.
    expect(input.element.value).toBe('25.07.2026')
    await nextTick()
    expect(input.element.validationMessage).not.toBe('')

    await input.setValue('20.07.2026')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['2026-07-20'])
    await nextTick()
    expect(input.element.validationMessage).toBe('')
    wrapper.unmount()
  })

  it('does not offer days past max in the calendar', async () => {
    const wrapper = mountField({ modelValue: '2026-07-19', max: '2026-07-20' })
    await wrapper.get('button').trigger('click')
    await nextTick()

    const future = panel()!.querySelector<HTMLButtonElement>('[data-day="2026-07-21"]')!
    expect(future.getAttribute('aria-disabled')).toBe('true')
    future.click()
    await nextTick()

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(panel()).not.toBeNull()
    wrapper.unmount()
  })

  it('emits ISO and closes when a calendar day is picked', async () => {
    const wrapper = mountField({ modelValue: '2026-07-19' })
    await wrapper.get('button').trigger('click')
    await nextTick()

    panel()!.querySelector<HTMLButtonElement>('[data-day="2026-07-03"]')!.click()
    await nextTick()

    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['2026-07-03'])
    expect(panel()).toBeNull()
    expect(document.activeElement).toBe(wrapper.get('input').element)
    wrapper.unmount()
  })

  it('closes on Escape without letting the key bubble to the host modal', async () => {
    const wrapper = mountField({ modelValue: '2026-07-19' })
    await wrapper.get('button').trigger('click')
    await nextTick()

    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    const stop = vi.spyOn(event, 'stopPropagation')
    panel()!.dispatchEvent(event)
    await nextTick()

    expect(stop).toHaveBeenCalled()
    expect(panel()).toBeNull()
    expect(document.activeElement).toBe(wrapper.get('input').element)
    wrapper.unmount()
  })
})
