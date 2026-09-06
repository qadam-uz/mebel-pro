<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch, type CSSProperties } from 'vue'

import { nextStableId } from '@/shared/app/listboxNav'
import { overlayRect, overlayViewport } from '@/shared/app/overlayGeometry'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import Icon from '@/shared/components/AppIcon.vue'

/**
 * The client editor's overlay shell: a **full-height bottom sheet on phones and
 * a centred modal from `sm` up** — the two frames the canvas draws for the same
 * three surfaces (the part editor, the material picker, the tape picker).
 *
 * It is not `AppModal` with a class on it. A sheet has a head that stays put, a
 * body that scrolls, and a foot docked to the bottom edge — on a phone that
 * foot has to sit **above the on-screen keyboard** while a numeric field is
 * focused (§7.0), which is a three-row grid, not a modal's single scrolling
 * slot. Everything a modal owes the reader is carried over unchanged: the
 * scrim, the focus trap, Escape, the body scroll-lock and focus returned to the
 * trigger — all of it via `useFocusTrap`, the same seam `AppModal` uses.
 *
 * `--app-vh`, never `100dvh`: the desktop root paints at `zoom: 90%`, so a raw
 * viewport unit would resolve against the unzoomed viewport and paint 90% of
 * the screen (web/AGENTS.md, "Measuring under the root zoom").
 *
 * **A third frame, opt-in: `anchor`.** From `md` up a caller that hands over the
 * control which opened it gets a `SearchCombobox`-shaped panel placed against
 * that control instead of a centred modal — the frame §7.3 asks for on the
 * material picker. It is a popover, not a dialog: no scrim, no scroll lock, no
 * Tab trap; Escape and an outside click close it, focus returns to the trigger,
 * and it repositions on scroll (capture phase, so an inner scroller is heard —
 * web/AGENTS.md) and on resize. Below `md`, and with no anchor, nothing changes.
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    /** Tailwind max-width for the desktop modal. */
    maxWidth?: string
    /** Inset from the top of the viewport on phones, so the page shows through. */
    sheetTopClass?: string
    /** The control that opened this — turns on the anchored frame at `md`. */
    anchor?: HTMLElement | null
    /**
     * Raised from inside another sheet. Two sheets both at the modal layer tie
     * on z-index, and the tie is broken by the order their `Teleport` anchors
     * were created — which put the always-mounted tape picker *behind* the
     * part sheet that opens it, so §7.1's «kromka tanlang» gate opened onto
     * nothing. This is the ladder's raised-from-a-modal tier (DESIGN.md).
     */
    raised?: boolean
  }>(),
  { maxWidth: 'sm:max-w-[560px]', sheetTopClass: 'top-3', anchor: null, raised: false },
)

const emit = defineEmits<{ close: [] }>()

const panelRef = ref<HTMLElement | null>(null)
const id = nextStableId('mp-sheet')

// `md` is the client's own phone/desktop split (§2) and is below the 769px the
// root zoom starts at, so the raw number matches the `md:` utility.
const wide = ref(
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia('(min-width: 768px)').matches
    : false,
)
let mediaQuery: MediaQueryList | null = null
function onMediaChange(event: MediaQueryListEvent) {
  wide.value = event.matches
}
if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  mediaQuery = window.matchMedia('(min-width: 768px)')
  mediaQuery.addEventListener('change', onMediaChange)
}

const anchored = computed(() => Boolean(props.anchor) && wide.value)
// The modal/sheet frame keeps the trap; the anchored popover manages its own
// focus below, so the trap must not also lock the body behind it.
const trapOpen = computed(() => props.open && !anchored.value)
const trap = useFocusTrap(panelRef, trapOpen, () => emit('close'))

const PANEL_GUTTER = 8
const PANEL_MIN_WIDTH = 420
const PANEL_MAX_HEIGHT = 460
const panelStyle = ref<CSSProperties>({})

