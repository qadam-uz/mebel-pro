<script setup lang="ts">
import { computed, ref } from 'vue'

import { nextStableId } from '@/shared/app/listboxNav'
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
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    /** Tailwind max-width for the desktop modal. */
    maxWidth?: string
    /** Inset from the top of the viewport on phones, so the page shows through. */
    sheetTopClass?: string
  }>(),
  { maxWidth: 'sm:max-w-[560px]', sheetTopClass: 'top-3' },
)

const emit = defineEmits<{ close: [] }>()

const panelRef = ref<HTMLElement | null>(null)
const openRef = computed(() => props.open)
const id = nextStableId('mp-sheet')
const trap = useFocusTrap(panelRef, openRef, () => emit('close'))
</script>

<template>
  <Teleport to="body">
    <!-- z-[80] is the app modal layer, shared with AppModal — a ConfirmDialog
         raised from inside one still lands above at z-[85]. -->
    <div v-if="open" class="fixed inset-0 z-[80] sm:grid sm:place-items-center sm:p-4">
      <div class="absolute inset-0 bg-ink/35" aria-hidden="true" @click="emit('close')"></div>
      <section
        :id="id"
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`${id}-title`"
        tabindex="-1"
        class="absolute inset-x-0 bottom-0 grid grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden rounded-t-[18px] border-t border-hairline-strong bg-elevated shadow-[0_-28px_90px_-30px_color-mix(in_srgb,var(--color-ink)_55%,transparent)] sm:static sm:max-h-[min(calc(var(--app-vh)*0.9),44rem)] sm:w-full sm:rounded-2xl sm:border sm:shadow-[0_28px_90px_-30px_color-mix(in_srgb,var(--color-ink)_55%,transparent)]"
        :class="[sheetTopClass, maxWidth]"
        @keydown="trap.onKeydown"
      >
        <!-- The grab handle is the phone affordance and says nothing on a
             desktop modal, where the frame is already a dialog. -->
        <div class="row-start-1 sm:hidden" aria-hidden="true">
          <span class="mx-auto mt-2 block h-1 w-9 rounded-full bg-hairline-strong"></span>
        </div>

        <header
          class="row-start-1 flex items-start justify-between gap-3 border-b border-hairline px-4 pb-3 pt-2.5 sm:px-5 sm:py-4"
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
        <div class="row-start-2 grid min-h-0 grid-rows-[auto_minmax(0,1fr)]">
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
          class="row-start-3 border-t border-hairline bg-elevated px-4 pt-3 shadow-[0_-6px_24px_-14px_color-mix(in_srgb,var(--color-ink)_30%,transparent)] sm:px-5 sm:py-4 sm:shadow-none"
          style="padding-bottom: calc(0.75rem + env(safe-area-inset-bottom))"
        >
          <slot name="foot"></slot>
        </div>
      </section>
    </div>
  </Teleport>
</template>
