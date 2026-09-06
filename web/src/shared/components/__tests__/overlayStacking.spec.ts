import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'

import { api } from '@/shared/api/client'
import { resetOverlayStack } from '@/shared/app/overlayStack'
import CuttingBottomSheet from '@/shared/components/CuttingBottomSheet.vue'
import CuttingDecorThumb from '@/shared/components/CuttingDecorThumb.vue'

vi.mock('@/shared/api/client', () => ({
  api: { blob: vi.fn() },
  apiTraceId: () => null,
  withQuery: (path: string) => path,
}))

/**
 * The production bug this file exists for: **the decor lightbox opened behind
 * the tape picker that raised it.**
 *
 * Every overlay here teleports to `<body>`, so two on the same tier tie and the
 * tie goes to the order their `Teleport` anchors were created. The tape picker
 * carried a hand-set "raised" tier to beat the «Detal» sheet; the lightbox
 * inside it — a plain `AppModal` at the flat modal tier — had no way to beat
 * *that*, so it painted underneath, invisible and focus-trapped. A phone user
 * tapping a decor thumbnail saw nothing happen and could not get out.
 *
 * Asserting on the classes would not have caught it (both were valid tiers),
 * and jsdom has no stacking context to observe, so what this pins is the
 * relation the browser actually resolves: the **numbers each overlay ends up
 * with**, in nesting order, plus who answers Escape and where focus lands.
 */

/** The «Detal» sheet, with the tape picker's sheet and a decor thumb inside. */
const Nested = defineComponent({
  components: { CuttingBottomSheet, CuttingDecorThumb },
  setup() {
    const outerOpen = ref(true)
    const innerOpen = ref(true)
    return { outerOpen, innerOpen }
  },
  template: `
    <CuttingBottomSheet :open="outerOpen" title="Detal #1" @close="outerOpen = false">
      <p>part fields</p>
    </CuttingBottomSheet>
    <CuttingBottomSheet :open="innerOpen" title="Kromka" @close="innerOpen = false">
      <CuttingDecorThumb file-id="file-a" label="Egger H1137" />
    </CuttingBottomSheet>
  `,
})

/** Every open overlay's fixed root, in the order they were teleported. */
function overlayRoots(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>('section[role="dialog"]')].map((panel) => {
    const root = panel.parentElement
    if (!root) throw new Error('a dialog rendered without its fixed root')
    return root
  })
}

function zOf(root: HTMLElement): number {
  return Number(root.style.zIndex)
}

/** The fixed root of the dialog whose heading is `title`. */
function rootTitled(title: string): HTMLElement {
  const root = dialogTitled(title).parentElement
  if (!root) throw new Error(`the dialog titled ${title} rendered without its fixed root`)
  return root
}

function dialogTitled(title: string): HTMLElement {
  const hit = [...document.querySelectorAll<HTMLElement>('section[role="dialog"]')].find((panel) =>
    panel.querySelector('h2')?.textContent?.includes(title),
  )
  if (!hit) throw new Error(`no open dialog titled ${title}`)
  return hit
}

/**
 * Tap the decor thumbnail in the tape picker's list.
 *
 * `.mp-scroll` scopes it to the sheet's scrolling body — the first `<button>`
 * in the panel is the header's close control, and clicking that closes the
 * picker instead of opening anything.
 */
function openLightbox(): HTMLButtonElement {
  const thumb = dialogTitled('Kromka').querySelector<HTMLButtonElement>('.mp-scroll button')
  if (!thumb) throw new Error('the decor thumbnail did not render')
  thumb.focus()
  thumb.click()
  return thumb
}

function pressEscape() {
  const target = document.activeElement ?? document.body
  target.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
}

describe('overlay stacking — the decor lightbox over the sheets that raise it', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.blob).mockReset()
    vi.mocked(api.blob).mockResolvedValue(new Blob(['x']))
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:test'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  })

  afterEach(() => {
    document.body.innerHTML = ''
    resetOverlayStack()
  })

  it('paints the lightbox above the picker, which is above the sheet under it', async () => {
    const wrapper = mount(Nested, {
      global: { stubs: { Icon: true } },
      attachTo: document.body,
    })
    await flushPromises()

    const sheet = rootTitled('Detal #1')
    const picker = rootTitled('Kromka')
    expect(zOf(sheet)).toBeLessThan(zOf(picker))

    openLightbox()
    await flushPromises()

    expect(overlayRoots()).toHaveLength(3)
    const lightbox = rootTitled('Egger H1137')
    expect(zOf(lightbox)).toBeGreaterThan(zOf(picker))
    expect(zOf(lightbox)).toBeGreaterThan(zOf(sheet))

    wrapper.unmount()
  })

  it('closes the lightbox on Escape and leaves the picker open, focus back on the thumb', async () => {
    const wrapper = mount(Nested, {
      global: { stubs: { Icon: true } },
      attachTo: document.body,
    })
    await flushPromises()

    const thumb = openLightbox()
    await flushPromises()
    expect(overlayRoots()).toHaveLength(3)

    pressEscape()
    await flushPromises()

    // Only the innermost overlay answered: both sheets are still open.
    expect(overlayRoots()).toHaveLength(2)
    expect(dialogTitled('Kromka')).not.toBeNull()
    expect(dialogTitled('Detal #1')).not.toBeNull()
    expect(document.activeElement).toBe(thumb)

    // …and the next Escape is the picker's, not the sheet's under it.
    pressEscape()
    await flushPromises()
    expect(overlayRoots()).toHaveLength(1)
    expect(dialogTitled('Detal #1')).not.toBeNull()

    wrapper.unmount()
  })
})