function updatePanelPosition() {
  const trigger = props.anchor
  if (!trigger) return
  const rect = overlayRect(trigger)
  const { width: viewportWidth, height: viewportHeight } = overlayViewport()
  const width = Math.min(
    Math.max(rect.width, PANEL_MIN_WIDTH),
    Math.max(200, viewportWidth - PANEL_GUTTER * 2),
  )
  const below = viewportHeight - rect.bottom - PANEL_GUTTER - 4
  const above = rect.top - PANEL_GUTTER - 4
  const openUp = below < PANEL_MAX_HEIGHT && above > below
  const maxHeight = Math.max(220, Math.min(openUp ? above : below, PANEL_MAX_HEIGHT))
  const left = Math.min(
    Math.max(rect.left, PANEL_GUTTER),
    Math.max(PANEL_GUTTER, viewportWidth - width - PANEL_GUTTER),
  )
  const top = openUp
    ? Math.max(PANEL_GUTTER, rect.top - maxHeight - 4)
    : Math.min(rect.bottom + 4, viewportHeight - PANEL_GUTTER)
  panelStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
    width: `${width}px`,
    maxHeight: `${maxHeight}px`,
  }
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape' || event.defaultPrevented) return
  event.preventDefault()
  emit('close')
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (panelRef.value?.contains(target)) return
  if (props.anchor?.contains(target)) return
  emit('close')
}

function stopAnchoredListeners() {
  document.removeEventListener('keydown', onDocumentKeydown)
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
  window.removeEventListener('resize', updatePanelPosition)
  // Capture phase: a `scroll` event does not bubble, so a listener bound in the
  // bubble phase never hears the column the trigger actually scrolls in.
  document.removeEventListener('scroll', updatePanelPosition, true)
}

let anchoredTrigger: HTMLElement | null = null

watch(
  () => props.open && anchored.value,
  async (isOpen) => {
    if (!isOpen) {
      stopAnchoredListeners()
      if (anchoredTrigger) {
        anchoredTrigger.focus()
        anchoredTrigger = null
      }
      return
    }
    anchoredTrigger = props.anchor ?? null
    document.addEventListener('keydown', onDocumentKeydown)
    document.addEventListener('pointerdown', onDocumentPointerDown, true)
    window.addEventListener('resize', updatePanelPosition)
    document.addEventListener('scroll', updatePanelPosition, true)
    await nextTick()
    updatePanelPosition()
    // The search field first — a combobox's caret belongs in its query box, not
    // on the close button that happens to come first in the DOM.
    const panel = panelRef.value
    ;(
      panel?.querySelector<HTMLElement>('input') ??
      panel?.querySelector<HTMLElement>('button') ??
      panel
    )?.focus()
  },
  { flush: 'post' },
)

onBeforeUnmount(() => {
  stopAnchoredListeners()
  mediaQuery?.removeEventListener('change', onMediaChange)
})
</script>

