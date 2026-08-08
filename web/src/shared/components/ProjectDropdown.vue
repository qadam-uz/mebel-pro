<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useSlots } from 'vue'
import { useI18n } from 'vue-i18n'

import { nextStableId } from '@/shared/app/listboxNav'
import { overlayRect, overlayViewport } from '@/shared/app/overlayGeometry'
import type { DropdownOption } from '@/shared/app/roleConfig'

const props = defineProps<{
  label: string
  modelValue: string
  options: DropdownOption[]
  // Visually hide the eyebrow label (still read by screen readers) to keep the
  // trigger compact, for a host whose surrounding row already says what the
  // choice is.
  hideLabel?: boolean
  // Host-owned skin. `triggerClass` replaces the built-in trigger classes
  // wholesale and `hintClass` the hint's, so a caller that also fills the
  // `#trigger` slot — the workshop sidebar's two-line branch card — wears its
  // own shape without forking the listbox, its keyboard contract, or its
  // positioning.
  triggerClass?: string
  hintClass?: string
  // Filter-bar variant: external sentence-case caption above the trigger (the
  // in-trigger eyebrow goes screen-reader-only) and the COMPACT skin — a lean
  // one-line trigger and option rows without icon tile, meta line, or status
  // dots (only explicit `option.dot` markers render). Leaving it off gives the
  // RICH skin — option rows that keep the meta line and status dots. Every
  // filter-bar caller passes `topLabel`, so the rich skin's one remaining caller
  // is the workshop sidebar's branch card (and the drawer's copy of it), which
  // brings its own trigger through the slot.
  topLabel?: boolean
  // Inert mode: the selection still reads as the current context but cannot be
  // changed here. Used by the workshop sidebar on pages the branch context does
  // not apply to — chrome that disappears between routes is more confusing than
  // chrome that says why it is inactive. `hint` explains the why.
  disabled?: boolean
  hint?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const { t } = useI18n()
const slots = useSlots()

const DOT_CLASS: Record<NonNullable<DropdownOption['dot']>, string> = {
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
  accent: 'bg-accent',
  muted: 'bg-ink-muted',
}

const buttonRef = ref<HTMLButtonElement | null>(null)
const listboxRef = ref<HTMLUListElement | null>(null)
const open = ref(false)
const activeIndex = ref(0)
const popoverStyle = ref<Record<string, string>>({})
const listboxId = nextStableId('mp-listbox')
const POPOVER_GUTTER = 8
const POPOVER_MAX_HEIGHT = 288

const selected = computed(
  () =>
    props.options.find((option) => option.value === props.modelValue) ?? {
      value: '',
      label: t('forms.dropdown.unselected'),
      meta: '',
      status: 'pending' as const,
      dot: undefined,
    },
)
// Status filters mix dotted and dot-less options ("Hammasi") — reserve the dot
// column for the whole list so labels stay aligned.
const hasDots = computed(() => props.options.some((option) => option.dot))
// A host that brings its own trigger owns its geometry as well as its skin.
const hostSkinned = computed(() => Boolean(props.triggerClass || slots.trigger))
const triggerClasses = computed(() => {
  if (props.triggerClass) {
    // Nothing is shared: a host that brings its own class owns the inert look
    // too. The shared cue used to be appended here, and a utility outranks
    // `@layer components`, so `opacity-60` won over the sidebar card's own inert
    // treatment and rendered a full-width panel that read as broken rather than
    // as inactive. The host still gets `disabled` on the button, so the
    // behaviour is unchanged.
    return [props.triggerClass]
  }
  return [
    props.topLabel
      ? [
          'flex min-h-10 items-center gap-2 rounded-lg border bg-elevated px-3 text-left transition',
          open.value ? 'border-accent' : 'border-hairline-strong hover:bg-sunk',
        ]
      : 'mp-surface flex min-h-10 min-w-52 items-center gap-2.5 rounded-lg border-hairline px-3 text-left shadow-none transition',
    props.disabled ? 'cursor-not-allowed bg-sunk opacity-60' : '',
  ]
})
// Minimum panel width. The built-in triggers are narrow by design, so the panel
// widens past them to keep option rows readable; a host-skinned trigger already
// sized itself (the 232px sidebar card) and the panel must match rather than
// overhang the column it sits in.
const panelMinWidth = computed(() => {
  if (hostSkinned.value) return 0
  return props.topLabel ? 200 : 260
})
const activeOptionId = computed(() => {
  const option = props.options[activeIndex.value]
  return option ? `${listboxId}-${option.value}` : undefined
})

function updatePopoverPosition() {
  const button = buttonRef.value
  if (!button) return
  const rect = overlayRect(button)
  const { width: viewportWidth, height: viewportHeight } = overlayViewport()
  const panelWidth = Math.min(
    Math.max(rect.width, panelMinWidth.value),
    Math.max(160, viewportWidth - 16),
  )
  const listHeight = Math.min(
    listboxRef.value?.offsetHeight || POPOVER_MAX_HEIGHT,
    POPOVER_MAX_HEIGHT,
  )
  const spaceBelow = viewportHeight - rect.bottom - POPOVER_GUTTER - 6
  const spaceAbove = rect.top - POPOVER_GUTTER - 6
  const openUp = spaceBelow < listHeight && spaceAbove > spaceBelow
  const maxHeight = Math.max(120, Math.min(openUp ? spaceAbove : spaceBelow, POPOVER_MAX_HEIGHT))
  const left = Math.min(
    Math.max(rect.left, POPOVER_GUTTER),
    Math.max(POPOVER_GUTTER, viewportWidth - panelWidth - POPOVER_GUTTER),
  )
  const top = openUp
    ? Math.max(POPOVER_GUTTER, rect.top - maxHeight - 6)
    : Math.min(rect.bottom + 6, viewportHeight - POPOVER_GUTTER)
  popoverStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
    width: `${panelWidth}px`,
    maxHeight: `${maxHeight}px`,
  }
}

