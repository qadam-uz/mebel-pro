import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FilePicker from '@/shared/components/FilePicker.vue'

describe('FilePicker', () => {
  it('shows the Uzbek placeholder and button label by default', () => {
    const wrapper = mount(FilePicker)
    expect(wrapper.text()).toContain('Fayl tanlanmagan')
    expect(wrapper.get('button').text()).toBe('Fayl tanlang')
    // The native input is present but visually hidden (sr-only).
    const input = wrapper.get('input[type="file"]')
    expect(input.classes()).toContain('sr-only')
  })

  it('re-emits the native change event and shows the picked file name', async () => {
    const wrapper = mount(FilePicker)
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['x'], 'chek.pdf', { type: 'application/pdf' })],
      configurable: true,
    })

    await input.trigger('change')

    const events = wrapper.emitted('change')
    expect(events).toHaveLength(1)
    expect(events?.[0][0]).toBeInstanceOf(Event)
    expect(wrapper.text()).toContain('chek.pdf')
    expect(wrapper.text()).not.toContain('Fayl tanlanmagan')
  })

  it('forwards accept and disabled to the input and button', () => {
    const wrapper = mount(FilePicker, {
      props: { accept: 'application/pdf', disabled: true, buttonLabel: 'Yuklash' },
    })
    expect(wrapper.get('input[type="file"]').attributes('accept')).toBe('application/pdf')
    expect(wrapper.get('input[type="file"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button').text()).toBe('Yuklash')
  })

  it('shows a busy state and disables the input while uploading', () => {
    const wrapper = mount(FilePicker, { props: { uploading: true } })
    expect(wrapper.text()).toContain('Yuklanmoqda')
    expect(wrapper.get('input[type="file"]').attributes('disabled')).toBeDefined()
  })

  it('shows the parent-controlled name over the locally picked one', () => {
    const wrapper = mount(FilePicker, { props: { selectedName: 'Biriktirilgan chek' } })
    expect(wrapper.text()).toContain('Biriktirilgan chek')
    expect(wrapper.text()).not.toContain('Fayl tanlanmagan')
  })

  it('emits remove and clears the local name when the remove action is used', async () => {
    const wrapper = mount(FilePicker, { props: { removable: true } })
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['x'], 'chek.pdf', { type: 'application/pdf' })],
      configurable: true,
    })
    await input.trigger('change')
    const removeButton = wrapper.get('button[aria-label="Faylni olib tashlash"]')
    await removeButton.trigger('click')
    expect(wrapper.emitted('remove')).toHaveLength(1)
    expect(wrapper.text()).toContain('Fayl tanlanmagan')
  })
})