<template>
  <Teleport to="body">
    <!-- The anchored frame (`md` and up, with a trigger): a popover, so no
         scrim, and z-[90] — the layer `SearchCombobox`'s own panel uses.
         The single explicit `minmax(0,1fr)` column is load-bearing on every
         frame here: with one explicit column, row-flow auto-placement can only
         ever open implicit *rows*, so no region can be shunted sideways, and a
         `truncate`d child can never widen the panel past its measured width. -->
    <section
      v-if="open && anchored"
      :id="id"
      ref="panelRef"
      role="dialog"
      :aria-labelledby="`${id}-title`"
      tabindex="-1"
      class="fixed z-[90] grid grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden rounded-2xl border border-hairline bg-elevated shadow-[0_28px_90px_-30px_color-mix(in_srgb,var(--color-ink)_55%,transparent)]"
      :style="panelStyle"
    >
      <header
        class="row-start-1 flex items-start justify-between gap-3 border-b border-hairline px-4 py-3"
      >
        <div class="min-w-0">
          <h2 :id="`${id}-title`" class="text-[13.5px] font-bold text-ink">{{ title }}</h2>
          <p v-if="$slots.subtitle" class="mt-0.5 text-[12.5px] font-semibold text-ink-muted">
            <slot name="subtitle"></slot>
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-1.5">
          <slot name="head-actions"></slot>
          <button
            type="button"
            class="mp-action-icon-button size-8 min-h-0 text-ink-muted hover:bg-sunk hover:text-ink"
            :aria-label="$t('shell.action.close')"
            @click="emit('close')"
          >
            <Icon name="x" class="size-4" />
          </button>
        </div>
      </header>
      <div
        class="row-start-2 grid min-h-0 grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)]"
      >
        <div v-if="$slots.pinned"><slot name="pinned"></slot></div>
        <div class="mp-scroll min-h-0 overflow-y-auto px-4 py-3"><slot></slot></div>
      </div>
      <div v-if="$slots.foot" class="row-start-3 border-t border-hairline bg-elevated px-4 py-3">
        <slot name="foot"></slot>
      </div>
    </section>

    <!-- z-[80] is the app modal layer, shared with AppModal — a ConfirmDialog
         raised from inside one still lands above at z-[85]. -->
    <div
      v-else-if="open"
      class="fixed inset-0 sm:grid sm:place-items-center sm:p-4"
      :class="raised ? 'z-[85]' : 'z-[80]'"
    >
      <div class="absolute inset-0 bg-ink/35" aria-hidden="true" @click="emit('close')"></div>
      <section
        :id="id"
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`${id}-title`"
        tabindex="-1"
        class="absolute inset-x-0 bottom-0 grid grid-cols-[minmax(0,1fr)] grid-rows-[auto_auto_minmax(0,1fr)_auto] overflow-hidden rounded-t-[18px] border-t border-hairline-strong bg-elevated shadow-[0_-28px_90px_-30px_color-mix(in_srgb,var(--color-ink)_55%,transparent)] sm:static sm:max-h-[min(calc(var(--app-vh)*0.9),44rem)] sm:w-full sm:rounded-2xl sm:border sm:shadow-[0_28px_90px_-30px_color-mix(in_srgb,var(--color-ink)_55%,transparent)]"
        :class="[sheetTopClass, maxWidth]"
        @keydown="trap.onKeydown"
      >
        <!-- The grab handle is the phone affordance and says nothing on a
             desktop modal, where the frame is already a dialog. It owns row 1
             of its own: sharing a row with the header auto-placed the header
             into an implicit *second column*, which halved the sheet and pushed
             the close button off a phone screen. Four explicit rows, one
             explicit `minmax(0,1fr)` column — every region stays in column 1,
             and at `sm` the hidden handle simply leaves row 1 empty. -->
        <div class="col-start-1 row-start-1 sm:hidden" aria-hidden="true">
          <span class="mx-auto mt-2 block h-1 w-9 rounded-full bg-hairline-strong"></span>
        </div>

        <header
          class="col-start-1 row-start-2 flex items-start justify-between gap-3 border-b border-hairline px-4 pb-3 pt-2.5 sm:px-5 sm:py-4"
        >
          <div class="min-w-0">
            <h2
              :id="`${id}-title`"
              class="font-display text-lg font-bold tracking-[-0.02em] text-ink"
            >
              {{ title }}
            </h2>
            <p v-if="$slots.subtitle" class="mt-0.5 text-[12.5px] font-semibold text-ink-muted">
              <slot name="subtitle"></slot>
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-1.5">
            <slot name="head-actions"></slot>
            <button
              type="button"
              class="mp-action-icon-button size-9 min-h-0 text-ink-muted hover:bg-sunk hover:text-ink"
              :aria-label="$t('shell.action.close')"
              @click="emit('close')"
            >
              <Icon name="x" class="size-[18px]" />
            </button>
          </div>
        </header>

        <!-- `pinned` renders between the head and the scrolling body: the tape
             picker's «Plita rangi» strip and each picker's search field stay in
             view while the list under them scrolls. -->
        <!-- The inner grid needs the explicit column as much as the frame does:
             an implicit `auto` track sizes to the *widest* thing the pinned
             strip or the list can name — a decor label — and pushed the tape
             picker's whole body past the right edge of the phone. -->
        <div
          class="col-start-1 row-start-3 grid min-h-0 grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)]"
        >
          <div v-if="$slots.pinned"><slot name="pinned"></slot></div>
          <div class="mp-scroll min-h-0 overflow-y-auto px-4 py-3.5 sm:px-5 sm:py-4">
            <slot></slot>
          </div>
        </div>

        <!-- The docked foot. On a phone this is what keeps «Saqlash va yana»
             reachable with the keyboard up: the body scrolls under it rather
             than pushing it off-screen. `safe-area-inset-bottom` for the home
             indicator. -->
        <div
          v-if="$slots.foot"
          class="col-start-1 row-start-4 border-t border-hairline bg-elevated px-4 pt-3 shadow-[0_-6px_24px_-14px_color-mix(in_srgb,var(--color-ink)_30%,transparent)] sm:px-5 sm:py-4 sm:shadow-none"
          style="padding-bottom: calc(0.75rem + env(safe-area-inset-bottom))"
        >
          <slot name="foot"></slot>
        </div>
      </section>
    </div>
  </Teleport>
</template>
