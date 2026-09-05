import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import { DEFAULT_LOCALE, setLocale } from '@/shared/i18n'
import CuttingResultsSection from '@/shared/components/CuttingResultsSection.vue'
import {
  useCuttingStore,
  type CuttingDraft,
  type CuttingPart,
  type CuttingResult,
} from '@/shared/stores/cutting'
import type { OrderQuote } from '@/shared/stores/orders'

const PANEL_A = 'panel-a'
const PANEL_B = 'panel-b'
const EDGE_A = 'edge-a'
const EDGE_B = 'edge-b'

function part(overrides: Partial<CuttingPart> = {}): CuttingPart {
  return {
    part_ref: 'part-a',
    name: null,
    material_id: PANEL_A,
    material_source: 'shop',
    follow_grain: true,
    thickened: false,
    length_mm: 300,
    width_mm: 200,
    quantity: 1,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
    ...overrides,
  }
}

function result(): CuttingResult {
  return {
    id: 'result-a',
    draft_id: 'draft-a',
    algorithm_name: 'guillotine',
    algorithm_version: '1',
    source: 'optimizer',
    status: 'candidate',
    kerf_mm: 4,
    edge_trim_mm: 5,
    panels_used_by_material: { [PANEL_A]: 5, [PANEL_B]: 2 },
    waste_percentage: '0.12',
    total_cut_length_mm: 0,
    total_edge_length_mm: 0,
    edge_length_by_material: {},
    // The tapes appear in this order on the parts, so the registry numbers them
    // ① then ② — the receipt must follow that, not the quote's own ordering.
    parts_snapshot: [
      part({
        edge_top: { material_id: EDGE_A, source: 'shop' },
        edge_left: { material_id: EDGE_B, source: 'shop' },
      }),
    ],
    material_snapshots: {
      [PANEL_A]: { panel_length_mm: 2750, panel_width_mm: 1830, thickness_mm: '18' },
      [PANEL_B]: { panel_length_mm: 2800, panel_width_mm: 2070, thickness_mm: '16' },
    },
    edge_length_shop_by_material: {},
    edge_length_own_by_material: {},
    edge_consumed_shop_by_material: { [EDGE_A]: 13500, [EDGE_B]: 8000 },
    edge_consumed_own_by_material: {},
    edge_banded_sides_by_material: {},
    order_id: null,
    created_at: '',
    confirmed_at: null,
    invalidated_at: null,
    panels: [],
  } as unknown as CuttingResult
}

function draft(): CuttingDraft {
  return {
    id: 'draft-a',
    name: 'Oshxona',
    preferred_branch_id: 'branch-a',
    chosen_result_id: 'result-a',
    own_panel_counts: {},
    own_edge_material_ids: [],
    results: [result()],
    parts: [],
  } as unknown as CuttingDraft
}

function quote(): OrderQuote {
  return {
    draft_id: 'draft-a',
    branch_id: 'branch-a',
    panels_used: 7,
    cutting_rate_tiyin: 3_000_000,
    edge_banding_rate_tiyin: 100_000,
    subtotal_cutting_tiyin: 21_000_000,
    subtotal_materials_tiyin: 235_000_000,
    subtotal_edge_banding_tiyin: 5_550_000,
    total_tiyin: 261_550_000,
    material_lines: [
      {
        material_id: PANEL_A,
        material_name: 'LDSP Egger H1334 · Sanoma · 2750×1830×18 mm',
        panels_used: 5,
        own_panels: 0,
        unit_price_tiyin: 30_000_000,
        line_total_tiyin: 150_000_000,
      },
      {
        material_id: PANEL_B,
        material_name: 'LDSP Kronospan W980 · Oq · 2800×2070×16 mm',
        panels_used: 2,
        own_panels: 0,
        unit_price_tiyin: 42_500_000,
        line_total_tiyin: 85_000_000,
      },
    ],
    edge_lines: [
      {
        material_id: EDGE_B,
        material_name: 'ABS Oq · 1×19',
        consumed_mm: 8000,
        own: false,
        metre_price_tiyin: 500_000,
        material_cost_tiyin: 4_000_000,
        service_cost_tiyin: 800_000,
        line_total_tiyin: 4_800_000,
      },
      {
        material_id: EDGE_A,
        material_name: 'ABS H1334 · 0.4×19',
        consumed_mm: 13500,
        own: false,
        metre_price_tiyin: 500_000,
        material_cost_tiyin: 6_750_000,
        service_cost_tiyin: 1_350_000,
        line_total_tiyin: 8_100_000,
      },
    ],
  } as unknown as OrderQuote
}

