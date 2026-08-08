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

  it('renders an external caption in top-label mode', () => {
    const wrapper = mount(ProjectDropdown, {
      props: { label: 'Holat', modelValue: 'a', options, topLabel: true },
    })
    const caption = wrapper.get('.mp-filter-dd-label')
    expect(caption.text()).toBe('Holat')
    expect(caption.attributes('aria-hidden')).toBe('true')
    // The in-trigger eyebrow duplicate is hidden from sight for AT-only use.
    expect(wrapper.get('button .sr-only').text()).toBe('Holat')
  })

  it('compact filter skin drops the icon tile, meta text, and status dots', async () => {
    const wrapper = mount(ProjectDropdown, {
      props: { label: 'Tur', modelValue: 'a', options, topLabel: true },
      attachTo: document.body,
    })
    const button = wrapper.get('button')
    // No rich-skin icon tile or secondary meta line on the trigger.
    expect(button.find('.mp-dot').exists()).toBe(false)
    expect(button.text()).not.toContain('open')

    await button.trigger('click')
    await nextTick()
    const listbox = document.querySelector('[role="listbox"]') as HTMLUListElement
    // Option rows show only labels: no meta, no status-derived dots.
    expect(listbox.textContent).toContain('A branch')
    expect(listbox.textContent).not.toContain('open')
    expect(listbox.querySelectorAll('.bg-success, .bg-warning, .bg-ink-muted')).toHaveLength(0)
    wrapper.unmount()
  })

  it('compact skin renders colored dots only when options declare them', async () => {
    const statusOptions: DropdownOption[] = [
      { value: 'all', label: 'Hammasi' },
      { value: 'active', label: 'Faol', dot: 'success' },
      { value: 'cancelled', label: 'Bekor qilingan', dot: 'danger' },
    ]
    const wrapper = mount(ProjectDropdown, {
      props: { label: 'Holat', modelValue: 'active', options: statusOptions, topLabel: true },
      attachTo: document.body,
    })
    const button = wrapper.get('button')
    // The trigger mirrors the selected option's dot.
    expect(button.find('.bg-success').exists()).toBe(true)

    await button.trigger('click')
    await nextTick()
    const listbox = document.querySelector('[role="listbox"]') as HTMLUListElement
    expect(listbox.querySelectorAll('.bg-success')).toHaveLength(1)
    expect(listbox.querySelectorAll('.bg-danger')).toHaveLength(1)
    // Dot-less options keep an invisible placeholder so labels align.
    expect(listbox.querySelectorAll('.bg-transparent')).toHaveLength(1)
    wrapper.unmount()
  })

  // QAD-148: the workshop topbar keeps the branch picker visible on pages the
  // branch context doesn't reach, but it must be inert and say why — an enabled
  // picker that silently does nothing is the bug this replaced.
  it('disabled: refuses to open by click or keyboard and exposes the hint', async () => {
    const wrapper = mount(ProjectDropdown, {
      props: {
        label: 'Branch',
        modelValue: 'a',
        options,
        disabled: true,
        hint: "Bu sahifa butun ustaxona bo'yicha",
      },
      attachTo: document.body,
    })
    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()

    await button.trigger('click')
    await button.trigger('keydown', { key: 'ArrowDown' })
    await nextTick()
    expect(document.querySelector('[role="listbox"]')).toBeNull()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    const hint = wrapper.get('.mp-dd-hint')
    expect(hint.text()).toBe("Bu sahifa butun ustaxona bo'yicha")
    expect(button.attributes('aria-describedby')).toBe(hint.attributes('id'))
    // The selection still reads as the current context — it's inert, not blank.
    expect(button.text()).toContain('A branch')
    wrapper.unmount()
  })

  // The sidebar branch card wears its own two-line skin. What must NOT come with
  // it is a second copy of the listbox, so the slot swaps the trigger's contents
  // while every behaviour stays in the primitive.
  it('host-skinned trigger: slot content replaces the default, keyboard still selects', async () => {
    const wrapper = mount(ProjectDropdown, {
      props: {
        label: 'Filial',
        modelValue: 'a',
        options,
        triggerClass: 'workshop-branch',
        hintClass: 'workshop-branch-hint',
        hint: "Bu sahifa butun ustaxona bo'yicha",
      },
      slots: {
        trigger: `<template #trigger="{ selected, open }">
          <span class="branch-name">Oq Daraxt</span>
          <span class="branch-meta">{{ selected.label }}</span>
          <span class="branch-open">{{ open ? 'on' : 'off' }}</span>
        </template>`,
      },
      attachTo: document.body,
    })
    const button = wrapper.get('button')

    // The host's classes replace the baked ones outright.
    expect(button.classes()).toContain('workshop-branch')
    expect(button.classes()).not.toContain('mp-surface')
    // Default trigger markup is gone; the slot's is what renders.
    expect(button.find('.mp-dot').exists()).toBe(false)
    expect(button.get('.branch-meta').text()).toBe('A branch')
    expect(button.get('.branch-open').text()).toBe('off')
    // The hint follows the host too, and stays wired to the trigger.
    const hint = wrapper.get('.workshop-branch-hint')
    expect(button.attributes('aria-describedby')).toBe(hint.attributes('id'))

    await button.trigger('keydown', { key: 'ArrowDown' })
    await nextTick()
    expect(button.get('.branch-open').text()).toBe('on')
    const listbox = document.querySelector('[role="listbox"]') as HTMLUListElement
    await new DOMWrapper(listbox).trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['b'])
    expect(document.activeElement).toBe(button.element)
    wrapper.unmount()
  })

  // A 260px floor is right for the primitive's own narrow trigger and wrong for a
  // 232px sidebar card: the panel would hang over the column it belongs to.
  it('host-skinned trigger: the panel matches the trigger instead of the 260px floor', async () => {
    vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(1440)
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(900)
    const wrapper = mount(ProjectDropdown, {
      props: { label: 'Filial', modelValue: 'a', options, triggerClass: 'workshop-branch' },
      slots: { trigger: '<span>Oq Daraxt</span>' },
      attachTo: document.body,
    })
    const button = wrapper.get('button')
    vi.spyOn(button.element, 'getBoundingClientRect').mockReturnValue({
      x: 16,
      y: 96,
      width: 232,
      height: 52,
      top: 96,
      right: 248,
      bottom: 148,
      left: 16,
      toJSON: () => ({}),
    } as DOMRect)

    await button.trigger('click')
    await nextTick()

    const listbox = document.querySelector('[role="listbox"]') as HTMLUListElement
    expect(listbox.style.width).toBe('232px')
    wrapper.unmount()
  })

  // The panel no longer widens past a host-skinned trigger, so the option rows are
  // the narrowest they have ever been and truncation is load-bearing. `truncate`
  // alone does nothing inside a grid column whose automatic minimum size is its
  // content — without `min-w-0` a long branch name scrolls the panel sideways.
  it('rich-skin option rows can actually shrink: min-w-0 on the text column', async () => {
    const wrapper = mount(ProjectDropdown, {
      props: {
        label: 'Filial',
        modelValue: 'a',
        options: [
          {
            value: 'a',
            label: 'Sergeli ishlab chiqarish sexi',
            meta: "Sergeli tumani, Yangi Sergeli ko'chasi 42",
            status: 'active',
          },
        ],
        triggerClass: 'workshop-branch',
      },
      slots: { trigger: '<span>Oq Daraxt</span>' },
      attachTo: document.body,
    })
    await wrapper.get('button').trigger('click')
    await nextTick()

    const row = document.querySelector('[role="option"]') as HTMLLIElement
    const text = row.children[1] as HTMLSpanElement
    expect(text.className).toContain('min-w-0')
    expect((text.children[0] as HTMLElement).className).toContain('truncate')
    expect((text.children[1] as HTMLElement).className).toContain('truncate')
    wrapper.unmount()
  })

  it('stops Escape from bubbling out of an open listbox (two-stage close)', async () => {
    const wrapper = mount(ProjectDropdown, {
      props: { label: 'Branch', modelValue: 'a', options },
      attachTo: document.body,
    })
    const button = wrapper.get('button')
    await button.trigger('click')
    await nextTick()

    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    const stop = vi.spyOn(event, 'stopPropagation')
    button.element.dispatchEvent(event)
    await nextTick()
    expect(stop).toHaveBeenCalled()
    expect(document.querySelector('[role="listbox"]')).toBeNull()
    wrapper.unmount()
  })
})
