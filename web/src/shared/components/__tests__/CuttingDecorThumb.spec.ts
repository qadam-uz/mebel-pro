import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import CuttingDecorThumb from '@/shared/components/CuttingDecorThumb.vue'

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

function requested() {
  return vi.mocked(api.blob).mock.calls.map((call) => call[0])
}

/**
 * The rendition this component asks for, pinned (spec decision 21).
 *
 * It is worth a test rather than a code comment because the cost is invisible
 * locally and only shows up on the connections this app actually runs over: a
 * picker row holds dozens of these, and one wrong word here is the difference
 * between 5 KB and 1.5 MB per row.
 */
describe('CuttingDecorThumb', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.blob).mockReset()
    vi.mocked(api.blob).mockResolvedValue(new Blob(['x']))
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:test'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  })

  it('draws the row swatch from the small rendition', async () => {
    mount(CuttingDecorThumb, {
      props: { fileId: 'file-a', label: 'Egger H1137' },
      global: { stubs: { Icon: true, AppModal: true } },
    })
    await flushPromises()

    expect(requested()).toEqual(['/files/file-a?size=sm'])
  })

  it('opens the lightbox on the cached small rendition, then the original', async () => {
    // Never `md`: nothing on the page caches it, so it would be a second
    // download of a picture the row beside it already has.
    const wrapper = mount(CuttingDecorThumb, {
      props: { fileId: 'file-a', label: 'Egger H1137' },
      global: {
        stubs: {
          Icon: true,
          // Renders its slot only while open, like the real modal — otherwise
          // the lightbox image mounts before anything is clicked.
          AppModal: { props: ['open'], template: '<div v-if="open"><slot /></div>' },
        },
      },
    })
    await flushPromises()
    vi.mocked(api.blob).mockClear()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(requested()).toEqual(['/files/file-a?size=sm', '/files/file-a'])
  })
})
