import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { lockBodyScroll, unlockBodyScroll } from '@/shared/app/scrollLock'

/**
 * The drawer that replaces the sidebar below its breakpoint, shared by the
 * workshop and platform shells: an `aria-modal` dialog that traps focus, locks
 * body scroll while it is open, and hands focus back to whatever opened it.
 *
 * `onBeforeOpen` runs after the trigger has been remembered and before the
 * drawer opens — for a shell that has topbar overlays the drawer would cover.
 */
export function useMobileNav(options: { onBeforeOpen?: () => void } = {}) {
  const mobileNavOpen = ref(false)
  const mobileTriggerRef = ref<HTMLButtonElement | null>(null)
  const drawerPanelRef = ref<HTMLElement | null>(null)
  let previousMobileFocus: HTMLElement | null = null

  function drawerFocusable() {
    return Array.from(
      drawerPanelRef.value?.querySelectorAll<HTMLElement>(
        'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    ).filter((element) => !element.hasAttribute('disabled') && element.tabIndex >= 0)
  }

  function openMobileNav() {
    previousMobileFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : mobileTriggerRef.value
    options.onBeforeOpen?.()
    mobileNavOpen.value = true
  }

  function closeMobileNav() {
    if (!mobileNavOpen.value) return
    mobileNavOpen.value = false
  }

  function onDrawerKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault()
      closeMobileNav()
      return
    }
    if (event.key !== 'Tab') return

    const focusable = drawerFocusable()
    if (focusable.length === 0) {
      event.preventDefault()
      drawerPanelRef.value?.focus()
      return
    }
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  /** A popover the drawer hosts, teleported to `<body>` and therefore outside the
   *  drawer's own subtree. */
  function isDrawerOverlay(node: Node | null) {
    if (!(node instanceof Element)) return false
    return Boolean(node.closest('[role="listbox"], [role="menu"], .mp-action-menu'))
  }

  // The keydown trap above only sees events inside the drawer, and the drawer now
  // hosts two controls whose panels teleport to `<body>`: the branch picker and
  // the account menu. `ProjectDropdown` closes its listbox on Tab WITHOUT
  // returning focus, so the browser resumed the tab order from `<body>` and walked
  // straight out of an `aria-modal` dialog into the page behind it. A focusin
  // guard catches that no matter how focus left — Tab, Shift+Tab, or a
  // programmatic move — because it tests where focus LANDED rather than which key
  // produced it.
  function onDocumentFocusIn(event: FocusEvent) {
    if (!mobileNavOpen.value) return
    const target = event.target
    if (!(target instanceof Node)) return
    if (drawerPanelRef.value?.contains(target) || isDrawerOverlay(target)) return
    const focusable = drawerFocusable()
    if (focusable.length > 0) focusable[0].focus()
    else drawerPanelRef.value?.focus()
  }

  watch(
    mobileNavOpen,
    async (open) => {
      if (open) {
        lockBodyScroll()
        await nextTick()
        const first = drawerFocusable()[0]
        if (first) first.focus()
        else drawerPanelRef.value?.focus()
        return
      }
      unlockBodyScroll()
      previousMobileFocus?.focus()
      previousMobileFocus = null
    },
    { flush: 'post' },
  )

  onMounted(() => {
    document.addEventListener('focusin', onDocumentFocusIn)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('focusin', onDocumentFocusIn)
    if (mobileNavOpen.value) unlockBodyScroll()
    previousMobileFocus = null
  })

  return {
    mobileNavOpen,
    mobileTriggerRef,
    drawerPanelRef,
    openMobileNav,
    closeMobileNav,
    onDrawerKeydown,
  }
}
