import { DOMWrapper, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import MultiSelectFilter from '@/shared/components/MultiSelectFilter.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'

const options = [
  { value: 'panel', label: 'Panel', meta: 'sheet materials' },
  { value: 'edge', label: 'Edge', meta: 'edge banding' },
  { value: 'disabled', label: 'Disabled', disabled: true },
]

describe('Phase 3 shared controls', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('FormSelect opens, skips disabled options, selects with keyboard, and returns focus', async () => {
    const wrapper = mount(FormSelect, {
      props: {
        label: 'Material kind',
        modelValue: 'panel',
        options,
      },
      attachTo: document.body,
    })

    const button = wrapper.get('button')
    await button.trigger('keydown', { key: 'ArrowDown' })
    await nextTick()

    const listbox = wrapper.get('[role="listbox"]')
    expect(document.activeElement).toBe(listbox.element)
    expect(listbox.attributes('aria-activedescendant')).toContain('edge')

    await listbox.trigger('keydown', { key: 'ArrowDown' })
    expect(listbox.attributes('aria-activedescendant')).toContain('panel')

    await listbox.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['panel'])
    expect(document.activeElement).toBe(button.element)
  })

  it('FormSelect associates validation text with the trigger', () => {
    const wrapper = mount(FormSelect, {
      props: {
        label: 'Status',
        modelValue: null,
        options,
        error: 'Choose a status',
      },
      attachTo: document.body,
    })

    const button = wrapper.get('button')
    const error = wrapper.get('p')
    expect(button.attributes('aria-describedby')).toBe(error.attributes('id'))
  })

  it('FormSelect exposes required state in text and ARIA', () => {
    const wrapper = mount(FormSelect, {
      props: {
        label: 'Manufacturer',
        modelValue: null,
        options,
        required: true,
      },
      attachTo: document.body,
    })

    expect(wrapper.text()).toContain('*')
    expect(wrapper.get('button').attributes('role')).toBe('combobox')
    expect(wrapper.get('button').attributes('aria-required')).toBe('true')
  })

  it('ConfirmDialog focuses cancel, closes with Escape, and emits confirm', async () => {
    const wrapper = mount(ConfirmDialog, {
      props: {
        open: true,
        title: 'Delete draft',
        message: 'This cannot be undone.',
        confirmLabel: 'Delete draft',
        danger: true,
      },
      attachTo: document.body,
    })
    await nextTick()

    const dialog = new DOMWrapper(document.body.querySelector('[role="dialog"]') as HTMLElement)
    const buttons = Array.from(document.body.querySelectorAll('button'))
    expect(document.activeElement).toBe(buttons[0])

    await dialog.trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('cancel')).toHaveLength(1)

    await new DOMWrapper(buttons[1] as HTMLButtonElement).trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('SearchCombobox filters by typed text and picks with Enter', async () => {
    const wrapper = mount(SearchCombobox, {
      global: { stubs: { teleport: true } },
      props: {
        label: 'Material',
        modelValue: null,
        options,
      },
      attachTo: document.body,
    })

    const input = wrapper.get('input')
    await input.setValue('edge band')
    await nextTick()
    expect(wrapper.findAll('[role="option"]')).toHaveLength(1)

    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['edge'])
    expect(document.activeElement).toBe(input.element)
  })

  it('SearchCombobox closes on outside click and restores selected label', async () => {
    const wrapper = mount(SearchCombobox, {
      global: { stubs: { teleport: true } },
      props: {
        label: 'Material',
        modelValue: 'edge',
        options,
      },
      attachTo: document.body,
    })

    const input = wrapper.get('input')
    await input.setValue('unknown')
    document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    await nextTick()

    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    expect((input.element as HTMLInputElement).value).toBe('Edge')
  })

  it('MultiSelectFilter toggles selections with keyboard and keeps the list open', async () => {
    const wrapper = mount(MultiSelectFilter, {
      props: {
        label: 'Kinds',
        modelValue: [],
        options,
      },
      attachTo: document.body,
    })

    await wrapper.get('button').trigger('keydown', { key: 'Enter' })
    await nextTick()
    const listbox = wrapper.get('[role="listbox"]')
    await listbox.trigger('keydown', { key: ' ' })

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['panel']])
    expect(wrapper.find('[role="listbox"]').exists()).toBe(true)
  })

  it('MultiSelectFilter closes on Escape and returns focus', async () => {
    const wrapper = mount(MultiSelectFilter, {
      props: {
        label: 'Kinds',
        modelValue: ['panel'],
        options,
      },
      attachTo: document.body,
    })

    const button = wrapper.get('button')
    await button.trigger('click')
    const listbox = new DOMWrapper(wrapper.get('[role="listbox"]').element as HTMLUListElement)
    await listbox.trigger('keydown', { key: 'Escape' })

    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    expect(document.activeElement).toBe(button.element)
  })

  it('MultiSelectFilter exposes required and error state on the trigger', () => {
    const wrapper = mount(MultiSelectFilter, {
      props: {
        label: 'Branches',
        modelValue: [],
        options,
        required: true,
        error: 'Choose a branch',
      },
      attachTo: document.body,
    })

    const button = wrapper.get('button')
    const error = wrapper.get('p')
    expect(wrapper.text()).toContain('*')
    expect(button.attributes('aria-required')).toBe('true')
    expect(button.attributes('aria-invalid')).toBe('true')
    expect(button.attributes('aria-describedby')).toBe(error.attributes('id'))
  })
})
