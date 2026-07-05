import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import { presetRange } from '@/shared/app/dateRange'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'

function mountPicker(props: Record<string, unknown> = {}) {
  return mount(DateRangePicker, {
    props: { preset: 'all', dateFrom: '', dateTo: '', ...props },
    attachTo: document.body,
  })
}

function panel(): HTMLElement | null {
  return document.querySelector('[role="dialog"]')
}

describe('DateRangePicker', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('labels the trigger with the preset name, or the dates for a custom range', () => {
    const monthly = mountPicker({ preset: 'month', dateFrom: '2026-07-01', dateTo: '2026-07-04' })
    expect(monthly.get('button').text()).toContain('Joriy oy')
    monthly.unmount()

    const custom = mountPicker({ preset: 'custom', dateFrom: '2026-06-05', dateTo: '2026-07-04' })
    expect(custom.get('button').text()).toContain('05.06.2026 – 04.07.2026')
    custom.unmount()
  })

  it('emits the preset on shortcut click and closes the popover', async () => {
    const wrapper = mountPicker()
    await wrapper.get('button').trigger('click')
    await nextTick()
    expect(panel()).not.toBeNull()

    const shortcut = Array.from(panel()!.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === 'Bugun',
    )
    expect(shortcut).toBeDefined()
    shortcut!.click()
    await nextTick()

    expect(wrapper.emitted('update:preset')?.[0]).toEqual(['today'])
    expect(panel()).toBeNull()
    wrapper.unmount()
  })

  it('re-derives from/to when the preset changes programmatically (Tozalash contract)', async () => {
    const seeded = presetRange('month')
    const wrapper = mountPicker({
      preset: 'month',
      dateFrom: seeded.from ?? '',
      dateTo: seeded.to ?? '',
    })
    expect(wrapper.emitted('update:dateFrom')).toBeUndefined()

    await wrapper.setProps({ preset: 'all' })
    expect(wrapper.emitted('update:dateFrom')?.at(-1)).toEqual([''])
    expect(wrapper.emitted('update:dateTo')?.at(-1)).toEqual([''])

    await wrapper.setProps({ preset: 'custom' })
    expect(wrapper.emitted('update:dateFrom')).toHaveLength(1)
    wrapper.unmount()
  })

  it('completes a calendar selection into a custom range and closes', async () => {
    const wrapper = mountPicker({ preset: 'month', dateFrom: '2026-07-01', dateTo: '2026-07-04' })
    await wrapper.get('button').trigger('click')
    await nextTick()

    panel()!.querySelector<HTMLButtonElement>('[data-day="2026-07-10"]')!.click()
    await nextTick()
    expect(panel()).not.toBeNull()
    panel()!.querySelector<HTMLButtonElement>('[data-day="2026-07-14"]')!.click()
    await nextTick()

    expect(wrapper.emitted('update:preset')?.at(-1)).toEqual(['custom'])
    expect(wrapper.emitted('update:dateFrom')?.at(-1)).toEqual(['2026-07-10'])
    expect(wrapper.emitted('update:dateTo')?.at(-1)).toEqual(['2026-07-14'])
    expect(panel()).toBeNull()
    wrapper.unmount()
  })

  it('restarts the draft when a day before the anchor is clicked', async () => {
    const wrapper = mountPicker({ preset: 'month', dateFrom: '2026-07-01', dateTo: '2026-07-04' })
    await wrapper.get('button').trigger('click')
    await nextTick()

    panel()!.querySelector<HTMLButtonElement>('[data-day="2026-07-14"]')!.click()
    await nextTick()
    panel()!.querySelector<HTMLButtonElement>('[data-day="2026-07-10"]')!.click()
    await nextTick()
    // Earlier click re-anchored instead of completing a reversed range.
    expect(wrapper.emitted('update:preset')).toBeUndefined()
    panel()!.querySelector<HTMLButtonElement>('[data-day="2026-07-12"]')!.click()
    await nextTick()

    expect(wrapper.emitted('update:dateFrom')?.at(-1)).toEqual(['2026-07-10'])
    expect(wrapper.emitted('update:dateTo')?.at(-1)).toEqual(['2026-07-12'])
    wrapper.unmount()
  })

  it('keeps a tabbable day cell when the range start is outside the visible month', async () => {
    // One-month view (jsdom has no matchMedia) anchored on dateTo: the June
    // start is off-screen, so the roving tab stop must fall back to dateTo.
    const wrapper = mountPicker({ preset: 'custom', dateFrom: '2026-06-05', dateTo: '2026-07-04' })
    await wrapper.get('button').trigger('click')
    await nextTick()

    const tabbable = panel()!.querySelector('[data-day][tabindex="0"]')
    expect(tabbable?.getAttribute('data-day')).toBe('2026-07-04')
    wrapper.unmount()
  })

  it('closes on Escape without letting the key bubble (two-stage close)', async () => {
    const wrapper = mountPicker()
    const button = wrapper.get('button')
    await button.trigger('click')
    await nextTick()

    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    const stop = vi.spyOn(event, 'stopPropagation')
    panel()!.dispatchEvent(event)
    await nextTick()

    expect(stop).toHaveBeenCalled()
    expect(panel()).toBeNull()
    expect(document.activeElement).toBe(button.element)
    wrapper.unmount()
  })
})
