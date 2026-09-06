import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { groupTapeDecors } from '@/shared/app/cuttingGroupTape'
import CuttingTapePicker from '@/shared/components/CuttingTapePicker.vue'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

// Same transparent stub as the material picker's spec: `CuttingBottomSheet`
// teleports to <body>, which would take the picker's markup out of the wrapper.
const sheetStub = {
  CuttingBottomSheet: {
    props: ['open', 'title'],
    template: `<section v-if="open">
      <h2>{{ title }}</h2><slot name="pinned" /><slot /><slot name="foot" />
    </section>`,
  },
}

function tape(overrides: Partial<ClientCatalogMaterialOption> = {}) {
  return {
    id: 'tape-1',
    type: 'kromka',
    manufacturer_id: 'mfr-1',
    manufacturer_name: 'Egger',
    code: 'H1145',
    name: 'Sonoma eman',
    has_grain: false,
    image_file_id: null,
    thickness_mm: '0.4',
    length_mm: null,
    width_mm: null,
    tape_width_mm: 22,
    price_tiyin: 120_000,
    price_unset: false,
    display_unit: 'm',
    ...overrides,
  } as ClientCatalogMaterialOption
}

/** Three decors of the spec's own fixture, one of them in two thicknesses. */
const CATALOG = [
  tape(),
  tape({ id: 'tape-1b', thickness_mm: '2', price_tiyin: 260_000 }),
  tape({
    id: 'tape-2',
    manufacturer_id: 'mfr-2',
    manufacturer_name: 'Kronospan',
    code: 'W980',
    name: 'Oq',
  }),
  tape({
    id: 'tape-3',
    code: 'H3734',
    name: "Yong'oq",
  }),
]

function mountPicker(materials = CATALOG) {
  return mount(CuttingTapePicker, {
    attachTo: document.body,
    props: {
      open: true,
      decors: groupTapeDecors(materials),
      panel: tape({ id: 'panel-1', type: 'ldsp', name: 'Sonoma eman', thickness_mm: '18' }),
      panelImageFileId: null,
      currentKey: null,
      caption: 'Mebel Master · 3 ta kromka dekori',
    },
    global: { stubs: { Icon: true, AuthFileImage: true, CuttingDecorThumb: true, ...sheetStub } },
  })
}

/** The decor labels on screen, in render order. */
function labels(wrapper: ReturnType<typeof mountPicker>) {
  return wrapper.findAll('[role="radio"]').map((row) => row.find('span > span').text())
}

async function type(wrapper: ReturnType<typeof mountPicker>, query: string) {
  const input = wrapper.get('#cutting-tape-picker-search')
  await input.setValue(query)
}

describe('CuttingTapePicker — smart search (SPEC_CATALOG_SMART_SEARCH §2)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  it('lists every decor with no query, one row per decor', () => {
    const wrapper = mountPicker()
    expect(labels(wrapper)).toEqual([
      'Egger H1145 · Sonoma eman',
      'Kronospan W980 · Oq',
      "Egger H3734 · Yong'oq",
    ])
  })

  it('finds a Latin decor from a Cyrillic query (tier 1)', async () => {
    const wrapper = mountPicker()
    await type(wrapper, 'сонома')
    expect(labels(wrapper)).toEqual(['Egger H1145 · Sonoma eman'])
    await type(wrapper, 'ёнғоқ')
    expect(labels(wrapper)).toEqual(["Egger H3734 · Yong'oq"])
    await type(wrapper, 'эггер сонома')
    expect(labels(wrapper)).toEqual(['Egger H1145 · Sonoma eman'])
  })

  it('finds a query typed under the wrong keyboard layout (tier 2)', async () => {
    const wrapper = mountPicker()
    await type(wrapper, 'Ыщтщьф')
    expect(labels(wrapper)).toEqual(['Egger H1145 · Sonoma eman'])
  })

  it('finds a decor through a typo (tier 3)', async () => {
    const wrapper = mountPicker()
    await type(wrapper, 'sanoma')
    expect(labels(wrapper)).toEqual(['Egger H1145 · Sonoma eman'])
  })

  it('ranks a word start above a match inside a word', async () => {
    const wrapper = mountPicker([
      ...CATALOG,
      tape({ id: 'tape-4', code: 'U963', name: 'Ison tus', manufacturer_name: 'Egger' }),
    ])
    await type(wrapper, 'son')
    // «Sonoma» starts with the query; «Ison tus» only contains it.
    expect(labels(wrapper)).toEqual(['Egger H1145 · Sonoma eman', 'Egger U963 · Ison tus'])
  })

  it('puts the row whose code the query is first', async () => {
    const wrapper = mountPicker([
      tape({ id: 'tape-9', code: 'K512', name: 'Retro h1145 tus' }),
      tape(),
    ])
    await type(wrapper, 'h1145')
    expect(labels(wrapper)).toEqual(['Egger H1145 · Sonoma eman', 'Egger K512 · Retro h1145 tus'])
  })

  it('keeps the thickness search the list always had', async () => {
    const wrapper = mountPicker()
    await type(wrapper, '0.4')
    expect(labels(wrapper).length).toBe(3)
    await type(wrapper, 'kromka egger')
    expect(labels(wrapper)).toEqual(['Egger H1145 · Sonoma eman', "Egger H3734 · Yong'oq"])
  })

  it('says so when nothing matches, and keeps the board colour pinned', async () => {
    const wrapper = mountPicker()
    await type(wrapper, 'zzzz')
    expect(wrapper.findAll('[role="radio"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('Mos kromka topilmadi')
    // «Plita rangi» is above the search, not in the list: it survives any query.
    expect(wrapper.text()).toContain('Plita rangi')
    expect(wrapper.text()).toContain('LDSP Egger H1145 · Sonoma eman')
  })
})
