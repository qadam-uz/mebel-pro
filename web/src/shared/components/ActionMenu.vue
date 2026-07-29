<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch, type CSSProperties } from 'vue'
import AppIcon from '@/shared/components/AppIcon.vue'
import { overlayRect, overlayViewport } from '@/shared/app/overlayGeometry'

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

const GUTTER = 8
const MAX_PANEL_PX = 320 // matches the max-height in `.mp-action-menu`

const open = ref(false)
const wrapRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const buttonRef = ref<HTMLButtonElement | null>(null)
const panelStyle = ref<CSSProperties>({})

// The panel is teleported to `<body>` and positioned from the trigger, the same
// way every other popover here works (`ProjectDropdown`, `DateField`).
//
// It has to leave the row. `.table-wrap` is `overflow-x: auto`, which per spec
// makes it a scroll container on *both* axes, so a panel absolutely positioned
// inside it (a) grows the wrapper's `scrollHeight`, which slid rows under the
// opaque `position: sticky` header, and (b) gets clipped by the wrapper — and on
// a short table there is no room in *either* direction, so flipping alone can't
// save it. Out of the clipping ancestor, both problems stop existing (QAD-184).
function updatePosition() {
  const button = buttonRef.value
  const panel = menuRef.value
  if (!button || !panel) return
  const rect = overlayRect(button)
  const { width: viewportWidth, height: viewportHeight } = overlayViewport()
  // `|| MAX_PANEL_PX`, not `??`: offsetHeight is 0 before the first paint and a
  // zero here would wrongly suppress the flip.
  const panelHeight = Math.min(panel.offsetHeight || MAX_PANEL_PX, MAX_PANEL_PX)
  const panelWidth = panel.offsetWidth
  const spaceBelow = viewportHeight - rect.bottom - GUTTER - 6
  const spaceAbove = rect.top - GUTTER - 6
  const openUp = spaceBelow < panelHeight && spaceAbove > spaceBelow
  const maxHeight = Math.max(120, Math.min(openUp ? spaceAbove : spaceBelow, MAX_PANEL_PX))
  // Right-aligned to the trigger, as the row's `⋯` sits in the last column.
  const left = Math.min(
    Math.max(rect.right - panelWidth, GUTTER),
    Math.max(GUTTER, viewportWidth - panelWidth - GUTTER),
  )
  const top = openUp
    ? Math.max(GUTTER, rect.top - Math.min(panelHeight, maxHeight) - 6)
    : Math.min(rect.bottom + 6, viewportHeight - GUTTER)
  panelStyle.value = { top: `${top}px`, left: `${left}px`, maxHeight: `${maxHeight}px` }
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
  // The panel lives outside `wrapRef` in the DOM now, so it needs its own check
  // or clicking an item would close the menu before the item's click lands.
  if (wrapRef.value?.contains(event.target)) return
  if (menuRef.value?.contains(event.target)) return
  close()
}

// Bind the click-outside and re-measure listeners only while open, and move
// focus into the menu so keyboard users land on the first item. `preventScroll`
// because the menu opens directly under a button the user just clicked — it is
// already on screen and there is nothing to scroll to.
watch(open, async (isOpen) => {
  if (isOpen) {
    document.addEventListener('pointerdown', onDocumentPointerDown)
    window.addEventListener('resize', updatePosition)
    window.visualViewport?.addEventListener('resize', updatePosition)
    // Capture phase: the trigger's own scroll container is the one that moves it.
    window.addEventListener('scroll', updatePosition, true)
    await nextTick()
    updatePosition()
    menuRef.value
      ?.querySelector<HTMLElement>('[role="menuitem"]:not([disabled])')
      ?.focus({ preventScroll: true })
  } else {
    stopListening()
  }
})

function stopListening() {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('resize', updatePosition)
  window.visualViewport?.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
}
onBeforeUnmount(stopListening)
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
    <Teleport to="body">
      <!-- Esc is handled here as well as on the wrapper: focus is inside this
           panel while it is open, and teleporting means the keypress no longer
           bubbles through the wrapper. -->
      <div
        v-if="open"
        ref="menuRef"
        class="mp-action-menu"
        :style="panelStyle"
        role="menu"
        @keydown.esc.stop.prevent="close(true)"
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
    </Teleport>
  </div>
</template>
