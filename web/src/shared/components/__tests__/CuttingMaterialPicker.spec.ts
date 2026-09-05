import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import CuttingMaterialPicker from '@/shared/components/CuttingMaterialPicker.vue'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

// `CuttingBottomSheet` teleports to <body>, which puts its content outside the
// wrapper's tree. A transparent stub keeps the frame's contract (open, slots)
// while leaving the picker's own markup where the wrapper can read it; the
// sheet's focus trap and scroll lock are its component's business, not this
// one's.
const sheetStub = {
  CuttingBottomSheet: {
    props: ['open', 'title'],
    template: `<section v-if="open">
      <h2>{{ title }}</h2><slot name="pinned" /><slot /><slot name="foot" />
    </section>`,
  },
}

function option(overrides: Partial<ClientCatalogMaterialOption> = {}) {
  return {
    id: 'm-1',
    type: 'ldsp',
    manufacturer_id: 'mfr-1',
    manufacturer_name: 'Egger',
    code: 'H1334',
    name: 'Dub Sonoma',
    has_grain: true,
    image_file_id: null,
    thickness_mm: '18',
    length_mm: 2800,
    width_mm: 2070,
    tape_width_mm: null,
    price_tiyin: 28_500_000,
    price_unset: false,
    display_unit: 'list',
    ...overrides,
  } as ClientCatalogMaterialOption
}

function mountPicker(materials: ClientCatalogMaterialOption[], currentId: string | null = null) {
  return mount(CuttingMaterialPicker, {
    attachTo: document.body,
    props: {
      open: true,
      materials,
      loading: false,
      currentId,
      search: '',
      caption: 'Mebel Master katalogi · 2 ta dekor',
    },
    global: { stubs: { Icon: true, AuthFileImage: true, AppModal: true, ...sheetStub } },
  })
}

/** The button carrying a decor's or a format's own text. Looked up by copy
 *  rather than by index: the thumbnail beside a decor is a button only when the
 *  decor has an image, so positions shift with the fixture. */
function buttonWith(wrapper: ReturnType<typeof mountPicker>, text: string) {
  return wrapper.findAll('button').find((button) => button.text().includes(text))!
}

describe('CuttingMaterialPicker (spec §7.3)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  it('folds the branch catalog into one row per decor', () => {
    const wrapper = mountPicker([
      option({ id: 'm-18' }),
      option({ id: 'm-16', thickness_mm: '16', length_mm: 2750, width_mm: 1830 }),
      option({ id: 'm-oq', code: 'W980', name: 'Oq' }),
    ])

    const text = wrapper.text()
    // The identity line appears once per decor, not once per format.
    expect(text.match(/Dub Sonoma/g) ?? []).toHaveLength(1)
    expect(text).toContain('Oq')
  })

  it('prices a single-format decor on its own row, and names the format', () => {
    const wrapper = mountPicker([option({ id: 'm-18' })])

    const text = wrapper.text().replace(/ /g, ' ')
    expect(text).toContain('18 mm · 2800×2070 mm')
    expect(text).toContain("285 000 so'm")
    expect(text).toContain('/ list')
  })

  it('picks a single-format decor in one click', async () => {
    const wrapper = mountPicker([option({ id: 'm-18' })])

    await buttonWith(wrapper, 'Dub Sonoma').trigger('click')

    expect(wrapper.emitted('pick')).toEqual([['m-18']])
  })

  /**
   * The rule the whole component turns on: **the price is the format's, never
   * the decor's**. With two formats there is no single number the decor row
   * could honestly print, so it prints none and the formats carry their own.
   */
  it('prices the formats, not the decor, when the branch carries several', async () => {
    const wrapper = mountPicker([
      option({ id: 'm-18', price_tiyin: 28_500_000 }),
      option({
        id: 'm-16',
        thickness_mm: '16',
        length_mm: 2750,
        width_mm: 1830,
        price_tiyin: 24_100_000,
      }),
    ])

    // The decor row says how many formats there are and nothing about money.
    expect(wrapper.text()).toContain('2 ta format')

    await buttonWith(wrapper, 'Dub Sonoma').trigger('click')

    const text = wrapper.text().replace(/ /g, ' ')
    expect(text).toContain('18 mm · 2800×2070 mm')
    expect(text).toContain("285 000 so'm")
    expect(text).toContain('16 mm · 2750×1830 mm')
    expect(text).toContain("241 000 so'm")
    expect(wrapper.emitted('pick')).toBeUndefined()
  })

  it('selects a multi-format decor only once a format row is chosen', async () => {
    const wrapper = mountPicker([
      option({ id: 'm-18' }),
      option({ id: 'm-16', thickness_mm: '16' }),
    ])

    await buttonWith(wrapper, 'Dub Sonoma').trigger('click')
    // The decor itself is not selected by opening it — only a format row is.
    expect(wrapper.emitted('pick')).toBeUndefined()

    await buttonWith(wrapper, '16 mm').trigger('click')

    expect(wrapper.emitted('pick')?.[0]).toEqual(['m-16'])
  })

  it('opens the decor already holding the current format, so its radio is visible', () => {
    const wrapper = mountPicker(
      [option({ id: 'm-18' }), option({ id: 'm-16', thickness_mm: '16' })],
      'm-16',
    )

    // Expanded on open: both format rows are on screen without a tap.
    expect(wrapper.text()).toContain('16 mm')
    expect(wrapper.text()).toContain('18 mm')
  })

  it('says which empty it is — no catalog, or nothing matching the query', async () => {
    const empty = mountPicker([])
    expect(empty.text()).toContain('Bu filialda list materiali topilmadi.')

    await empty.setProps({ search: 'sonoma' })
    expect(empty.text()).toContain("Bu so'rov bo'yicha material topilmadi.")
  })
})
