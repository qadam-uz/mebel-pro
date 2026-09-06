<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useSlots, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useOverlayLayer } from '@/shared/app/overlayStack'
import { lockBodyScroll, unlockBodyScroll } from '@/shared/app/scrollLock'
import { nextStableId } from '@/shared/app/listboxNav'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    busyLabel?: string
    danger?: boolean
    busy?: boolean
    confirmDisabled?: boolean
  }>(),
  {
    danger: false,
    busy: false,
    confirmDisabled: false,
  },
)

const { t } = useI18n()

// The generic labels are resolved here rather than as prop defaults: a default
// is evaluated once, so it would freeze at whichever locale happened to be
// active when the module first ran. A call site that passes its own label — the
// destructive confirms that name their consequence — still wins.
const confirmText = computed(() => props.confirmLabel ?? t('shell.confirm.confirm'))
const cancelText = computed(() => props.cancelLabel ?? t('shell.confirm.cancel'))
const busyText = computed(() => props.busyLabel ?? t('shell.confirm.busy'))

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()

const panelRef = ref<HTMLElement | null>(null)
const cancelButtonRef = ref<HTMLButtonElement | null>(null)
const slots = useSlots()
const id = nextStableId('mp-confirm')
let previousFocus: HTMLElement | null = null

// This dialog is raised from inside another overlay more often than not, so its
// tier is its depth in the overlay stack rather than a fixed one step above the
// modal layer — a confirm over a sheet over a sheet still lands on top.
const layer = useOverlayLayer(computed(() => props.open))

// The trap must cycle slot fields too (a reason input/textarea sits before the
// footer buttons) — a buttons-only cycle makes those fields keyboard-unreachable.
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not(:disabled)',
  'textarea:not(:disabled)',
  'input:not(:disabled)',
  'select:not(:disabled)',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

function focusableElements() {
  return Array.from(panelRef.value?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [])
}

function onKeydown(event: KeyboardEvent) {
  // Escape belongs to whatever is innermost; when something is stacked over
  // this dialog the event is left untouched so that overlay answers it.
  if (event.key === 'Escape' && !props.busy && layer.isTopmost.value) {
    event.preventDefault()
    emit('cancel')
    return
  }
  // Enter in a single-line slot field confirms, matching the form these dialogs
  // replace (textareas keep Enter for newlines; buttons keep their own Enter).
  if (event.key === 'Enter' && event.target instanceof HTMLInputElement) {
    event.preventDefault()
    if (!props.busy && !props.confirmDisabled) emit('confirm')
    return
  }
  if (event.key !== 'Tab') return

  const focusable = focusableElements()
  if (focusable.length === 0) return

  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (!first || !last) return

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

async function focusInitial() {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  await nextTick()
  // The first focusable is the slot's field when one exists, else Cancel.
  const target = focusableElements()[0] ?? cancelButtonRef.value
  target?.focus()
}

watch(
  () => props.open,
  async (open) => {
    // Freeze the page behind the dialog on mobile (CB-43); the shared lock is
    // ref-counted so a dialog over the edge modal nests cleanly.
    if (open) lockBodyScroll()
    else unlockBodyScroll()
    if (open) {
      await focusInitial()
    } else if (previousFocus) {
      previousFocus.focus()
      previousFocus = null
    }
  },
  { flush: 'post' },
)

onMounted(() => {
  if (props.open) {
    lockBodyScroll()
    void focusInitial()
  }
})

onBeforeUnmount(() => {
  if (props.open) unlockBodyScroll()
  if (previousFocus) previousFocus.focus()
})
</script>

<template>
  <Teleport to="body">
    <!-- The tier comes from the overlay stack: above whatever raised this
         confirm so it is clickable, and always below the toast layer so the
         success/failure toast still shows on top (DESIGN.md, the z-ladder). -->
    <div
      v-if="open"
      class="fixed inset-0 grid place-items-center p-4"
      :style="{ zIndex: layer.zIndex.value }"
      @keydown="onKeydown"
    >
      <div class="absolute inset-0 bg-ink/35" aria-hidden="true"></div>
      <section
        :id="id"
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`${id}-title`"
        :aria-describedby="`${id}-message`"
        class="relative w-full max-w-md rounded-lg border border-hairline-strong bg-elevated p-5 shadow-[0_28px_90px_-30px_color-mix(in_srgb,var(--color-ink)_55%,transparent)]"
      >
        <h2 :id="`${id}-title`" class="font-display text-xl font-semibold text-ink">
          {{ title }}
        </h2>
        <p :id="`${id}-message`" class="mt-3 text-sm leading-6 text-ink-soft">
          {{ message }}
        </p>
        <div v-if="slots.default" class="mt-4">
          <slot></slot>
        </div>
        <div class="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            ref="cancelButtonRef"
            type="button"
            class="mp-button mp-button-outline"
            :disabled="busy"
            @click="emit('cancel')"
          >
            {{ cancelText }}
          </button>
          <button
            type="button"
            class="mp-button"
            :class="danger ? 'bg-danger text-white' : 'mp-button-primary'"
            :disabled="busy || confirmDisabled"
            @click="emit('confirm')"
          >
            {{ busy ? busyText : confirmText }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
