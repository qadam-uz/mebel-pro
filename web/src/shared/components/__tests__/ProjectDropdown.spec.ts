import { DOMWrapper, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import type { DropdownOption } from '@/shared/app/roleConfig'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'

const options: DropdownOption[] = [
  { value: 'a', label: 'A branch', meta: 'open', status: 'active' },
  { value: 'b', label: 'B branch', meta: 'pending', status: 'pending' },
]

describe('ProjectDropdown', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('selects an option with keyboard and returns focus to the button', async () => {
    const wrapper = mount(ProjectDropdown, {
      props: {
        label: 'Branch',
        modelValue: 'a',
        options,
      },
      attachTo: document.body,
    })
    const button = wrapper.get('button')

    await button.trigger('keydown', { key: 'ArrowDown' })
    await nextTick()
    const listbox = document.querySelector('[role="listbox"]')
    expect(listbox).not.toBeNull()
    expect(listbox?.getAttribute('aria-activedescendant')).toContain('-b')
    expect(document.activeElement).toBe(listbox)

    await new DOMWrapper(listbox as HTMLUListElement).trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['b'])
    expect(document.activeElement).toBe(button.element)
    wrapper.unmount()
  })
})
