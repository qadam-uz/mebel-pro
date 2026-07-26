import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import SegmentedControl from '@/shared/components/SegmentedControl.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'

const methods: ChoiceOption[] = [
  { value: 'cash', label: 'Naqd' },
  { value: 'bank_transfer', label: 'Bank / karta' },
  { value: 'other', label: 'Boshqa' },
]

function mountControl(modelValue: string | null = 'cash') {
  return mount(SegmentedControl, {
    props: { label: 'Usul', modelValue, options: methods },
    attachTo: document.body,
  })
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('SegmentedControl', () => {
  it('exposes a radiogroup with the selected segment checked', () => {
    const wrapper = mountControl('bank_transfer')
    const group = wrapper.get('[role="radiogroup"]')
    const segments = wrapper.findAll('[role="radio"]')

    expect(group.attributes('aria-labelledby')).toBeTruthy()
    expect(segments.map((segment) => segment.attributes('aria-checked'))).toEqual([
      'false',
      'true',
      'false',
    ])
  })

  it('is one tab stop: only the selected segment is reachable by Tab', () => {
    const wrapper = mountControl('other')

    expect(wrapper.findAll('[role="radio"]').map((s) => s.attributes('tabindex'))).toEqual([
      '-1',
      '-1',
      '0',
    ])
  })

  it('keeps the group reachable when nothing is selected yet', () => {
    const wrapper = mountControl(null)

    expect(wrapper.findAll('[role="radio"]')[0].attributes('tabindex')).toBe('0')
  })

  it('moves the selection with the arrow keys and wraps at the ends', async () => {
    const wrapper = mountControl('cash')

    await wrapper.get('[role="radiogroup"]').trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['bank_transfer'])

    await wrapper.get('[role="radiogroup"]').trigger('keydown', { key: 'ArrowLeft' })
    // Still on `cash` (the prop is controlled), so ArrowLeft wraps to the end.
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual(['other'])

    await wrapper.get('[role="radiogroup"]').trigger('keydown', { key: 'End' })
    expect(wrapper.emitted('update:modelValue')?.[2]).toEqual(['other'])
  })

  it('moves focus with the selection so the keyboard never lands nowhere', async () => {
    const wrapper = mountControl('cash')

    await wrapper.get('[role="radiogroup"]').trigger('keydown', { key: 'ArrowRight' })
    await nextTick()

    expect(document.activeElement?.textContent?.trim()).toBe('Bank / karta')
  })

  it('emits nothing while disabled', async () => {
    const wrapper = mount(SegmentedControl, {
      props: { label: 'Usul', modelValue: 'cash', options: methods, disabled: true },
      attachTo: document.body,
    })

    await wrapper.get('[role="radiogroup"]').trigger('keydown', { key: 'ArrowRight' })

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
