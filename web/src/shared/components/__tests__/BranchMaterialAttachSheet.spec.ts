import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/shared/api/client'
import BranchMaterialAttachSheet from '@/shared/components/BranchMaterialAttachSheet.vue'
import type { Dekor, DekorType } from '@/shared/stores/admin'
import { useWorkshopStore, type BranchMaterial } from '@/shared/stores/workshop'

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

function dekor(id: string, tur: DekorType = 'ldsp'): Dekor {
  return {
    id,
    manufacturer_id: 'maker-1',
    manufacturer_name: 'Egger',
    tur,
    kod: `H${id}`,
    nomi: 'Dub Sonoma',
    tolali: false,
    image_file_id: null,
    holat: 'active',
    label: `Dekor ${id}`,
    branch_usage_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

/** A row this branch already carries — feeds the carried / non-standard chips. */
function branchMaterial(dekorId: string, format: Partial<BranchMaterial>): BranchMaterial {
  return {
    id: `bm-${dekorId}-${format.qalinlik_mm}`,
    branch_id: 'branch-1',
    dekor_id: dekorId,
    dekor: dekor(dekorId),
    qalinlik_mm: '18',
    uzunlik_mm: null,
    eni_mm: null,
    kromka_eni_mm: null,
    price_tiyin: 0,
    price_unset: true,
    min_stock: 0,
    status: 'active',
    label: 'Dekor d-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...format,
  }
}

/** `GET .../catalog/dekorlar` returns the picker page; `.../catalog/filters` the facets. */
function respondWith(
  items: { dekor: Dekor; carried_format_count: number }[],
  total = items.length,
) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.includes('/catalog/filters')) return { manufacturers: [] }
    if (path.includes('/catalog/dekorlar')) return { items, total }
    return []
  })
}

function mountSheet() {
  return mount(BranchMaterialAttachSheet, {
    props: { open: true, branchId: 'branch-1' },
    global: { stubs: { teleport: true } },
  })
}

/** Step 1 → step 2: pick the first dekor card, then "Davom etish". */
async function pickFirstDekor(wrapper: ReturnType<typeof mountSheet>) {
  await wrapper.find('li button').trigger('click')
  await wrapper.find('button.mp-button-primary').trigger('click')
}

/** Click a chip by its visible text (`18 mm`, `2800×2070`, …). */
async function clickChip(wrapper: ReturnType<typeof mountSheet>, text: string) {
  const chip = wrapper.findAll('fieldset button').find((node) => node.text() === text)
  if (!chip) throw new Error(`chip not found: ${text}`)
  await chip.trigger('click')
}