function mountSection(
  overrides: {
    draft?: Partial<CuttingDraft>
    quote?: Partial<OrderQuote>
    // Own material is hidden on every client surface in the MVP (§7.7), so the
    // own-material assertions describe the WORKSHOP's copy of this card. The
    // store scope is what the component branches on.
    scope?: 'client' | 'workshop'
  } = {},
) {
  useCuttingStore().configureScope(overrides.scope ?? 'client')
  return mount(CuttingResultsSection, {
    props: {
      draft: { ...draft(), ...overrides.draft } as CuttingDraft,
      optimizeError: null,
      activePanelId: null,
      checkoutPath: '/c/orders/new',
      branchId: 'branch-a',
      quoteForDraft: vi.fn().mockResolvedValue({ ...quote(), ...overrides.quote }),
    },
    global: {
      provide: { [roleConfigKey as symbol]: clientConfig },
      stubs: {
        CuttingResultOverview: true,
        Icon: true,
        RouterLink: { template: '<a><slot/></a>' },
      },
    },
  })
}

describe('CuttingResultsSection receipt card', () => {
  it('shows the arithmetic behind every material line, not just its total', async () => {
    // A rolled-up subtotal asks to be trusted; `5 × 300 000 = 1 500 000` can be
    // checked, which is the whole point of the receipt.
    setActivePinia(createPinia())
    const wrapper = mountSection()
    await flushPromises()

    const text = wrapper.text().replace(/\u00a0/g, ' ')
    expect(text).toContain('5 list × 300 000 = 1 500 000')
    expect(text).toContain('2 list × 425 000 = 850 000')
  })

  it('prices cutting on every sheet, in its own section', async () => {
    // Cutting is charged per sheet regardless of whose material it is, so it
    // never belongs inside a material row.
    setActivePinia(createPinia())
    const wrapper = mountSection()
    await flushPromises()

    const text = wrapper.text().replace(/\u00a0/g, ' ')
    expect(text).toContain('Xizmatlar')
    expect(text).toContain('7 list × 30 000 = 210 000')
  })

  it('sums edge labour across tapes and shows the material share per tape', async () => {
    setActivePinia(createPinia())
    const wrapper = mountSection()
    await flushPromises()

    const text = wrapper.text().replace(/\u00a0/g, ' ')
    expect(text).toContain('21.50 m')
    expect(text).toContain('21.50 m × 1 000 = 21 500')
    expect(text).toContain('67 500')
    expect(text).toContain('40 000')
  })

  it('orders tapes by their registry number, not by the order the quote sent', async () => {
    // The quote lists edge-b first; the registry numbers edge-a ① because the
    // part uses it first. One tape must read as one thing across the drawing,
    // the parts list and this card.
    setActivePinia(createPinia())
    const wrapper = mountSection()
    await flushPromises()

    const text = wrapper.text()
    expect(text.indexOf('ABS H1334')).toBeLessThan(text.indexOf('ABS Oq'))
  })

  it('carries the currency on the totals only, never on a factor', async () => {
    setActivePinia(createPinia())
    const wrapper = mountSection()
    await flushPromises()

    const text = wrapper.text().replace(/\u00a0/g, ' ')
    expect(text).toContain("2 615 500 so'm")
    // Twice, and only twice: the phone hero's price (\u00a77.7) and the receipt's
    // \u00abJami\u00bb. Repeating it on every factor turned each line into three currency
    // labels \u2014 that is what this counts, and `5 list \u00d7 300 000 = 1 500 000`
    // above is the line it protects.
    expect(text.match(/so'm/g) ?? []).toHaveLength(2)
  })

  it('leaves the sheet size to the material name instead of repeating it', async () => {
    // The quote's `material_name` is the canonical catalog label and already
    // ends in `… · 2750×1830×16 mm`; a dimensions sub-line under it printed the
    // same figures twice on every row. Only a browser pass showed it — the unit
    // fixtures had invented short names that carried no size.
    setActivePinia(createPinia())
    const wrapper = mountSection()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('LDSP Egger H1334 · Sanoma · 2750×1830×18 mm')
    expect(text.match(/2750×1830×18/g) ?? []).toHaveLength(1)
  })
})

describe('CuttingResultsSection own material', () => {
  const OWNED_QUOTE = {
    material_lines: [
      {
        material_id: PANEL_A,
        material_name: 'LDSP Egger H1334 · Sanoma · 2750×1830×18 mm',
        panels_used: 5,
        own_panels: 3,
        unit_price_tiyin: 30_000_000,
        line_total_tiyin: 60_000_000,
      },
    ],
    edge_lines: [
      {
        material_id: EDGE_A,
        material_name: 'ABS H1334 · 0.4×19',
        consumed_mm: 13500,
        own: true,
        metre_price_tiyin: 500_000,
        material_cost_tiyin: 0,
        service_cost_tiyin: 1_350_000,
        line_total_tiyin: 1_350_000,
      },
      {
        material_id: EDGE_B,
        material_name: 'ABS Oq · 1×19',
        consumed_mm: 8000,
        own: false,
        metre_price_tiyin: 500_000,
        material_cost_tiyin: 4_000_000,
        service_cost_tiyin: 800_000,
        line_total_tiyin: 4_800_000,
      },
    ],
  }

  it('charges only the sheets the workshop supplies, and says which is which', async () => {
    setActivePinia(createPinia())
    const wrapper = mountSection({ quote: OWNED_QUOTE as never, scope: 'workshop' })
    await flushPromises()

    const text = wrapper.text().replace(/\u00a0/g, ' ')
    expect(text).toContain('3 sizniki · 2 ustaxonadan')
    // The multiplication follows the charged count, not the layout total.
    expect(text).toContain('2 list × 300 000 = 600 000')
    expect(text).not.toContain('5 list × 300 000')
  })

  it('gives an own tape no arithmetic line at all', async () => {
    setActivePinia(createPinia())
    const wrapper = mountSection({ quote: OWNED_QUOTE as never, scope: 'workshop' })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain("o'z lentangiz — hisoblanmaydi")
    // Its banded length still shows: the client has to bring that much.
    expect(text).toContain('13.50 m')
  })

  it('states the saving under the total, since nothing else moves when you claim', async () => {
    setActivePinia(createPinia())
    const wrapper = mountSection({ quote: OWNED_QUOTE as never, scope: 'workshop' })
    await flushPromises()

    // 3 sheets × 300 000 = 900 000, plus the shop rate the free tape would have
    // cost (4 000 000 tiyin / 8000 mm × 13 500 mm = 67 500 so'm).
    expect(wrapper.text().replace(/\u00a0/g, ' ')).toContain('967 500')
  })

  it('renders none of the own-material furniture on an ordinary order', async () => {
    setActivePinia(createPinia())
    const wrapper = mountSection()
    await flushPromises()

    const text = wrapper.text()
    expect(text).not.toContain('sizniki')
    expect(text).not.toContain('hisoblanmaydi')
    expect(text).not.toContain('tejaldi')
  })

  it('opens the claim dialog from the card', async () => {
    setActivePinia(createPinia())
    const wrapper = mountSection({ scope: 'workshop' })
    await flushPromises()

    const opener = wrapper.findAll('button').find((b) => b.text() === "O'zim olib kelaman")
    expect(opener).toBeDefined()
  })
})

/**
 * The receipt prints «N лист» three times over — the material headline, the
 * multiplication under it, and the cutting service. All three used to call
 * `$t('cutting.unit.sheet')` with no count, so vue-i18n never reached the
 * plural rule and every Russian line read «2 лист». One line per Russian class
 * (1 → one, 2 → few, 5 → many) proves all three forms are now reachable.
 */
describe('CuttingResultsSection — Russian agrees the sheet unit with its count', () => {
  const RU_QUOTE = {
    panels_used: 8,
    subtotal_cutting_tiyin: 24_000_000,
    material_lines: [
      {
        material_id: PANEL_A,
        material_name: 'LDSP Egger H1334 · Sanoma · 2750×1830×18 mm',
        panels_used: 1,
        own_panels: 0,
        unit_price_tiyin: 30_000_000,
        line_total_tiyin: 30_000_000,
      },
      {
        material_id: PANEL_B,
        material_name: 'LDSP Kronospan W980 · Oq · 2800×2070×16 mm',
        panels_used: 2,
        own_panels: 0,
        unit_price_tiyin: 42_500_000,
        line_total_tiyin: 85_000_000,
      },
      {
        material_id: 'panel-c',
        material_name: 'MDF Oq · 2800×2070×16 mm',
        panels_used: 5,
        own_panels: 0,
        unit_price_tiyin: 20_000_000,
        line_total_tiyin: 100_000_000,
      },
    ],
    edge_lines: [],
  }

  afterEach(async () => {
    await setLocale(DEFAULT_LOCALE)
  })

  it('inflects the headline, the multiplication and the service line', async () => {
    setActivePinia(createPinia())
    await setLocale('ru')
    const wrapper = mountSection({ quote: RU_QUOTE as never })
    await flushPromises()

    const text = wrapper.text().replace(/ /g, ' ')
    // Material headlines: «— N лист/листа/листов».
    expect(text).toContain('— 1 лист')
    expect(text).toContain('— 2 листа')
    expect(text).toContain('— 5 листов')
    // The multiplication under each of them carries the same agreement.
    expect(text).toContain('1 лист × 300 000')
    expect(text).toContain('2 листа × 425 000')
    expect(text).toContain('5 листов × 200 000')
    // And the cutting service, which counts the whole layout.
    expect(text).toContain('8 листов × 30 000')
    // The first form must not leak onto a count that is not «one».
    expect(text).not.toContain('2 лист ')
    expect(text).not.toContain('5 лист ')
  })

  it('leaves Uzbek on its single form at every count', async () => {
    setActivePinia(createPinia())
    await setLocale('uz')
    const wrapper = mountSection({ quote: RU_QUOTE as never })
    await flushPromises()

    const text = wrapper.text().replace(/ /g, ' ')
    expect(text).toContain('— 1 list')
    expect(text).toContain('— 2 list')
    expect(text).toContain('— 5 list')
    expect(text).toContain('8 list × 30 000')
  })

  // uz-Cyrl is derived from uz, so it must show the same one form — Cyrillic
  // script, not Russian grammar.
  it('gives uz-Cyrl the same single transliterated form', async () => {
    setActivePinia(createPinia())
    await setLocale('uz-Cyrl')
    const wrapper = mountSection({ quote: RU_QUOTE as never })
    await flushPromises()

    const text = wrapper.text().replace(/ /g, ' ')
    expect(text).toContain('— 1 лист')
    expect(text).toContain('— 2 лист')
    expect(text).toContain('— 5 лист')
    expect(text).not.toContain('листа')
    expect(text).not.toContain('листов')
  })
})
