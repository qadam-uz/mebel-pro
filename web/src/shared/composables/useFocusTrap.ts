import { nextTick, onBeforeUnmount, watch, type ComputedRef, type Ref } from 'vue'

import { useOverlayLayer } from '@/shared/app/overlayStack'
import { lockBodyScroll, unlockBodyScroll } from '@/shared/app/scrollLock'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not(:disabled)',
  'textarea:not(:disabled)',
  'input:not(:disabled)',
  'select:not(:disabled)',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

/**
 * Dialog focus management for the hand-rolled `.admin-modal` surfaces (AB-02).
 *
 * The shared `ConfirmDialog` already traps focus; the admin SPA's form/detail
 * dialogs are bespoke `<section role="dialog">` panels that did none of it —
 * focus stayed on the trigger behind the scrim, Tab walked out to the page, and
 * Escape was unhandled. This composable gives any such panel the same contract
 * `access-management.md` mandates: move focus in on open, trap Tab/Shift-Tab,
 * close on Escape, and return focus to the opener on close.
 *
 * Usage (inside a view's `setup`, one call per dialog):
 *   const panelRef = ref<HTMLElement | null>(null)
 *   const trap = useFocusTrap(panelRef, modalOpen, () => (modalOpen.value = false))
 *   // template: <section ref="panelRef" @keydown="trap.onKeydown" tabindex="-1">
 *
 * `open` is the same ref that `v-if`-mounts the panel; the post-flush watch runs
 * after the panel is in the DOM. Each call manages its own panel, so a view with
 * several dialogs (or a nested one) just calls it several times.
 */
export function useFocusTrap(
  panelRef: Ref<HTMLElement | null>,
  open: Ref<boolean>,
  onEscape: () => void,
): {
  onKeydown: (event: KeyboardEvent) => void
  zIndex: ComputedRef<number>
  isTopmost: ComputedRef<boolean>
} {
  let previousFocus: HTMLElement | null = null
  // Registering here rather than in each panel: every surface that traps focus
  // is an overlay, and its tier is its depth in the stack (shared/app/overlayStack).
  const { zIndex, isTopmost } = useOverlayLayer(open)

  function focusables(): HTMLElement[] {
    const panel = panelRef.value
    if (!panel) return []
    return Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
      (el) => el.offsetParent !== null || el === document.activeElement,
    )
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      // Escape belongs to the innermost overlay. When something is stacked over
      // this panel we leave the event alone entirely — no `preventDefault`, no
      // `stopPropagation` — so it reaches the document handler of the overlay
      // that *is* on top and closes that one instead.
      if (!isTopmost.value) return
      event.preventDefault()
      // The document-level handler below is the fallback for focus that has
      // left the panel; when the panel itself saw the keypress it owns it.
      // `preventDefault` alone does not settle that — a synthetic
      // non-cancelable keydown leaves `defaultPrevented` false and both
      // handlers fire — and with a dialog stacked over another, only the inner
      // one should close.
      event.stopPropagation()
      onEscape()
      return
    }
    if (event.key !== 'Tab') return
    const items = focusables()
    if (items.length === 0) {
      // Keep focus on the panel itself rather than letting Tab escape.
      event.preventDefault()
      panelRef.value?.focus()
      return
    }
    const first = items[0]
    const last = items[items.length - 1]
    if (!first || !last) return
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  /**
   * Escape, bound to the document rather than only to the panel.
   *
   * The panel handler needs the keypress to bubble out of the focused element,
   * which quietly stops being true the moment focus is anywhere else: a popover
   * teleported to <body> (every dropdown here, per web/AGENTS.md), or a control
   * that unmounts on selection and drops focus to <body>. Either way the modal
   * stopped closing on Escape — and only sometimes, which is worse than never.
   * Document level makes it independent of where focus landed.
   */
  function onDocumentKeydown(event: KeyboardEvent) {
    if (!open.value || event.key !== 'Escape' || event.defaultPrevented) return
    // Every open overlay has this listener bound, and they fire in the order
    // they were added — outermost first. Only the top of the stack answers.
    if (!isTopmost.value) return
    event.preventDefault()
    onEscape()
  }

  watch(
    open,
    async (isOpen) => {
      if (isOpen) {
        previousFocus =
          document.activeElement instanceof HTMLElement ? document.activeElement : null
        lockBodyScroll()
        document.addEventListener('keydown', onDocumentKeydown)
        await nextTick()
        const items = focusables()
        ;(items[0] ?? panelRef.value)?.focus()
      } else {
        document.removeEventListener('keydown', onDocumentKeydown)
        unlockBodyScroll()
        if (previousFocus) {
          previousFocus.focus()
          previousFocus = null
        }
      }
    },
    // `immediate`, because a panel can arrive already open: `CuttingPartSheet`
    // is `v-if`-mounted on the part it edits and passes `open: true` from its
    // first render, so a change-only watcher never fired and that sheet ran
    // with no trap at all — no focus moved in, no Escape at document level, no
    // body scroll lock (which is also what tells a teleported action menu it is
    // inside an overlay; see `body.modal-open .mp-action-menu` in main.css).
    // The closed branch is a no-op on mount: the lock is reference-counted and
    // returns early at zero, and there is no previous focus to restore.
    { flush: 'post', immediate: true },
  )

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', onDocumentKeydown)
    if (open.value) {
      unlockBodyScroll()
      if (previousFocus) previousFocus.focus()
    }
  })

  return { onKeydown, zIndex, isTopmost }
}
