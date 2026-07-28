<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import AppIcon from '@/shared/components/AppIcon.vue'

export interface ActionMenuItem {
  label: string
  // `AppIcon` name shown before the label. The word still carries the meaning —
  // the glyph is what keeps a danger item from being red text alone (QAD-184).
  icon?: string
  danger?: boolean
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    items: ActionMenuItem[]
    // Accessible name for the trigger (e.g. "Detal #2 amallari").
    label?: string
    triggerClass?: string
  }>(),
  { label: 'Amallar', triggerClass: 'mp-action-icon-button' },
)
const emit = defineEmits<{ select: [index: number] }>()

const open = ref(false)
const wrapRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const buttonRef = ref<HTMLButtonElement | null>(null)

function toggle() {
  open.value = !open.value
}
function close(returnFocus = false) {
  open.value = false
  if (returnFocus) buttonRef.value?.focus()
}
function onSelect(index: number) {
  if (props.items[index]?.disabled) return
  emit('select', index)
  close()
}
function onDocumentPointerDown(event: PointerEvent) {
  if (!(event.target instanceof Node)) return
  if (wrapRef.value?.contains(event.target)) return
  close()
}

// Open/close lifecycle: bind the click-outside listener only while open, and
// move focus into the menu so keyboard users land on the first item.
watch(open, async (isOpen) => {
  if (isOpen) {
    document.addEventListener('pointerdown', onDocumentPointerDown)
    await nextTick()
    menuRef.value?.querySelector<HTMLElement>('[role="menuitem"]:not([disabled])')?.focus()
  } else {
    document.removeEventListener('pointerdown', onDocumentPointerDown)
  }
})
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocumentPointerDown))
</script>

<template>
  <div ref="wrapRef" class="mp-action-menu-wrap" @keydown.esc.stop.prevent="close(true)">
    <!-- Default trigger is the row's `⋯`. The slot lets a caller wear something
         else — the topbar wraps the avatar with it (QAD-182) — without
         reimplementing the outside-click, focus and Esc handling. -->
    <button
      ref="buttonRef"
      type="button"
      :class="triggerClass"
      :aria-expanded="open"
      aria-haspopup="menu"
      :aria-label="label"
      @click="toggle"
    >
      <slot name="trigger"><span aria-hidden="true">⋯</span></slot>
    </button>
    <div v-if="open" ref="menuRef" class="mp-action-menu" role="menu">
      <button
        v-for="(item, index) in items"
        :key="index"
        type="button"
        class="mp-action-menu-item"
        :class="{ danger: item.danger }"
        role="menuitem"
        :disabled="item.disabled"
        @click="onSelect(index)"
      >
        <AppIcon v-if="item.icon" :name="item.icon" />
        {{ item.label }}
      </button>
    </div>
  </div>
</template>
