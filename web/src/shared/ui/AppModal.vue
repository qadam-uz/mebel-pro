<script setup lang="ts">
// Accessible modal — scrim + .modal from the design system. Teleported to
// <body>, focus-trapped while open, ESC + scrim-click close, focus restored
// on close. v-model:open controls visibility.
import { nextTick, ref, watch } from 'vue'
import { t } from '@/shared/i18n'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    wide?: boolean
    closeOnScrim?: boolean
  }>(),
  { closeOnScrim: true },
)

const emit = defineEmits<{ 'update:open': [value: boolean]; close: [] }>()

const dialog = ref<HTMLElement | null>(null)
let lastFocused: HTMLElement | null = null

function close() {
  emit('update:open', false)
  emit('close')
}

function focusables(): HTMLElement[] {
  if (!dialog.value) return []
  return Array.from(
    dialog.value.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
    ),
  )
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    close()
    return
  }
  if (e.key === 'Tab') {
    const items = focusables()
    if (items.length === 0) return
    const first = items[0]
    const last = items[items.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      lastFocused = document.activeElement as HTMLElement | null
      await nextTick()
      focusables()[0]?.focus()
    } else {
      lastFocused?.focus?.()
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <div class="scrim" :class="{ on: open }" @click="closeOnScrim && close()" />
    <div
      v-show="open"
      ref="dialog"
      class="modal"
      :class="{ on: open, wide }"
      role="dialog"
      aria-modal="true"
      @keydown="onKeydown"
    >
      <header class="modal-h">
        <h3>{{ title }}</h3>
        <button class="x" type="button" :aria-label="t('common.close')" @click="close">✕</button>
      </header>
      <div class="modal-b"><slot /></div>
      <footer v-if="$slots.footer" class="modal-f"><slot name="footer" /></footer>
    </div>
  </Teleport>
</template>
