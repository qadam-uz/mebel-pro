<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { nextStableId } from '@/shared/app/listboxNav'
import { overlayRect, overlayViewport } from '@/shared/app/overlayGeometry'
import type { DropdownOption } from '@/shared/app/roleConfig'

const props = defineProps<{
  label: string
  modelValue: string
  options: DropdownOption[]
  // Visually hide the eyebrow label (still read by screen readers) to keep the
  // trigger compact — used by the workshop topbar branch picker.
  hideLabel?: boolean
  // Filter-bar variant: external uppercase caption above the trigger (the
  // in-trigger eyebrow goes screen-reader-only) and the COMPACT skin — a lean
  // one-line trigger and option rows without icon tile, meta line, or status
  // dots (only explicit `option.dot` markers render). The rich skin stays for
  // the topbar: a one-line trigger (icon tile + label, topbar height) whose
  // option rows keep the meta line and status dots.
  topLabel?: boolean
  // Inert mode: the selection still reads as the current context but cannot be
  // changed here. Used by the workshop topbar on pages the branch context does
  // not apply to — chrome that disappears between routes is more confusing than
  // chrome that says why it is inactive. `hint` explains the why.
  disabled?: boolean
  hint?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const { t } = useI18n()

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
    Math.max(rect.width, props.topLabel ? 200 : 260),
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
  <!-- The hint sits BESIDE the trigger, not under it: stacking it would grow the
       host row (the workshop topbar) on scoped routes only, so the chrome would
       jump between pages — the exact thing keeping the picker visible avoids. -->
  <div
    class="relative"
    :class="topLabel ? 'flex flex-col gap-1' : 'inline-flex items-center gap-2.5'"
  >
    <span v-if="topLabel" class="mp-filter-dd-label" aria-hidden="true">{{ label }}</span>
    <button
      ref="buttonRef"
      type="button"
      :disabled="disabled"
      :class="[
        topLabel
          ? [
              'flex min-h-10 items-center gap-2 rounded-lg border bg-elevated px-3 text-left transition',
              open ? 'border-accent' : 'border-hairline-strong hover:bg-sunk',
            ]
          : 'mp-surface flex h-10 min-w-52 items-center gap-2.5 rounded-[7px] border-hairline-strong px-3 text-left shadow-none transition',
        disabled ? 'cursor-not-allowed bg-sunk opacity-60' : '',
      ]"
      :aria-expanded="disabled ? undefined : open"
      :aria-controls="disabled ? undefined : listboxId"
      :aria-haspopup="disabled ? undefined : 'listbox'"
      :aria-describedby="hint ? hintId : undefined"
      :title="hint ?? undefined"
      @click="open ? closeList() : openList()"
      @keydown="onButtonKeydown"
    >
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
            hideLabel || topLabel
              ? 'sr-only'
              : 'block text-[11px] font-bold uppercase tracking-[0.13em] text-ink-muted'
          "
        >
          {{ label }}
        </span>
        <span
          :class="
            topLabel
              ? 'block truncate text-[13px] font-semibold text-ink'
              : 'block truncate text-sm font-bold text-ink'
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
    </button>

    <span v-if="hint" :id="hintId" class="mp-dd-hint">{{ hint }}</span>

    <Teleport to="body">
      <ul
        v-if="open && !disabled"
        :id="listboxId"
        ref="listboxRef"
        role="listbox"
        tabindex="0"
        class="fixed z-50 overflow-auto overscroll-contain rounded-lg border border-hairline-strong bg-elevated p-1 shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)]"
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
            topLabel ? 'flex gap-2.5 text-[13px]' : 'grid grid-cols-[auto_1fr_auto] gap-3 text-sm',
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
          <span :class="topLabel ? 'min-w-0 flex-1' : ''">
            <span :class="topLabel ? 'block truncate font-semibold' : 'block font-bold'">
              {{ option.label }}
            </span>
            <span
              v-if="!topLabel && option.meta"
              class="block font-mono text-[11px] text-ink-muted"
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
