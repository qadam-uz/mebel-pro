import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, h, ref, shallowRef, type Ref } from 'vue'

import {
  OVERLAY_BASE_Z,
  OVERLAY_MAX_Z,
  OVERLAY_STEP_Z,
  openOverlayCount,
  resetOverlayStack,
  useAttachedOverlayZIndex,
  useOverlayLayer,
} from '@/shared/app/overlayStack'

/**
 * The stack itself, away from any component.
 *
 * What it has to guarantee is narrow and easy to break by accident: the tier an
 * overlay gets is its **nesting depth**, the innermost one owns Escape, and a
 * closed or unmounted overlay leaves no slot behind — a leak would push every
 * later overlay one tier up until the app is reloaded.
 */

/**
 * Mount a component that registers one overlay driven by `open`.
 *
 * `shallowRef`, not `ref`: a deep ref would make the returned object reactive
 * and unwrap the computeds inside it, so `layer.zIndex.value` would read
 * `undefined` off a plain number.
 */
function mountOverlay(open: Ref<boolean>) {
  const layer = shallowRef<ReturnType<typeof useOverlayLayer> | null>(null)
  const wrapper = mount(
    defineComponent({
      setup() {
        layer.value = useOverlayLayer(open)
        return () => h('div')
      },
    }),
  )
  return { wrapper, layer: layer.value! }
}

afterEach(() => {
  resetOverlayStack()
})

describe('overlay stack', () => {
  it('gives each overlay a tier from its nesting depth', async () => {
    const outer = ref(true)
    const inner = ref(false)
    const top = ref(false)
    const a = mountOverlay(outer)
    const b = mountOverlay(inner)
    const c = mountOverlay(top)

    expect(a.layer.zIndex.value).toBe(OVERLAY_BASE_Z)

    inner.value = true
    await Promise.resolve()
    expect(b.layer.zIndex.value).toBe(OVERLAY_BASE_Z + OVERLAY_STEP_Z)

    top.value = true
    await Promise.resolve()
    expect(c.layer.zIndex.value).toBe(OVERLAY_BASE_Z + OVERLAY_STEP_Z * 2)
    // The tiers are strictly increasing outward-in, which is the whole point:
    // nesting order decides, not the order the `Teleport` anchors were created.
    expect(a.layer.zIndex.value).toBeLessThan(b.layer.zIndex.value)
    expect(b.layer.zIndex.value).toBeLessThan(c.layer.zIndex.value)

    a.wrapper.unmount()
    b.wrapper.unmount()
    c.wrapper.unmount()
  })

  it('gives Escape to the innermost overlay only', async () => {
    const outer = ref(true)
    const inner = ref(false)
    const a = mountOverlay(outer)
    const b = mountOverlay(inner)

    expect(a.layer.isTopmost.value).toBe(true)

    inner.value = true
    await Promise.resolve()
    expect(a.layer.isTopmost.value).toBe(false)
    expect(b.layer.isTopmost.value).toBe(true)

    // Closing the inner one hands ownership back rather than leaving nobody.
    inner.value = false
    await Promise.resolve()
    expect(a.layer.isTopmost.value).toBe(true)

    a.wrapper.unmount()
    b.wrapper.unmount()
  })

  it('releases its slot on close and on unmount', async () => {
    const open = ref(true)
    const first = mountOverlay(open)
    expect(openOverlayCount()).toBe(1)

    open.value = false
    await Promise.resolve()
    expect(openOverlayCount()).toBe(0)

    open.value = true
    await Promise.resolve()
    expect(openOverlayCount()).toBe(1)
    first.wrapper.unmount()
    expect(openOverlayCount()).toBe(0)

    // …and the next overlay starts from the modal layer again, not from a tier
    // inflated by the ones before it.
    const next = mountOverlay(ref(true))
    expect(next.layer.zIndex.value).toBe(OVERLAY_BASE_Z)
    next.wrapper.unmount()
  })

  it('caps the ladder below the toast layer', () => {
    const mounted = Array.from({ length: 40 }, () => mountOverlay(ref(true)))
    expect(mounted[mounted.length - 1]!.layer.zIndex.value).toBe(OVERLAY_MAX_Z)
    for (const item of mounted) item.wrapper.unmount()
  })

  it('lifts an attached popover over the innermost overlay, never below its base', async () => {
    const open = ref(false)
    const attached = shallowRef<ReturnType<typeof useAttachedOverlayZIndex> | null>(null)
    const host = mount(
      defineComponent({
        setup() {
          attached.value = useAttachedOverlayZIndex(60)
          return () => h('div')
        },
      }),
    )
    // Nothing open: the popover keeps the tier its own CSS class declares.
    expect(attached.value!.value).toBe(60)

    const overlay = mountOverlay(open)
    open.value = true
    await Promise.resolve()
    // Over its host, and still under anything that host raises.
    expect(attached.value!.value).toBe(OVERLAY_BASE_Z + 4)
    expect(attached.value!.value).toBeLessThan(OVERLAY_BASE_Z + OVERLAY_STEP_Z)

    overlay.wrapper.unmount()
    host.unmount()
  })
})
