import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

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
) {
  let previousFocus: HTMLElement | null = null

  function focusables(): HTMLElement[] {
    const panel = panelRef.value
    if (!panel) return []
    return Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
      (el) => el.offsetParent !== null || el === document.activeElement,
    )
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault()
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
    { flush: 'post' },
  )

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', onDocumentKeydown)
    if (open.value) {
      unlockBodyScroll()
      if (previousFocus) previousFocus.focus()
    }
  })

  return { onKeydown }
}
