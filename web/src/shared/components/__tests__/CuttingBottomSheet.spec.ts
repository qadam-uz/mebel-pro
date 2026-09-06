import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import CuttingBottomSheet from '@/shared/components/CuttingBottomSheet.vue'

/**
 * The phone sheet's frame, guarded structurally.
 *
 * The bug this file exists for: the grab handle and the `<header>` both claimed
 * `row-start-1` of a `grid-rows-[auto_minmax(0,1fr)_auto]` with **no explicit
 * column**, so auto-placement pushed the header into an implicit *second*
 * column. Body and foot stayed in column 1, which collapsed to roughly half the
 * screen — narrow left column, title floated right, close button off the edge,
 * foot buttons on top of each other.
 *
 * jsdom has no layout engine, so `getBoundingClientRect()` and a resolved
 * `grid-template-columns` are both zeroes here — asserting on them would pass
 * against the broken markup too. What is assertable, and what actually
 * regressed, is the *placement declaration*: one explicit column track, and one
 * distinct explicit row per region. Keep both and the browser cannot open an
 * implicit column; drop either and this fails.
 */

let wrapper: VueWrapper | null = null

function mountSheet(props: Record<string, unknown> = {}) {
  wrapper = mount(CuttingBottomSheet, {
    props: { open: true, title: 'Detal #1', ...props },
    slots: { default: '<p>body</p>', foot: '<button type="button">Saqlash</button>' },
    global: { stubs: { Icon: true } },
    attachTo: document.body,
  })
  const section = document.querySelector<HTMLElement>('section[role="dialog"]')
  if (!section) throw new Error('the sheet did not render')
  return section
}

/** The `row-start-N` / `col-start-N` a region declares, or null when it auto-places. */
function placement(el: Element, axis: 'row' | 'col'): number | null {
  const hit = [...el.classList].find((name) => name.startsWith(`${axis}-start-`))
  return hit ? Number(hit.slice(`${axis}-start-`.length)) : null
}

/** Make the component's own `(min-width: 768px)` probe report a wide viewport. */
function pretendWide() {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: true,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  )
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('CuttingBottomSheet frame', () => {
  it('lays the phone sheet out in one column, one region per row', () => {
    const section = mountSheet()

    expect(section.classList).toContain('grid-cols-[minmax(0,1fr)]')

    const handle = section.querySelector('[aria-hidden="true"]')
    const header = section.querySelector('header')
    const body = section.querySelector('.mp-scroll')?.parentElement
    const foot = section.querySelector('button[type="button"]:not([aria-label])')?.parentElement

    expect(handle).not.toBeNull()
    expect(header).not.toBeNull()
    expect(body).not.toBeNull()
    expect(foot).not.toBeNull()

    // Every region on the same left edge: column 1, explicitly.
    for (const region of [handle!, header!, body!, foot!]) {
      expect(placement(region, 'col')).toBe(1)
    }

    // …and each in a row of its own, in reading order. A shared row is what
    // opened the implicit second column.
    const rows = [handle!, header!, body!, foot!].map((region) => placement(region, 'row'))
    expect(rows).toEqual([1, 2, 3, 4])
    expect(new Set(rows).size).toBe(rows.length)

    // The row template has to have a track for each of them, with the body the
    // only one that flexes.
    const template = [...section.classList].find((name) => name.startsWith('grid-rows-'))
    expect(template).toBe('grid-rows-[auto_auto_minmax(0,1fr)_auto]')
  })

  it('keeps the anchored popover to a single column too', () => {
    pretendWide()
    const anchor = document.createElement('button')
    document.body.append(anchor)
    const section = mountSheet({ anchor })

    // It really is the popover frame, not the sheet falling through.
    expect(section.getAttribute('aria-modal')).toBeNull()
    expect(section.classList).toContain('grid-cols-[minmax(0,1fr)]')

    const rows = [
      section.querySelector('header')!,
      section.querySelector('.mp-scroll')!.parentElement!,
      section.querySelector('button[type="button"]:not([aria-label])')!.parentElement!,
    ].map((region) => placement(region, 'row'))
    expect(rows).toEqual([1, 2, 3])
  })
})
