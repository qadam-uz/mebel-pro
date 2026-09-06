<script setup lang="ts">
import { computed, ref } from 'vue'

import { nextStableId } from '@/shared/app/listboxNav'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import AdminModalCloseIcon from '@/shared/components/AdminModalCloseIcon.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    // Tailwind max-width utility for the panel; defaults to a comfortable form width.
    maxWidth?: string
  }>(),
  { maxWidth: 'max-w-lg' },
)

const emit = defineEmits<{ close: [] }>()

const panelRef = ref<HTMLElement | null>(null)
const openRef = computed(() => props.open)
const id = nextStableId('mp-modal')
// The trap moves focus in on open, cycles Tab, closes on Escape, restores focus
// on close, and ref-counts the body scroll lock — no direct lock calls needed.
const trap = useFocusTrap(panelRef, openRef, () => emit('close'))
</script>

<template>
  <Teleport to="body">
    <!-- The tier comes from the overlay stack, not from a literal: this modal
         is the decor lightbox as often as it is a form, and a lightbox opened
         from inside a bottom sheet has to clear the sheet that raised it
         (shared/app/overlayStack; DESIGN.md, the overlay z-ladder). -->
    <div
      v-if="open"
      class="fixed inset-0 grid place-items-center p-4"
      :style="{ zIndex: trap.zIndex.value }"
    >
      <div class="absolute inset-0 bg-ink/35" aria-hidden="true" @click="emit('close')"></div>
      <section
        :id="id"
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`${id}-title`"
        tabindex="-1"
        class="relative flex max-h-[min(90dvh,44rem)] w-full flex-col overflow-hidden rounded-lg border border-hairline-strong bg-elevated shadow-[0_28px_90px_-30px_color-mix(in_srgb,var(--color-ink)_55%,transparent)]"
        :class="maxWidth"
        @keydown="trap.onKeydown"
      >
        <header class="flex items-center justify-between gap-3 border-b border-hairline px-5 py-4">
          <h2 :id="`${id}-title`" class="font-display text-lg font-semibold text-ink">
            {{ title }}
          </h2>
          <button
            type="button"
            class="grid size-9 shrink-0 place-items-center rounded-md text-ink-muted transition hover:bg-sunk hover:text-ink [&_svg]:size-5 [&_svg]:fill-none [&_svg]:stroke-current [&_svg]:stroke-2"
            :aria-label="$t('shell.action.close')"
            @click="emit('close')"
          >
            <AdminModalCloseIcon />
          </button>
        </header>
        <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <slot></slot>
        </div>
      </section>
    </div>
  </Teleport>
</template>
