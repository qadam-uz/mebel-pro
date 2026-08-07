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

/** A row the attach call reports back as created — the store prepends it. */
function created(dekorId: string): BranchMaterial {
  return branchMaterial(dekorId, { qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070 })
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

type Sheet = ReturnType<typeof mountSheet>

/** Tick the nth dekor card (step 1 is multi-select — cards are checkboxes). */
async function tickDekor(wrapper: Sheet, index = 0) {
  await wrapper.findAll('li input[type="checkbox"]')[index].trigger('change')
}

async function continueToFormats(wrapper: Sheet) {
  await wrapper.find('button.mp-button-primary').trigger('click')
}

/** Step 1 → step 2 on the first dekor alone — the single-dekor path. */
async function pickFirstDekor(wrapper: Sheet) {
  await tickDekor(wrapper, 0)
  await continueToFormats(wrapper)
}

/** Click a chip by its visible text (`18 mm`, `2800×2070`, …). */
async function clickChip(wrapper: Sheet, text: string, blockIndex = 0) {
  const block = wrapper.findAll('fieldset')
  // Two fieldsets per tur block: qalinlik, then o'lcham / lenta eni.
  const scope = [block[blockIndex * 2], block[blockIndex * 2 + 1]]
  const chip = scope.flatMap((node) => node.findAll('button')).find((node) => node.text() === text)
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
    expect(wrapper.text()).toContain("2 o'lcham bor")
  })

  // "Davom etish" needs a selection; nothing ticked is not a step.
  it('blocks "Davom etish" until at least one dekor is ticked', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 0 }])
    const wrapper = mountSheet()
    await flushPromises()

    expect(wrapper.find('button.mp-button-primary').attributes('disabled')).toBeDefined()
    await tickDekor(wrapper, 0)
    expect(wrapper.find('button.mp-button-primary').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('1 ta tanlandi')
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
      panel.find<HTMLInputElement>(
        '[aria-label="Dekor d-1 · 2800×2070×18 mm kam qoldiq chegarasi"]',
      ).element.value,
    ).toBe('0')

    respondWith([{ dekor: dekor('d-2', 'kromka'), carried_format_count: 0 }])
    const tape = mountSheet()
    await flushPromises()
    await pickFirstDekor(tape)
    await clickChip(tape, '0.4 mm')
    await clickChip(tape, '19 mm')
    expect(
      tape.find<HTMLInputElement>('[aria-label="Dekor d-2 · 0.4×19 mm kam qoldiq chegarasi"]')
        .element.value,
    ).toBe('0')
  })

  // Price is optional now: a branch routinely registers its whole format list
  // before it knows prices, so an empty field means 0 tiyin, not a rejection.
  it('attaches an unpriced o’lcham, sending price_tiyin: 0', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 0 }])
    vi.mocked(api.post).mockResolvedValue({ created: [created('d-1')], skipped: [] })
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
      items: [
        {
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
        },
      ],
    })
  })

  // The job this sheet exists for: many dekorlar, one o'lcham, one save. The
  // chips are picked ONCE and apply to every selected dekor of that tur.
  it('sends one item per dekor when several share one o’lcham', async () => {
    respondWith([
      { dekor: dekor('d-1'), carried_format_count: 0 },
      { dekor: dekor('d-2'), carried_format_count: 0 },
    ])
    vi.mocked(api.post).mockResolvedValue({
      created: [created('d-1'), created('d-2')],
      skipped: [],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await tickDekor(wrapper, 0)
    await tickDekor(wrapper, 1)
    await continueToFormats(wrapper)
    await clickChip(wrapper, '18 mm')
    await clickChip(wrapper, '2800×2070')

    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    const [, body] = vi.mocked(api.post).mock.calls[0]
    expect(body).toEqual({
      items: [
        {
          dekor_id: 'd-1',
          formats: [
            { qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070, price_tiyin: 0, min_stock: 0 },
          ],
        },
        {
          dekor_id: 'd-2',
          formats: [
            { qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070, price_tiyin: 0, min_stock: 0 },
          ],
        },
      ],
    })
  })

  // A board and its matching kromka have different o'lcham axes and still belong
  // in one save, so each tur gets its own chip block.
  it('gives every tur in the selection its own chip block', async () => {
    respondWith([
      { dekor: dekor('d-1', 'ldsp'), carried_format_count: 0 },
      { dekor: dekor('d-2', 'kromka'), carried_format_count: 0 },
    ])
    vi.mocked(api.post).mockResolvedValue({
      created: [created('d-1'), created('d-2')],
      skipped: [],
    })
    const wrapper = mountSheet()
    await flushPromises()
    await tickDekor(wrapper, 0)
    await tickDekor(wrapper, 1)
    await continueToFormats(wrapper)

    // Four fieldsets: qalinlik + o'lcham for LDSP, qalinlik + lenta eni for kromka.
    expect(wrapper.findAll('fieldset')).toHaveLength(4)
    expect(wrapper.text()).toContain('Lenta eni')

    await clickChip(wrapper, '18 mm', 0)
    await clickChip(wrapper, '2800×2070', 0)
    await clickChip(wrapper, '2 mm', 1)
    await clickChip(wrapper, '19 mm', 1)

    await wrapper.find('button.mp-button-primary').trigger('click')
    await flushPromises()

    const [, body] = vi.mocked(api.post).mock.calls[0]
    expect(body).toEqual({
      items: [
        {
          dekor_id: 'd-1',
          formats: [
            { qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070, price_tiyin: 0, min_stock: 0 },
          ],
        },
        {
          dekor_id: 'd-2',
          formats: [{ qalinlik_mm: '2', kromka_eni_mm: 19, price_tiyin: 0, min_stock: 0 }],
        },
      ],
    })
  })

  // "Filtrdagi hammasi (N)" covers the filter, not the loaded page — it pages
  // through the rest server-side before selecting.
  it('selects every dekor in the filter, paging past the loaded page', async () => {
    const page1 = [
      { dekor: dekor('d-1'), carried_format_count: 0 },
      { dekor: dekor('d-2'), carried_format_count: 0 },
    ]
    const page2 = [{ dekor: dekor('d-3'), carried_format_count: 0 }]
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path.includes('/catalog/filters')) return { manufacturers: [] }
      if (path.includes('/catalog/dekorlar')) {
        return { items: path.includes('offset=2') ? page2 : page1, total: 3 }
      }
      return []
    })
    const wrapper = mountSheet()
    await flushPromises()

    expect(wrapper.text()).toContain('Filtrdagi hammasi (3)')
    // The master checkbox sits outside the card list.
    await wrapper.find('input[type="checkbox"]').trigger('change')
    await flushPromises()

    expect(wrapper.text()).toContain('3 ta tanlandi')
  })

  // Both axes are multi-select; the cross product is what gets created.
  it('posts the cross product of the picked qalinliklar and o’lchamlar', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 0 }])
    vi.mocked(api.post).mockResolvedValue({
      created: [created('d-1'), created('d-1'), created('d-1'), created('d-1')],
      skipped: [],
    })
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
    expect((body as { items: { formats: unknown[] }[] }).items[0].formats).toHaveLength(4)
  })

  // A combination the branch already carries is shown, disabled, and left out of
  // the payload — the server would skip it anyway, but the operator should see why.
  it('disables an already-carried combination and never submits it', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 1 }])
    vi.mocked(api.post).mockResolvedValue({ created: [created('d-1')], skipped: [] })
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
      items: [
        {
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
        },
      ],
    })
  })

  // The branch's own off-standard qalinliklar get their own group, so a standard
  // set never silently grows. The group is scoped by TUR, not by the selected
  // dekor: the operator is usually adding dekorlar the branch does not carry yet.
  it('offers the branch’s own non-standard qalinlik under "Nostandart"', async () => {
    respondWith([{ dekor: dekor('d-9'), carried_format_count: 0 }])
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

  // A duplicate o'lcham is skipped server-side, not rejected — the caller has to
  // be able to say "1 added, 1 already there".
  it('reports created and skipped counts to its parent', async () => {
    respondWith([{ dekor: dekor('d-1'), carried_format_count: 0 }])
    vi.mocked(api.post).mockResolvedValue({
      created: [created('d-1')],
      skipped: [
        {
          dekor_id: 'd-1',
          qalinlik_mm: '18',
          uzunlik_mm: 2800,
          eni_mm: 2070,
          kromka_eni_mm: null,
        },
      ],
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