describe('BranchMaterialAttachSheet', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
  })

  // A dekor the branch already carries is never hidden — carrying 18 mm does not
  // stop you adding 16 mm — so the picker labels it instead of dropping it.
  it('lists carried dekorlar with their format count instead of hiding them', async () => {
    respondWith([
      { dekor: dekor('d-1'), carried_format_count: 2 },
      { dekor: dekor('d-2'), carried_format_count: 0 },
    ])
    const wrapper = mountSheet()
    await flushPromises()

    expect(wrapper.text()).toContain('Dekor d-1')
    expect(wrapper.text()).toContain('Dekor d-2')
    expect(wrapper.text()).toContain('2 format bor')
  })

  // The threshold prefills 0 for every tur: a branch registers its format list
  // before it knows a threshold, so a non-zero prefill would be a number nobody
  // chose. QAD-159's 5 / 50 m prefill is deliberately reversed here.
  it('prefills the low-stock threshold at 0 for both a panel and kromka', async () => {
    respondWith([{ dekor: dekor('d-1', 'ldsp'), carried_format_count: 0 }])
    const panel = mountSheet()
    await flushPromises()
    await pickFirstDekor(panel)
    await clickChip(panel, '18 mm')
    await clickChip(panel, '2800×2070')
    expect(
      panel.find<HTMLInputElement>('[aria-label="2800×2070×18 mm kam qoldiq chegarasi"]').element
        .value,
    ).toBe('0')

    respondWith([{ dekor: dekor('d-2', 'kromka'), carried_format_count: 0 }])
    const tape = mountSheet()
    await flushPromises()
    await pickFirstDekor(tape)
    await clickChip(tape, '0.4 mm')
    await clickChip(tape, '19 mm')
    expect(
      tape.find<HTMLInputElement>('[aria-label="0.4×19 mm kam qoldiq chegarasi"]').element.value,
    ).toBe('0')
  })

  // Price is optional now: a branch routinely registers its whole format list
  // before it knows prices, so an empty field means 0 tiyin, not a rejection.
  it('attaches an unpriced format, sending price_tiyin: 0', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 0 }])
    vi.mocked(api.post).mockResolvedValue({ created: [{}], skipped: [] })
    const wrapper = mountSheet()
    await flushPromises()
    await pickFirstDekor(wrapper)
    await clickChip(wrapper, '18 mm')
    await clickChip(wrapper, '2800×2070')

    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    const [path, body] = vi.mocked(api.post).mock.calls[0]
    expect(path).toBe('/workshop/branches/branch-1/materials')
    expect(body).toEqual({
      dekor_id: 'd-1',
      formats: [
        {
          qalinlik_mm: '18',
          uzunlik_mm: 2800,
          eni_mm: 2070,
          price_tiyin: 0,
          min_stock: 0,
        },
      ],
    })
  })

  // Both axes are multi-select; the cross product is what gets created.
  it('posts the cross product of the picked thicknesses and sizes', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 0 }])
    vi.mocked(api.post).mockResolvedValue({ created: [{}, {}, {}, {}], skipped: [] })
    const wrapper = mountSheet()
    await flushPromises()
    await pickFirstDekor(wrapper)
    await clickChip(wrapper, '16 mm')
    await clickChip(wrapper, '18 mm')
    await clickChip(wrapper, '2750×1830')
    await clickChip(wrapper, '2800×2070')

    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    const [, body] = vi.mocked(api.post).mock.calls[0]
    expect((body as { formats: unknown[] }).formats).toHaveLength(4)
  })

  // A combination the branch already carries is shown, disabled, and left out of
  // the payload — the server would skip it anyway, but the operator should see why.
  it('disables an already-carried combination and never submits it', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 1 }])
    vi.mocked(api.post).mockResolvedValue({ created: [{}], skipped: [] })
    const wrapper = mountSheet()
    const workshop = useWorkshopStore()
    workshop.branchMaterials = [
      branchMaterial('d-1', { qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070 }),
    ]
    await flushPromises()
    await pickFirstDekor(wrapper)
    await clickChip(wrapper, '18 mm')
    await clickChip(wrapper, '2800×2070')
    await clickChip(wrapper, '2750×1830')

    expect(wrapper.text()).toContain("Allaqachon qo'shilgan")
    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    const [, body] = vi.mocked(api.post).mock.calls[0]
    expect(body).toEqual({
      dekor_id: 'd-1',
      formats: [
        {
          qalinlik_mm: '18',
          uzunlik_mm: 2750,
          eni_mm: 1830,
          price_tiyin: 0,
          min_stock: 0,
        },
      ],
    })
  })

  // The branch's own off-standard thicknesses get their own group, so a standard
  // set never silently grows.
  it('offers the branch’s own non-standard thickness under "Nostandart"', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 1 }])
    const wrapper = mountSheet()
    const workshop = useWorkshopStore()
    workshop.branchMaterials = [
      branchMaterial('d-1', { qalinlik_mm: '22', uzunlik_mm: 2800, eni_mm: 2070 }),
    ]
    await flushPromises()
    await pickFirstDekor(wrapper)

    expect(wrapper.text()).toContain('Nostandart')
    expect(wrapper.findAll('fieldset button').map((node) => node.text())).toContain('22 mm')
  })

  // A duplicate format is skipped server-side, not rejected — the caller has to
  // be able to say "1 added, 1 already there".
  it('reports created and skipped counts to its parent', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 0 }])
    vi.mocked(api.post).mockResolvedValue({
      created: [{}],
      skipped: [{ qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070, kromka_eni_mm: null }],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await pickFirstDekor(wrapper)
    await clickChip(wrapper, '18 mm')
    await clickChip(wrapper, '2800×2070')

    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('attached')?.[0]).toEqual([{ created: 1, skipped: 1 }])
  })
})
