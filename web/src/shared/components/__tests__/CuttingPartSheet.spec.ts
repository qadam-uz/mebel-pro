import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import CuttingPartSheet from '@/shared/components/CuttingPartSheet.vue'
import { DEFAULT_LOCALE, setLocale } from '@/shared/i18n'
import type { CuttingPart } from '@/shared/stores/cutting'

function part(quantity: number): CuttingPart {
  return {
    part_ref: 'part-a',
    name: null,
    material_id: 'panel-a',
    material_source: 'shop',
    follow_grain: true,
    thickened: false,
    length_mm: 300,
    width_mm: 200,
    quantity,
    edge_top: null,
    edge_bottom: null,
    edge_left: null,
    edge_right: null,
  } as unknown as CuttingPart
}

let wrapper: VueWrapper | null = null

/**
 * The unit caption under «Soni». The sheet teleports to `<body>`, so the
 * captions are not in the wrapper's own subtree; the three numeric fields
 * (Uzunlik · Kenglik · Soni) each carry one, and Soni's is the last.
 */
function quantityCaption(quantity: number): string {
  wrapper = mount(CuttingPartSheet, {
    props: {
      open: true,
      part: part(quantity),
      index: 0,
      displayIndex: 0,
      decor: null,
      selectedThicknessMm: null,
      foreignTapeLabel: () => '',
    },
    global: { stubs: { Icon: true, ActionMenu: true, CuttingEdgeSides: true } },
    attachTo: document.body,
  })
  const captions = [...document.querySelectorAll('span.mt-1.block.text-center')]
  return captions[captions.length - 1]?.textContent?.trim() ?? ''
}

afterEach(async () => {
  wrapper?.unmount()
  wrapper = null
  await setLocale(DEFAULT_LOCALE)
})

/**
 * «Soni» carries its unit caption directly under the number the operator typed,
 * so in Russian the caption has to agree with it. It used to call
 * `$t('cutting.unit.piece')` with no count, which never reaches the plural rule
 * — «штука» printed under every quantity, including 5.
 */
describe('CuttingPartSheet — the quantity caption agrees with the quantity', () => {
  it.each([
    [1, 'штука'],
    [2, 'штуки'],
    [5, 'штук'],
  ])('renders a quantity of %i as «%s» in Russian', async (quantity, expected) => {
    await setLocale('ru')

    expect(quantityCaption(quantity)).toBe(expected)
  })

  it.each([1, 2, 5])('leaves the single Uzbek form alone at a quantity of %i', async (quantity) => {
    await setLocale('uz')

    expect(quantityCaption(quantity)).toBe('dona')
  })

  // uz-Cyrl is transliterated from uz, so it keeps that one form.
  it.each([1, 2, 5])('gives uz-Cyrl the same single form at %i', async (quantity) => {
    await setLocale('uz-Cyrl')

    expect(quantityCaption(quantity)).toBe('дона')
  })
})
