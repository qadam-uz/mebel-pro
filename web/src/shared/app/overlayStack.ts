import { computed, onBeforeUnmount, ref, watch, type ComputedRef, type Ref } from 'vue'

/**
 * The overlay stack — which surface is on top, decided by **nesting order**
 * rather than by DOM order or a hand-set tier.
 *
 * Every overlay here teleports to `<body>`, so two of them on the same
 * `z-index` tie, and the tie goes to the order their `Teleport` anchors were
 * created — which for an always-mounted child is *before* the sheet that opens
 * it. That is how the tape picker once opened behind the «Detal» sheet, and how
 * the decor lightbox (an `AppModal` at the flat modal tier) opened behind the
 * tape picker that raised it: invisible, focus-trapped, and unreachable.
 *
 * Hand-set tiers only move the tie around. So each overlay **registers while it
 * is open** and reads its z-index off its depth in the stack: the first is the
 * modal layer, and every overlay opened from inside another clears the one
 * below it by {@link OVERLAY_STEP_Z}. Nothing has to know what raised it.
 *
 * Two consumers on top of that:
 * - `isTopmost` — Escape belongs to the innermost overlay only, so the sheet
 *   under a lightbox must not answer it.
 * - {@link useAttachedOverlayZIndex} — a popover attached to a control *inside*
 *   an overlay (the action menu, `DateField`'s calendar, `SearchCombobox`'s
 *   listbox) has to clear its host without claiming a whole overlay tier.
 *
 * The ladder these numbers belong to is documented in `web/DESIGN.md`
 * ("The overlay z-ladder").
 */

/** The modal layer: the first overlay on screen. */
export const OVERLAY_BASE_Z = 80
/** How far each overlay clears the one it was opened from. */
export const OVERLAY_STEP_Z = 5
/**
 * The ceiling for nesting, so a runaway stack can never reach the toast layer
 * (`.mp-toast-host`, z-200) — a toast is the app talking and always shows.
 */
export const OVERLAY_MAX_Z = 150
/**
 * A popover attached to a control inside an overlay sits just above it — over
 * its host, still under anything raised *from* that host.
 */
const ATTACHED_OFFSET = 4

/** Open overlays, outermost first. Values are opaque registration tokens. */
const stack = ref<number[]>([])
let nextToken = 0

function zForDepth(depth: number): number {
  return Math.min(OVERLAY_BASE_Z + depth * OVERLAY_STEP_Z, OVERLAY_MAX_Z)
}

/** The z-index of the innermost open overlay, or 0 when none is open. */
export function topOverlayZIndex(): number {
  return stack.value.length === 0 ? 0 : zForDepth(stack.value.length - 1)
}

/** How many overlays are open. Exposed for tests and diagnostics. */
export function openOverlayCount(): number {
  return stack.value.length
}

/**
 * Register an overlay for as long as `open` is true.
 *
 * Call it from the overlay's own `setup` — the registration follows the
 * component's lifetime, so an overlay unmounted while open leaves the stack
 * cleanly. `zIndex` is meant to be bound as an inline style on the overlay's
 * fixed root; `isTopmost` gates Escape.
 */
export function useOverlayLayer(open: Ref<boolean>): {
  depth: ComputedRef<number>
  zIndex: ComputedRef<number>
  isTopmost: ComputedRef<boolean>
} {
  const token = ref<number | null>(null)

  function enter() {
    if (token.value !== null) return
    nextToken += 1
    token.value = nextToken
    stack.value = [...stack.value, nextToken]
  }

  function leave() {
    const mine = token.value
    if (mine === null) return
    token.value = null
    stack.value = stack.value.filter((entry) => entry !== mine)
  }

  // `immediate`, because a panel can arrive already open — `CuttingPartSheet`
  // is `v-if`-mounted on the part it edits and renders with `open: true` from
  // its first frame, so a change-only watcher would never register it.
  watch(open, (isOpen) => (isOpen ? enter() : leave()), { immediate: true })
  onBeforeUnmount(leave)

  const depth = computed(() => {
    const mine = token.value
    if (mine === null) return 0
    const index = stack.value.indexOf(mine)
    return index < 0 ? 0 : index
  })

  return {
    depth,
    zIndex: computed(() => zForDepth(depth.value)),
    isTopmost: computed(
      () => token.value !== null && stack.value[stack.value.length - 1] === token.value,
    ),
  }
}

/**
 * The z-index for a popover that hangs off a control rather than being an
 * overlay of its own — the action menu, a date picker, a listbox panel.
 *
 * `base` is the tier it uses on a plain page (nothing open); with an overlay on
 * screen it lifts just above the innermost one. The page behind an overlay is
 * inert, so a popover open at that moment can only have been opened from inside
 * that overlay.
 */
export function useAttachedOverlayZIndex(base: number): ComputedRef<number> {
  return computed(() => Math.max(base, topOverlayZIndex() + ATTACHED_OFFSET))
}

/** Test seam: drop every registration. Never call this from app code. */
export function resetOverlayStack() {
  stack.value = []
}
