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
      branch: 'Mebel Master',
    },
    global: { stubs: { Icon: true, AuthFileImage: true, AppModal: true, ...sheetStub } },
  })
}

/** The board-type chips — the only radiogroup in the sheet. */
function chips(wrapper: ReturnType<typeof mountPicker>) {
  return wrapper.findAll('[role="radio"]')
}

function chip(wrapper: ReturnType<typeof mountPicker>, label: string) {
  return chips(wrapper).find((button) => button.text() === label)!
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

/**
 * The board-type filter (decision 27b). It cuts **formats**, not decors: the
 * same decor can be on the shelf as both an LDSP and an MDF board, and under
 * the MDF chip only its MDF formats are its formats.
 */
describe('CuttingMaterialPicker — the board-type filter', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  /** Dub Sonoma in two LDSP formats and one MDF; Oq in MDF; Qayin in fanera. */
  function shelf() {
    return [
      option({ id: 'm-18' }),
      option({ id: 'm-16', thickness_mm: '16', length_mm: 2750, width_mm: 1830 }),
      option({ id: 'm-mdf', type: 'mdf', thickness_mm: '16' }),
      option({ id: 'm-oq', type: 'mdf', code: 'W980', name: 'Oq' }),
      option({ id: 'm-qayin', type: 'fanera', code: 'F1', name: 'Qayin' }),
    ]
  }

  it('offers one chip per type on the shelf, boards first and the rest alphabetically', () => {
    const wrapper = mountPicker(shelf())

    expect(chips(wrapper).map((button) => button.text())).toEqual([
      'Barchasi',
      'LDSP',
      'MDF',
      'Fanera',
    ])
    expect(chips(wrapper)[0].attributes('aria-checked')).toBe('true')
  })

  it('stays out of the way when the branch carries one type', () => {
    const wrapper = mountPicker([
      option({ id: 'm-18' }),
      option({ id: 'm-16', thickness_mm: '16' }),
    ])

    expect(chips(wrapper)).toHaveLength(0)
  })

  it('narrows the decor list, and counts only the chosen type on the rows it keeps', async () => {
    const wrapper = mountPicker(shelf())

    await chip(wrapper, 'LDSP').trigger('click')

    const text = wrapper.text()
    expect(text).toContain('Dub Sonoma')
    // Three formats on the shelf, two of them LDSP — the row counts the filter's.
    expect(text).toContain('2 ta format')
    expect(text).not.toContain('Oq')
    expect(text).not.toContain('Qayin')
  })

  /**
   * The caption counts what is on screen. A branch total held over a narrowed
   * list reads as a broken list — the client counts three rows under a line
   * that promises four.
   */
  it('counts the decors the chip left, not the branch total', async () => {
    const wrapper = mountPicker(shelf())
    // Dub Sonoma, Oq, Qayin — the whole shelf folded by decor.
    expect(wrapper.text()).toContain('Mebel Master katalogi · 3 ta dekor')

    await chip(wrapper, 'MDF').trigger('click')
    // Dub Sonoma and Oq carry an MDF board; Qayin does not.
    expect(wrapper.text()).toContain('Mebel Master katalogi · 2 ta dekor')

    await chip(wrapper, 'Fanera').trigger('click')
    expect(wrapper.text()).toContain('Mebel Master katalogi · 1 ta dekor')

    // The search narrows the same count, and the chip still cuts what it hands
    // back: one Fanera hit under the Fanera chip.
    await wrapper.setProps({
      search: 'qayin',
      materials: [option({ id: 'm-qayin', type: 'fanera', code: 'F1', name: 'Qayin' })],
    })
    expect(wrapper.text()).toContain('Mebel Master katalogi · 1 ta dekor')
  })

  it('picks silently when the chip leaves a decor with a single format', async () => {
    const wrapper = mountPicker(shelf())

    await chip(wrapper, 'MDF').trigger('click')
    // Dub Sonoma is one MDF board now, so its row is that board — price and all.
    expect(wrapper.text()).toContain('16 mm · 2800×2070 mm')

    await buttonWith(wrapper, 'Dub Sonoma').trigger('click')

    expect(wrapper.emitted('pick')).toEqual([['m-mdf']])
  })

  /**
   * The search is the server's, so the parent hands down an already-narrowed
   * list; the chips must survive it (they are the shelf's, not the result's)
   * and keep cutting what is left.
   */
  it('composes with the search instead of replacing it', async () => {
    const wrapper = mountPicker(shelf())
    await chip(wrapper, 'MDF').trigger('click')

    await wrapper.setProps({
      search: 'oq',
      materials: [option({ id: 'm-oq', type: 'mdf', code: 'W980', name: 'Oq' })],
    })

    // Every chip the shelf offered is still there, and MDF is still armed.
    expect(chips(wrapper).map((button) => button.text())).toEqual([
      'Barchasi',
      'LDSP',
      'MDF',
      'Fanera',
    ])
    expect(chip(wrapper, 'MDF').attributes('aria-checked')).toBe('true')
    expect(wrapper.text()).toContain('Oq')

    // A query whose hits are all LDSP, with the MDF chip still armed: the two
    // filters compose to nothing, and that is the no-results empty, not the
    // branch-has-no-catalog one.
    await wrapper.setProps({ search: 'sonoma 18', materials: [option({ id: 'm-18' })] })
    expect(wrapper.text()).toContain("Bu so'rov bo'yicha material topilmadi.")
  })

  it('forgets the chip when the picker closes', async () => {
    const wrapper = mountPicker(shelf())
    await chip(wrapper, 'MDF').trigger('click')
    expect(wrapper.text()).not.toContain('Qayin')

    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })

    expect(chips(wrapper)[0].attributes('aria-checked')).toBe('true')
    expect(wrapper.text()).toContain('Qayin')
  })
})
