import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ClientChipFilter from '@/apps/client/components/ClientChipFilter.vue'

const options = [
  { value: 'all', label: 'Hammasi' },
  { value: 'active', label: 'Faol' },
  { value: 'ready', label: 'Tayyor' },
  { value: 'completed', label: 'Yakunlangan' },
  { value: 'cancelled', label: 'Bekor' },
]

/**
 * jsdom has no layout, so the row's geometry is stubbed. The numbers are the
 * ones a 375px phone actually produces (measured): a 299px viewport onto a
 * 412px row — five status chips do not fit, which is the case the fade exists
 * for.
 */
function stubGeometry(row: Element, { scrollWidth = 412, clientWidth = 299, scrollLeft = 0 } = {}) {
  Object.defineProperty(row, 'scrollWidth', { value: scrollWidth, configurable: true })
  Object.defineProperty(row, 'clientWidth', { value: clientWidth, configurable: true })
  Object.defineProperty(row, 'scrollLeft', {
    value: scrollLeft,
    writable: true,
    configurable: true,
  })
}

async function mountRow(modelValue = 'all', geometry = {}) {
  const view = mount(ClientChipFilter, {
    props: { label: 'Holat', modelValue, options },
    attachTo: document.body,
  })
  stubGeometry(view.element, geometry)
  view.element.dispatchEvent(new Event('scroll'))
  await flushPromises()
  return view
}

describe('ClientChipFilter — the scroll affordance', () => {
  it('fades only the overflowing side at the start of the row', async () => {
    const view = await mountRow('all')

    const mask = view.attributes('style') ?? ''
    // Content runs off to the right, so the right edge fades and the left does not.
    expect(mask).toContain('calc(100% - 24px)')
    expect(mask).not.toContain('transparent 0')
  })

  it('flips the fade to the left once the row is scrolled to the end', async () => {
    const view = await mountRow('all')
    ;(view.element as HTMLElement).scrollLeft = 113
    view.element.dispatchEvent(new Event('scroll'))
    await flushPromises()

    const mask = view.attributes('style') ?? ''
    expect(mask).toContain('transparent 0')
    expect(mask).not.toContain('calc(100% - 24px)')
  })

  it('fades nothing when every chip already fits', async () => {
    const view = await mountRow('all', { scrollWidth: 280, clientWidth: 299 })

    expect(view.attributes('style') ?? '').not.toContain('linear-gradient')
  })

  it('keeps the checked chip reachable by one tab stop, the rest by arrows', async () => {
    const view = await mountRow('cancelled')

    const chips = view.findAll('[role="radio"]')
    expect(chips.map((chip) => chip.attributes('tabindex'))).toEqual(['-1', '-1', '-1', '-1', '0'])
    expect(chips[4].attributes('aria-checked')).toBe('true')

    await view.trigger('keydown', { key: 'Home' })
    expect(view.emitted('update:modelValue')?.[0]).toEqual(['all'])
  })
})
