import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'

vi.mock('@/shared/api/client', () => ({
  api: { blob: vi.fn() },
  apiTraceId: () => null,
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

describe('AuthFileImage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.blob).mockReset()
    let index = 0
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => `blob:test-${++index}`),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
  })

  it('revokes a stale object URL when an older file load resolves late', async () => {
    const first = deferred<Blob>()
    const second = deferred<Blob>()
    vi.mocked(api.blob)
      .mockReturnValueOnce(first.promise as never)
      .mockReturnValueOnce(second.promise as never)

    const wrapper = mount(AuthFileImage, {
      props: { fileId: 'file-a', alt: 'Logo' },
    })
    await wrapper.setProps({ fileId: 'file-b' })

    second.resolve(new Blob(['b']))
    await flushPromises()
    expect(wrapper.find('img').attributes('src')).toBe('blob:test-1')

    first.resolve(new Blob(['a']))
    await flushPromises()

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-2')
    expect(wrapper.find('img').attributes('src')).toBe('blob:test-1')
  })
})
