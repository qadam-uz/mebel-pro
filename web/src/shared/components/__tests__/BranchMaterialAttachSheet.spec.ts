import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import BranchMaterialAttachSheet from '@/shared/components/BranchMaterialAttachSheet.vue'
import type { Material } from '@/shared/stores/admin'

vi.mock('@/shared/app/authInit', () => ({
  authInit: () => ({ accessToken: 'access-token' }),
}))

vi.mock('@/shared/api/client', () => {
  class ApiError extends Error {
    constructor(
      readonly status: number,
      readonly body: unknown,
    ) {
      super(`API ${status}`)
      this.name = 'ApiError'
    }
  }
  return {
    ApiError,
    api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn(), blob: vi.fn() },
    apiErrorCode: () => null,
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
  }
})

function material(id: string, kind: 'panel' | 'edge' = 'panel'): Material {
  return {
    id,
    kind,
    manufacturer_id: 'maker-1',
    manufacturer_name: 'Maker',
    type: kind === 'panel' ? 'dsp' : null,
    name: `Material ${id}`,
    thickness_mm: kind === 'panel' ? '16' : '0.8',
    color: 'Oak',
    decor_code: null,
    panel_length_mm: kind === 'panel' ? 2800 : null,
    panel_width_mm: kind === 'panel' ? 2070 : null,
    edge_width_mm: kind === 'edge' ? 22 : null,
    grain_direction: false,
    image_file_id: null,
    status: 'active',
  } as unknown as Material
}

/** `GET .../catalog/materials` returns a page; `.../catalog/filters` the facets. */
function respondWith(pages: { items: Material[]; total: number }[]) {
  let call = 0
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.includes('/catalog/filters')) return { manufacturers: [], thicknesses: [] }
    const page = pages[Math.min(call, pages.length - 1)]
    call += 1
    return { items: page.items.map((row) => ({ material: row })), total: page.total }
  })
}

function mountSheet() {
  return mount(BranchMaterialAttachSheet, {
    props: { open: true, branchId: 'branch-1' },
    global: { stubs: { teleport: true } },
  })
}

describe('BranchMaterialAttachSheet', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
  })

  // The bulk action's whole promise: "Filtrdagi hammasi (N)" selects every match,
  // not the page on screen. The seeded E2E catalog is smaller than one page, so
  // this cross-page case only ever gets proven here.
  it('selects every material matching the filter, including pages not yet loaded', async () => {
    const first = Array.from({ length: 100 }, (_, index) => material(`m-${index}`))
    const second = Array.from({ length: 30 }, (_, index) => material(`m-${100 + index}`))
    respondWith([
      { items: first, total: 130 },
      { items: second, total: 130 },
    ])
    const wrapper = mountSheet()
    await flushPromises()

    expect(wrapper.text()).toContain('Filtrdagi hammasi (130)')

    await wrapper.find('input[type="checkbox"]').setValue(true)
    await flushPromises()

    expect(wrapper.text()).toContain('130 ta tanlandi')
    expect(wrapper.text()).toContain('Davom etish (130)')
  })

  it('leaves the master checkbox unchecked while matches beyond the page are unknown', async () => {
    const first = Array.from({ length: 100 }, (_, index) => material(`m-${index}`))
    respondWith([{ items: first, total: 130 }])
    const wrapper = mountSheet()
    await flushPromises()

    const master = wrapper.find('input[type="checkbox"]')
    expect((master.element as HTMLInputElement).checked).toBe(false)
  })

  // A prefilled 0 switched low-stock alerts off for every material ever attached.
  it('prefills the low-stock threshold per material kind — 5 for a panel, 50 m for kromka', async () => {
    respondWith([{ items: [material('p-1', 'panel'), material('e-1', 'edge')], total: 2 }])
    const wrapper = mountSheet()
    await flushPromises()

    const boxes = wrapper.findAll('li input[type="checkbox"]')
    await boxes[0].setValue(true)
    await boxes[1].setValue(true)
    await wrapper.find('button.mp-button-primary').trigger('click')

    const panelThreshold = wrapper.find<HTMLInputElement>(
      '[aria-label="Material p-1 kam qoldiq chegarasi"]',
    )
    const edgeThreshold = wrapper.find<HTMLInputElement>(
      '[aria-label="Material e-1 kam qoldiq chegarasi"]',
    )
    expect(panelThreshold.element.value).toBe('5')
    expect(edgeThreshold.element.value).toBe('50')
  })

  it('refuses to attach a material with no price and never calls the API', async () => {
    respondWith([{ items: [material('p-1')], total: 1 }])
    const wrapper = mountSheet()
    await flushPromises()

    await wrapper.find('li input[type="checkbox"]').setValue(true)
    await wrapper.find('button.mp-button-primary').trigger('click')
    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    expect(api.post).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('narxsiz material')
  })

  it('bulk-fills every selected row, then lets one row override the shared price', async () => {
    respondWith([{ items: [material('p-1'), material('p-2')], total: 2 }])
    const wrapper = mountSheet()
    await flushPromises()

    const boxes = wrapper.findAll('li input[type="checkbox"]')
    await boxes[0].setValue(true)
    await boxes[1].setValue(true)
    await wrapper.find('button.mp-button-primary').trigger('click')

    // "Hammasiga" bar: price, threshold, then Qo'llash.
    const bulkInputs = wrapper.findAll('.bg-sunk input')
    await bulkInputs[0].setValue('120000')
    await wrapper.findAll('.bg-sunk button')[0].trigger('click')

    const rowPrice = wrapper.find<HTMLInputElement>('[aria-label="Material p-2 narxi"]')
    expect(wrapper.find<HTMLInputElement>('[aria-label="Material p-1 narxi"]').element.value).toBe(
      '120000',
    )
    expect(rowPrice.element.value).toBe('120000')

    await rowPrice.setValue('99000')
    vi.mocked(api.post).mockResolvedValue({ created: [{}, {}], skipped_material_ids: [] })
    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    const [, body] = vi.mocked(api.post).mock.calls[0]
    expect(body).toEqual({
      items: [
        { material_id: 'p-1', price_tiyin: 12000000, min_stock: 5 },
        { material_id: 'p-2', price_tiyin: 9900000, min_stock: 5 },
      ],
    })
  })
})
