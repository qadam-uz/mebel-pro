import { DOMWrapper, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import type { DropdownOption } from '@/shared/app/roleConfig'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'

const options: DropdownOption[] = [
  { value: 'a', label: 'A branch', meta: 'open', status: 'active' },
  { value: 'b', label: 'B branch', meta: 'pending', status: 'pending' },
]

describe('ProjectDropdown', () => {
  afterEach(() => {
    vi.restoreAllMocks()
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

  it('positions the fixed popover in viewport coordinates and clamps screen edges', async () => {
    vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(360)
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(640)
    vi.spyOn(window, 'scrollX', 'get').mockReturnValue(400)
    vi.spyOn(window, 'scrollY', 'get').mockReturnValue(500)
    const wrapper = mount(ProjectDropdown, {
      props: {
        label: 'Branch',
        modelValue: 'a',
        options,
      },
      attachTo: document.body,
    })
    const button = wrapper.get('button')
    vi.spyOn(button.element, 'getBoundingClientRect').mockReturnValue({
      x: 310,
      y: 20,
      width: 80,
      height: 44,
      top: 20,
      right: 390,
      bottom: 64,
      left: 310,
      toJSON: () => ({}),
    } as DOMRect)

    await button.trigger('click')
    await nextTick()

    const listbox = document.querySelector('[role="listbox"]') as HTMLUListElement
    expect(listbox).not.toBeNull()
    expect(parseFloat(listbox.style.left)).toBeLessThanOrEqual(92)
    expect(parseFloat(listbox.style.top)).toBe(70)
    expect(listbox.style.width).toBe('260px')
    wrapper.unmount()
  })
})