const hintId = `${listboxId}-hint`

async function openList() {
  if (props.disabled) return
  activeIndex.value = Math.max(
    0,
    props.options.findIndex((option) => option.value === selected.value.value),
  )
  open.value = true
  await nextTick()
  updatePopoverPosition()
  listboxRef.value?.focus()
}

function closeList({ returnFocus = false } = {}) {
  open.value = false
  if (returnFocus) buttonRef.value?.focus()
}

function choose(option: DropdownOption) {
  if (props.disabled || !option.value) return
  emit('update:modelValue', option.value)
  closeList({ returnFocus: true })
}

function move(delta: number) {
  if (props.options.length === 0) return
  if (!open.value) {
    void openList().then(() => {
      activeIndex.value = (activeIndex.value + delta + props.options.length) % props.options.length
    })
    return
  }
  activeIndex.value = (activeIndex.value + delta + props.options.length) % props.options.length
}

function onButtonKeydown(event: KeyboardEvent) {
  if (props.disabled) return
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    if (open.value) {
      const option = props.options[activeIndex.value]
      if (option) choose(option)
    } else {
      void openList()
    }
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  } else if (event.key === 'Escape' && open.value) {
    // Two-stage Escape: swallow only while open so a host dialog isn't dismissed
    // by the same keypress that closes this listbox.
    event.stopPropagation()
    closeList({ returnFocus: true })
  } else if (event.key === 'Tab') {
    closeList()
  }
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (buttonRef.value?.contains(target)) return
  const listbox = document.getElementById(listboxId)
  if (listbox?.contains(target)) return
  closeList()
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  window.addEventListener('resize', updatePopoverPosition)
  window.visualViewport?.addEventListener('resize', updatePopoverPosition)
  window.addEventListener('scroll', updatePopoverPosition, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('resize', updatePopoverPosition)
  window.visualViewport?.removeEventListener('resize', updatePopoverPosition)
  window.removeEventListener('scroll', updatePopoverPosition, true)
})
</script>

