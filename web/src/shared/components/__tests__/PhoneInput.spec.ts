import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PhoneInput from '@/shared/components/PhoneInput.vue'

/** Type `raw` into the field and return the value emitted via update:modelValue. */
async function typeAndEmit(raw: string) {
  const wrapper = mount(PhoneInput, { props: { modelValue: '' } })
  const input = wrapper.get('input')
  input.element.value = raw
  await input.trigger('input')
  const events = wrapper.emitted('update:modelValue')
  return { wrapper, input, emitted: events?.at(-1)?.[0] as string | undefined }
}

describe('PhoneInput', () => {
  it('renders a fixed +998 prefix and groups the national digits', async () => {
    const { wrapper, input } = await typeAndEmit('901234567')
    expect(wrapper.text()).toContain('+998')
    // The prefix is an adornment, not part of the editable value.
    expect(input.element.value).toBe('90 123 45 67')
  })

  it('emits the normalized +998XXXXXXXXX on input', async () => {
    const { emitted } = await typeAndEmit('901234567')
    expect(emitted).toBe('+998901234567')
  })

  it('hard-caps entry at 9 national digits', async () => {
    const { input, emitted } = await typeAndEmit('9012345678999')
    expect(input.element.value).toBe('90 123 45 67')
    expect(emitted).toBe('+998901234567')
  })

  it('strips non-digits as they are typed', async () => {
    const { input } = await typeAndEmit('90abc12-34')
    expect(input.element.value).toBe('90 123 4')
  })

  it.each([
    ['+998 90 123-45-67', '+998901234567'],
    ['998901234567', '+998901234567'],
    ['0901234567', '+998901234567'],
    ['8 998 90 123 45 67', '+998901234567'],
    ['901234567', '+998901234567'],
  ])('normalizes pasted %s to %s', async (paste, expected) => {
    const { emitted } = await typeAndEmit(paste)
    expect(emitted).toBe(expected)
  })

  it('emits empty string when cleared (optional fields stay empty)', async () => {
    const { emitted } = await typeAndEmit('')
    expect(emitted).toBe('')
  })

  it('renders an existing model value grouped, prefix stripped', () => {
    const wrapper = mount(PhoneInput, { props: { modelValue: '+998907654321' } })
    expect(wrapper.get('input').element.value).toBe('90 765 43 21')
  })

  it('forwards id, required and passthrough attrs to the inner input', () => {
    const wrapper = mount(PhoneInput, {
      props: { modelValue: '', id: 'staff-phone', required: true },
      attrs: { 'aria-invalid': 'true', 'aria-describedby': 'staff-phone-error' },
    })
    const input = wrapper.get('input')
    expect(input.attributes('id')).toBe('staff-phone')
    expect(input.attributes('required')).toBeDefined()
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(input.attributes('aria-describedby')).toBe('staff-phone-error')
  })

  it('disables the inner input and marks the wrapper', () => {
    const wrapper = mount(PhoneInput, { props: { modelValue: '', disabled: true } })
    expect(wrapper.get('input').attributes('disabled')).toBeDefined()
    expect(wrapper.classes()).toContain('is-disabled')
  })
})
