import { onBeforeUnmount, ref, type Ref } from 'vue'

import { overlayRect, overlayViewport } from '@/shared/app/overlayGeometry'

const MAX_LIST_PX = 288 // matches the max-h clamp (18rem)

/**
 * Decide whether a dropdown listbox should open above its anchor instead of below
 * (CB-64). A listbox pinned strictly below the input gets clipped or pushed
 * off-screen when the input sits low in the (keyboard-shrunk) viewport; this
 * flips it up when there isn't room below and there is more room above, and keeps
 * re-measuring while open as the visual viewport changes.
 */
export function useDropdownPlacement(
  anchor: Ref<HTMLElement | null>,
  list: Ref<HTMLElement | null>,
) {
  const dropUp = ref(false)
  let listening = false

  function measure() {
    const el = anchor.value
    if (!el) return
    // Overlay space keeps this comparable to `offsetHeight` below, which the
    // root zoom leaves in local pixels.
    const rect = overlayRect(el)
    const spaceBelow = overlayViewport().height - rect.bottom
    const spaceAbove = rect.top
    // `|| MAX_LIST_PX` (not `??`): offsetHeight is 0 before the first paint, and a
    // 0 here would wrongly suppress the flip — fall back to the clamp height.
    const listHeight = Math.min(list.value?.offsetHeight || MAX_LIST_PX, MAX_LIST_PX)
    dropUp.value = spaceBelow < listHeight && spaceAbove > spaceBelow
  }

  function start() {
    if (listening) return
    listening = true
    measure()
    window.visualViewport?.addEventListener('resize', measure)
    window.addEventListener('resize', measure)
  }

  function stop() {
    if (!listening) return
    listening = false
    dropUp.value = false
    window.visualViewport?.removeEventListener('resize', measure)
    window.removeEventListener('resize', measure)
  }

  onBeforeUnmount(stop)

  return { dropUp, start, stop, measure }
}