<template>
  <!-- Where the hint goes is the host's call, via `hintClass`. In a filter row or
       a form it sits BESIDE the trigger, because stacking it would grow the row
       on scoped routes only and the controls would jump between pages. In the
       sidebar column there is no row to grow, so the branch card stacks it
       underneath. Either way it stays wired to the trigger by
       `aria-describedby`. -->
  <div
    class="relative"
    :class="
      topLabel
        ? 'flex flex-col gap-1'
        : hostSkinned
          ? 'flex flex-col'
          : 'inline-flex items-center gap-2.5'
    "
  >
    <span v-if="topLabel" class="mp-filter-dd-label" aria-hidden="true">{{ label }}</span>
    <button
      ref="buttonRef"
      type="button"
      :disabled="disabled"
      :class="triggerClasses"
      :aria-expanded="disabled ? undefined : open"
      :aria-controls="disabled ? undefined : listboxId"
      :aria-haspopup="disabled ? undefined : 'listbox'"
      :aria-describedby="hint ? hintId : undefined"
      :title="hint ?? undefined"
      @click="open ? closeList() : openList()"
      @keydown="onButtonKeydown"
    >
      <!-- The slot is INSIDE the button on purpose: a host swaps the trigger's
           contents, never its behaviour — positioning, the two-stage Escape,
           Tab-closes, focus return and the outside-click test all stay here. -->
      <slot name="trigger" :selected="selected" :open="open" :disabled="disabled === true">
        <span
          v-if="!topLabel"
          class="grid size-7 place-items-center rounded-md"
          :class="disabled ? 'bg-sunk text-ink-muted' : 'bg-accent-soft text-accent'"
          aria-hidden="true"
        >
          <span class="mp-dot"></span>
        </span>
        <span
          v-else-if="selected.dot"
          class="size-2 shrink-0 rounded-full"
          :class="DOT_CLASS[selected.dot]"
          aria-hidden="true"
        ></span>
        <span class="min-w-0 flex-1">
          <span
            :class="
              hideLabel || topLabel ? 'sr-only' : 'block text-[12.5px] font-medium text-ink-muted'
            "
          >
            {{ label }}
          </span>
          <span
            :class="
              topLabel
                ? 'block truncate text-[13.5px] font-semibold text-ink'
                : 'block truncate text-sm font-semibold text-ink'
            "
          >
            {{ selected.label }}
          </span>
        </span>
        <svg class="size-4 shrink-0 text-ink-muted" viewBox="0 0 20 20" aria-hidden="true">
          <path
            d="M5 7.5 10 12l5-4.5"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.8"
          />
        </svg>
      </slot>
    </button>

    <span v-if="hint" :id="hintId" :class="hintClass ?? 'mp-dd-hint'">{{ hint }}</span>

    <Teleport to="body">
      <ul
        v-if="open && !disabled"
        :id="listboxId"
        ref="listboxRef"
        role="listbox"
        tabindex="0"
        class="fixed z-50 overflow-auto overscroll-contain rounded-xl border border-hairline bg-elevated p-1 shadow-[0_1px_2px_color-mix(in_srgb,var(--color-ink)_6%,transparent),0_14px_32px_-20px_color-mix(in_srgb,var(--color-ink)_60%,transparent)]"
        :style="popoverStyle"
        :aria-label="label"
        :aria-activedescendant="activeOptionId"
        @keydown="onButtonKeydown"
      >
        <li
          v-for="(option, index) in options"
          :id="`${listboxId}-${option.value}`"
          :key="option.value"
          role="option"
          :aria-selected="option.value === selected.value"
          class="cursor-pointer items-center rounded-md px-3 py-2"
          :class="[
            topLabel
              ? 'flex gap-2.5 text-[13.5px]'
              : 'grid grid-cols-[auto_1fr_auto] gap-3 text-sm',
            index === activeIndex ? 'bg-sunk' : 'bg-elevated',
            option.value === selected.value ? 'text-accent' : 'text-ink',
          ]"
          @mouseenter="activeIndex = index"
          @click="choose(option)"
        >
          <span
            v-if="!topLabel"
            class="size-2 rounded-full"
            :class="{
              'bg-success': option.status === 'active',
              'bg-warning': option.status === 'pending',
              'bg-ink-muted': option.status === 'blocked',
            }"
            aria-hidden="true"
          ></span>
          <span
            v-else-if="hasDots"
            class="size-2 shrink-0 rounded-full"
            :class="option.dot ? DOT_CLASS[option.dot] : 'bg-transparent'"
            aria-hidden="true"
          ></span>
          <!-- `min-w-0` in BOTH skins. A flex/grid child's automatic minimum size
               is its content, so without it the `1fr` column refuses to shrink,
               `truncate` never gets to ellipsise and a long branch name
               ("Sergeli ishlab chiqarish sexi") pushes the panel into a sideways
               scroll instead — worst on the rich skin, whose only caller now is
               the workshop sidebar's 232px branch card, where the panel matches
               the trigger rather than widening past it. -->
          <span :class="topLabel ? 'min-w-0 flex-1' : 'min-w-0'">
            <span class="block truncate font-semibold">
              {{ option.label }}
            </span>
            <span
              v-if="!topLabel && option.meta"
              class="block truncate text-[12.5px] text-ink-muted"
            >
              {{ option.meta }}
            </span>
          </span>
          <svg
            v-if="option.value === selected.value"
            class="size-4 shrink-0"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <path
              d="m4.5 10.5 3.2 3.2L15.5 6"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
            />
          </svg>
        </li>
      </ul>
    </Teleport>
  </div>
</template>
