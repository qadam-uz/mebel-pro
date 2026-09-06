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
function mountSheet(quantity = 1, deletable = true) {
  wrapper = mount(CuttingPartSheet, {
    props: {
      open: true,
      part: part(quantity),
      index: 0,
      displayIndex: 0,
      decor: null,
      selectedThicknessMm: null,
      foreignTapeLabel: () => '',
      deletable,
    },
    global: { stubs: { Icon: true, CuttingEdgeSides: true } },
    attachTo: document.body,
  })
  return wrapper
}

function quantityCaption(quantity: number): string {
  mountSheet(quantity)
  const captions = [...document.querySelectorAll('span.mt-1.block.text-center')]
  return captions[captions.length - 1]?.textContent?.trim() ?? ''
}

function deleteButton(): HTMLElement | null {
  return (
    [...document.querySelectorAll<HTMLElement>('[role="dialog"] button')].find((button) =>
      button.textContent?.includes("Detalni o'chirish"),
    ) ?? null
  )
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

/**
 * Decision 27(c). The ⋯ that used to carry «O'chirish» is gone — its teleported
 * panel painted under the sheet's own layer, so on a phone the trigger opened
 * onto nothing. The action is a button at the end of the form instead, and only
 * a row the list already shows can be deleted.
 */
describe("CuttingPartSheet — «Detalni o'chirish» replaces the head ⋯", () => {
  it('carries no action menu in the head', () => {
    mountSheet()

    expect(document.querySelector('[role="dialog"] .mp-action-menu-wrap')).toBeNull()
  })

  it('emits delete from the form button for an existing part', async () => {
    const sheet = mountSheet(1, true)
    const button = deleteButton()

    expect(button).not.toBeNull()
    button?.click()
    await sheet.vm.$nextTick()

    expect(sheet.emitted('delete')).toHaveLength(1)
  })

  it('offers no delete for a part the sheet has just created', () => {
    mountSheet(1, false)

    expect(deleteButton()).toBeNull()
  })
})
