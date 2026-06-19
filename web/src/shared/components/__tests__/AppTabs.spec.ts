import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import AppTabs from '@/shared/components/AppTabs.vue'

const tabs = [
  { value: 'one', label: 'One' },
  { value: 'two', label: 'Two' },
  { value: 'three', label: 'Three' },
]

describe('AppTabs', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders tab semantics and roves focus with arrow keys', async () => {
    const wrapper = mount(AppTabs, {
      props: {
        modelValue: 'one',
        tabs,
        idPrefix: 'test-tabs',
        label: 'Test tabs',
      },
      attachTo: document.body,
    })

    const buttons = wrapper.findAll('[role="tab"]')
    expect(wrapper.get('[role="tablist"]').attributes('aria-label')).toBe('Test tabs')
    expect(buttons[0].attributes('aria-selected')).toBe('true')
    expect(buttons[1].attributes('tabindex')).toBe('-1')
    expect(buttons[0].attributes('aria-controls')).toBe('test-tabs-one-panel')

    await buttons[0].trigger('keydown', { key: 'ArrowRight' })
    await nextTick()

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['two'])
    expect(document.activeElement).toBe(buttons[1].element)
  })

  it('skips disabled tabs during keyboard navigation', async () => {
    const wrapper = mount(AppTabs, {
      props: {
        modelValue: 'one',
        tabs: [
          { value: 'one', label: 'One' },
          { value: 'two', label: 'Two', disabled: true },
          { value: 'three', label: 'Three' },
        ],
        idPrefix: 'skip-tabs',
        label: 'Skip tabs',
      },
      attachTo: document.body,
    })

    await wrapper.get('[role="tab"]').trigger('keydown', { key: 'ArrowRight' })
    await nextTick()

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['three'])
  })
})
