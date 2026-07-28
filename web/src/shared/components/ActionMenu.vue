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
const dropUp = ref(false)
const wrapRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const buttonRef = ref<HTMLButtonElement | null>(null)

/** The nearest ancestor that clips — the table wrapper, usually — else the viewport. */
function clippingBottom(element: HTMLElement): number {
  for (let node = element.parentElement; node; node = node.parentElement) {
    const overflowY = getComputedStyle(node).overflowY
    if (overflowY !== 'visible') return node.getBoundingClientRect().bottom
  }
  return window.innerHeight
}

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
//
// `preventScroll` matters inside a table. `.table-wrap` is `overflow-x: auto`,
// which makes it a scroll container on *both* axes, and the panel is absolutely
// positioned inside it — so opening the menu grows the container's scrollable
// height by the panel's height. Focusing an item then scrolls it into view, and
// because `.tbl th` is `position: sticky` with an opaque fill, the rows slide up
// and disappear under the header. The menu opens directly beneath a button the
// user just clicked, so it is already on screen and there is nothing to scroll
// to (QAD-184).
watch(open, async (isOpen) => {
  if (isOpen) {
    document.addEventListener('pointerdown', onDocumentPointerDown)
    dropUp.value = false
    await nextTick()
    const menu = menuRef.value
    if (menu) {
      // Measure where it actually landed, then flip if it hangs past whatever
      // clips it. Cheaper and more honest than predicting from the trigger.
      const rect = menu.getBoundingClientRect()
      if (rect.bottom > clippingBottom(menu)) dropUp.value = true
    }
    menu
      ?.querySelector<HTMLElement>('[role="menuitem"]:not([disabled])')
      ?.focus({ preventScroll: true })
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
    <div
      v-if="open"
      ref="menuRef"
      class="mp-action-menu"
      :class="{ 'is-above': dropUp }"
      role="menu"
    >
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
