import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'

vi.mock('@/shared/api/client', () => ({
  api: { blob: vi.fn() },
  apiTraceId: () => null,
  withQuery: (path: string, params: Record<string, unknown>) => {
    const search = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value === null || value === undefined || value === '') continue
      search.set(key, String(value))
    }
    const query = search.toString()
    return query ? `${path}?${query}` : path
  },
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

  it('shows a loading skeleton while the saved image is being fetched', async () => {
    const pending = deferred<Blob>()
    vi.mocked(api.blob).mockReturnValueOnce(pending.promise as never)

    const wrapper = mount(AuthFileImage, {
      props: { fileId: 'file-a', alt: 'Logo' },
    })

    // Before the fetch resolves: skeleton visible, no <img>, not the empty state.
    const skeleton = wrapper.find('[aria-busy="true"]')
    expect(skeleton.exists()).toBe(true)
    expect(skeleton.classes()).toContain('sk')
    expect(wrapper.find('img').exists()).toBe(false)

    pending.resolve(new Blob(['a']))
    await flushPromises()

    // Once loaded: image shown, skeleton gone.
    expect(wrapper.find('img').attributes('src')).toBe('blob:test-1')
    expect(wrapper.find('[aria-busy="true"]').exists()).toBe(false)
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

  // The size a screen draws is the whole point of renditions: the production
  // original is 2160x2160 / 1.5 MB and these boxes are 34-58 px.
  it('requests the small rendition by default', async () => {
    vi.mocked(api.blob).mockResolvedValueOnce(new Blob(['x']) as never)

    mount(AuthFileImage, { props: { fileId: 'file-a', alt: 'Swatch' } })
    await flushPromises()

    expect(vi.mocked(api.blob).mock.calls[0]?.[0]).toBe('/files/file-a?size=sm')
  })

  it('requests the rendition it was given', async () => {
    vi.mocked(api.blob).mockResolvedValueOnce(new Blob(['x']) as never)

    mount(AuthFileImage, { props: { fileId: 'file-a', alt: 'Preview', size: 'md' } })
    await flushPromises()

    expect(vi.mocked(api.blob).mock.calls[0]?.[0]).toBe('/files/file-a?size=md')
  })

  it('sends no size parameter for the original, keeping the pre-rendition URL', async () => {
    vi.mocked(api.blob).mockResolvedValueOnce(new Blob(['x']) as never)

    mount(AuthFileImage, { props: { fileId: 'file-a', alt: 'Full', size: 'original' } })
    await flushPromises()

    expect(vi.mocked(api.blob).mock.calls[0]?.[0]).toBe('/files/file-a')
  })

  it('re-fetches when the requested rendition changes', async () => {
    vi.mocked(api.blob)
      .mockResolvedValueOnce(new Blob(['small']) as never)
      .mockResolvedValueOnce(new Blob(['medium']) as never)

    const wrapper = mount(AuthFileImage, { props: { fileId: 'file-a', alt: 'Swatch' } })
    await flushPromises()
    await wrapper.setProps({ size: 'md' })
    await flushPromises()

    expect(vi.mocked(api.blob).mock.calls.map((call) => call[0])).toEqual([
      '/files/file-a?size=sm',
      '/files/file-a?size=md',
    ])
  })

  describe('progressive upgrade', () => {
    it('shows the small rendition first, then swaps in the larger one', async () => {
      const small = deferred<Blob>()
      const large = deferred<Blob>()
      vi.mocked(api.blob)
        .mockReturnValueOnce(small.promise as never)
        .mockReturnValueOnce(large.promise as never)

      const wrapper = mount(AuthFileImage, {
        props: { fileId: 'file-a', alt: 'Detail', size: 'sm', upgradeTo: 'md' },
      })
      small.resolve(new Blob(['small']))
      await flushPromises()
      const afterSmall = wrapper.find('img').attributes('src')

      large.resolve(new Blob(['large']))
      await flushPromises()

      expect(afterSmall).toBe('blob:test-1')
      // Swapped, and the small object URL released only after the new src landed —
      // so there is never a frame without an image.
      expect(wrapper.find('img').attributes('src')).toBe('blob:test-2')
      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-1')
    })

    it('keeps the small rendition when the upgrade fails, and reports nothing', async () => {
      vi.mocked(api.blob)
        .mockResolvedValueOnce(new Blob(['small']) as never)
        .mockRejectedValueOnce(new Error('network went away'))

      const wrapper = mount(AuthFileImage, {
        props: { fileId: 'file-a', alt: 'Detail', size: 'sm', upgradeTo: 'md' },
      })
      await flushPromises()

      // The user is already looking at a correct image; a failed upgrade must not
      // turn that into an error state.
      expect(wrapper.find('img').attributes('src')).toBe('blob:test-1')
      expect(wrapper.find('img').exists()).toBe(true)
    })

    it('does not upgrade at all unless asked', async () => {
      vi.mocked(api.blob).mockResolvedValueOnce(new Blob(['small']) as never)

      mount(AuthFileImage, { props: { fileId: 'file-a', alt: 'Swatch' } })
      await flushPromises()

      // Upgrading by default would download the same picture twice on the exact
      // connection that was the bottleneck.
      expect(api.blob).toHaveBeenCalledTimes(1)
    })
  })
})
