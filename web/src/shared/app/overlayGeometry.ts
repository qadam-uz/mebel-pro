// Client-space → overlay-space geometry.
//
// The app paints desktop at `zoom: 90%` on the root (see `assets/main.css`).
// Zoom scales how a box *paints* but not how it *lays out*, and the DOM reports
// the two in different units:
//
//   - `getBoundingClientRect()`, `window.inner*` and `visualViewport` are in
//     painted viewport pixels — the same space pointer events live in.
//   - `offsetWidth` / `offsetHeight` and any `top`/`left` written into a style
//     are in local layout pixels, which the browser then scales by the zoom.
//
// So a fixed overlay handed a measured `rect.top` of 270 renders at 243 — every
// rect-positioned layer lands 10% off its anchor, and an overlay meant to sit
// beside a control ends up on top of it. Convert measurements to overlay space
// once, at the point of measurement, and the rest of the math stays in one unit.

export interface OverlayRect {
  top: number
  left: number
  right: number
  bottom: number
  width: number
  height: number
}

/** Effective root zoom, or 1 where it isn't reported (jsdom, older engines). */
export function overlayZoom(): number {
  const zoom: number | undefined = document.documentElement.currentCSSZoom
  return typeof zoom === 'number' && zoom > 0 ? zoom : 1
}

/** An element's box in the coordinate space of a fixed overlay layer. */
export function overlayRect(element: Element): OverlayRect {
  const rect = element.getBoundingClientRect()
  const zoom = overlayZoom()
  return {
    top: rect.top / zoom,
    left: rect.left / zoom,
    right: rect.right / zoom,
    bottom: rect.bottom / zoom,
    width: rect.width / zoom,
    height: rect.height / zoom,
  }
}

/** The viewport in that same space — what an overlay can occupy. */
export function overlayViewport(): { width: number; height: number } {
  const zoom = overlayZoom()
  // The visual viewport shrinks with the on-screen keyboard; prefer it so
  // dropdowns still flip against the space the user can actually see.
  const width = window.visualViewport?.width ?? window.innerWidth
  const height = window.visualViewport?.height ?? window.innerHeight
  return { width: width / zoom, height: height / zoom }
}
