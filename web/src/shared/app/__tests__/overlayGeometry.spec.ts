import { afterEach, describe, expect, it } from 'vitest'

import { overlayRect, overlayViewport, overlayZoom } from '@/shared/app/overlayGeometry'

// Regression guard for the desktop `zoom: 90%` root: a spotlight/popover
// positioned straight from client-space numbers renders at 90% of its anchor's
// position, which put an invisible click-blocker over the very button the
// onboarding hint told the owner to press.

function setZoom(zoom: number | undefined) {
  if (zoom === undefined) {
    delete (document.documentElement as { currentCSSZoom?: number }).currentCSSZoom
    return
  }
  Object.defineProperty(document.documentElement, 'currentCSSZoom', {
    value: zoom,
    configurable: true,
  })
}

function anchorAt(box: { top: number; left: number; width: number; height: number }) {
  const element = document.createElement('div')
  element.getBoundingClientRect = () =>
    ({
      top: box.top,
      left: box.left,
      right: box.left + box.width,
      bottom: box.top + box.height,
      width: box.width,
      height: box.height,
    }) as DOMRect
  return element
}

afterEach(() => setZoom(undefined))

describe('overlayZoom', () => {
  it('falls back to 1 where the engine reports no zoom', () => {
    setZoom(undefined)
    expect(overlayZoom()).toBe(1)
  })

  it('ignores a nonsensical zero zoom rather than dividing by it', () => {
    setZoom(0)
    expect(overlayZoom()).toBe(1)
  })
})

describe('overlayRect', () => {
  it('scales a painted client rect up into overlay space', () => {
    setZoom(0.9)
    expect(overlayRect(anchorAt({ top: 270, left: 180, width: 135, height: 36 }))).toEqual({
      top: 300,
      left: 200,
      right: 350,
      bottom: 340,
      width: 150,
      height: 40,
    })
  })

  it('leaves the rect untouched when the page is unzoomed', () => {
    setZoom(1)
    expect(overlayRect(anchorAt({ top: 270, left: 180, width: 135, height: 36 }))).toMatchObject({
      top: 270,
      left: 180,
    })
  })
})

describe('overlayViewport', () => {
  it('reports the room an overlay actually has in its own units', () => {
    setZoom(0.9)
    window.innerWidth = 1280
    window.innerHeight = 800
    const viewport = overlayViewport()
    expect(viewport.width).toBeCloseTo(1422.22, 1)
    expect(viewport.height).toBeCloseTo(888.89, 1)
  })
})
