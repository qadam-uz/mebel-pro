<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useSlots, watch } from 'vue'

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
    // Uzbek is the only shipped locale: a call site that forgets to pass a label
    // must still render Uzbek, never an English placeholder (QAD-163).
    confirmLabel: 'Tasdiqlash',
    cancelLabel: 'Bekor qilish',
    busyLabel: 'Bajarilmoqda…',
    danger: false,
    busy: false,
    confirmDisabled: false,
  },
)

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()

const panelRef = ref<HTMLElement | null>(null)
const cancelButtonRef = ref<HTMLButtonElement | null>(null)
const slots = useSlots()
const id = nextStableId('mp-confirm')
let previousFocus: HTMLElement | null = null

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
  if (event.key === 'Escape' && !props.busy) {
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
    <!-- z-[85]: above the modal layer (admin modal panel z-80, scrim z-70) so a
         confirm raised from inside another modal is clickable, yet below toasts
         (z-90) so the success/failure toast still shows on top. -->
    <div v-if="open" class="fixed inset-0 z-[85] grid place-items-center p-4" @keydown="onKeydown">
      <div class="absolute inset-0 bg-ink/35" aria-hidden="true"></div>
      <section
        :id="id"
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`${id}-title`"
        :aria-describedby="`${id}-message`"
        class="relative w-full max-w-md rounded-lg border border-hairline-strong bg-elevated p-5 shadow-[0_28px_90px_-30px_rgb(15_27_45_/_55%)]"
      >
        <h2 :id="`${id}-title`" class="font-serif text-xl font-semibold text-ink">
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
            {{ cancelLabel }}
          </button>
          <button
            type="button"
            class="mp-button"
            :class="danger ? 'bg-danger text-white' : 'mp-button-primary'"
            :disabled="busy || confirmDisabled"
            @click="emit('confirm')"
          >
            {{ busy ? busyLabel : confirmLabel }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
