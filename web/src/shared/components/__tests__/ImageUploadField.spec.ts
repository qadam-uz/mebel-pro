import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ImageUploadField from '@/shared/components/ImageUploadField.vue'

describe('ImageUploadField', () => {
  it('emits the selected image and shows an immediate local preview', async () => {
    const createObjectURL = vi.fn(() => 'blob:image-preview')
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })

    const wrapper = mount(ImageUploadField, {
      props: { fileId: null, alt: 'Material image' },
      global: { stubs: { AuthFileImage: true } },
    })
    const file = new File(['x'], 'oak.webp', { type: 'image/webp' })
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })

    await input.trigger('change')

    expect(wrapper.emitted('select')?.[0]).toEqual([file])
    expect(wrapper.get('img').attributes('src')).toBe('blob:image-preview')
    expect(wrapper.text()).toContain('oak.webp')
  })

  it('clears the local preview and emits remove', async () => {
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:image-preview'),
    })
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })

    const wrapper = mount(ImageUploadField, {
      props: { fileId: null, alt: 'Material image' },
      global: { stubs: { AuthFileImage: true } },
    })
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['x'], 'oak.jpg', { type: 'image/jpeg' })],
      configurable: true,
    })

    await input.trigger('change')
    await wrapper.findAll('button')[1].trigger('click')

    expect(wrapper.emitted('remove')).toHaveLength(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:image-preview')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('renders an existing authenticated image when a file id exists', () => {
    const wrapper = mount(ImageUploadField, {
      props: { fileId: 'file-1', alt: 'Oak material' },
      global: { stubs: { AuthFileImage: { template: '<img data-auth-file-image />' } } },
    })

    expect(wrapper.find('[data-auth-file-image]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Saqlangan rasm')
    expect(wrapper.get('button').text()).toBe('Rasmni almashtirish')
  })
})
