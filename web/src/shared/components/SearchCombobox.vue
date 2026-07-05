<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { firstEnabledIndex as findEnabledIndex, nextStableId } from '@/shared/app/listboxNav'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useDropdownPlacement } from '@/shared/composables/useDropdownPlacement'

const props = withDefaults(
  defineProps<{
    label: string
    modelValue: string | null
    options: ChoiceOption[]
    placeholder?: string
    error?: string | null
    disabled?: boolean
    noResultsText?: string
    // Extra classes on the visible <label> — e.g. `lg:sr-only` to keep the label
    // for a11y while a column header carries it on wide layouts. Default: visible.
    labelClass?: string
    // Dense single-line trigger for grid/table cells (shorter, tighter padding).
    compact?: boolean
    // A colour swatch rendered inside the input's left edge (e.g. the picked
    // material colour) so the cell reads visually, not just by name.
    swatchColor?: string | null
    // Show a trailing ✕ that clears the current selection and reopens the list
    // for a fresh search — opt-in, since most pickers expect a value to stay set.
    clearable?: boolean
  }>(),
  {
    placeholder: 'Qidiring',
    error: null,
    disabled: false,
    noResultsText: "Mos variant yo'q",
    labelClass: '',
    compact: false,
    swatchColor: null,
    clearable: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
  search: [value: string]
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const listRef = ref<HTMLUListElement | null>(null)
const query = ref('')
const open = ref(false)
const activeIndex = ref(0)
const id = nextStableId('mp-combobox')
const {
  dropUp,
  start: startPlacement,
  stop: stopPlacement,
} = useDropdownPlacement(inputRef, listRef)

const selected = computed(() => props.options.find((option) => option.value === props.modelValue))
const showClear = computed(() => props.clearable && !!props.modelValue && !props.disabled)
const filteredOptions = computed(() => {
  const value = query.value.trim().toLowerCase()
  if (!value) return props.options
  return props.options.filter((option) =>
    `${option.label} ${option.meta ?? ''}`.toLowerCase().includes(value),
  )
})
const activeOptionId = computed(() => {
  const option = filteredOptions.value[activeIndex.value]
  return option ? `${id}-${option.value}` : undefined
})
const errorId = computed(() => (props.error ? `${id}-error` : undefined))

// Remember the chosen option's label so the input keeps showing it even when the
// parent filters that option out of `options` (CB-84 panel filters) — the value
// is still selected, so the display must not blank out.
const rememberedLabel = ref('')
watch(
  selected,
  (option) => {
    if (option) rememberedLabel.value = option.label
  },
  { immediate: true },
)

function selectedLabel() {
  if (selected.value) return selected.value.label
  return props.modelValue ? rememberedLabel.value : ''
}

function syncQueryFromModel() {
  if (!open.value) query.value = selectedLabel()
}

function firstEnabledIndex(start = 0, direction = 1) {
  return findEnabledIndex(filteredOptions.value, start, direction)
}

// Set while choosing closes the list: clicking an option blurs the input, and
// choose() refocuses it — without this guard the input's @focus would reopen the
// list we just closed (the dropdown "lingered" after picking).
let suppressFocusOpen = false

async function openList() {
  if (props.disabled || suppressFocusOpen) return
  open.value = true
  activeIndex.value = firstEnabledIndex(0)
  await nextTick()
  // Placement flips the list up when there's no room below and the list scrolls
  // internally, so it stays visible without scrolling the page (which jumped the
  // content "up" when the dropdown opened low in the viewport).
  startPlacement()
}

function closeList(returnFocus = false) {
  open.value = false
  stopPlacement()
  syncQueryFromModel()
  if (returnFocus) inputRef.value?.focus()
}

function choose(option: ChoiceOption) {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  query.value = option.label
  suppressFocusOpen = true
  closeList(true)
  suppressFocusOpen = false
}

async function clearSelection() {
  emit('update:modelValue', null)
  query.value = ''
  emit('search', '')
  await openList()
  inputRef.value?.focus()
}

function onInput(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) return
  query.value = target.value
  emit('search', query.value)
  if (props.modelValue) emit('update:modelValue', null)
  void openList()
}

function move(direction: number) {
  if (!open.value) {
    void openList()
    return
  }
  const next = firstEnabledIndex(activeIndex.value + direction, direction)
  if (next >= 0) activeIndex.value = next
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  } else if (event.key === 'Enter') {
    if (!open.value) return
    event.preventDefault()
    const option = filteredOptions.value[activeIndex.value]
    if (option) choose(option)
  } else if (event.key === 'Escape') {
    // Only act when open; refocusing a closed list would retrigger @focus → reopen.
    // Two-stage Escape: closing the listbox must not bubble into a host
    // dialog's focus trap and dismiss the whole modal.
    if (open.value) {
      event.stopPropagation()
      closeList(true)
    }
  } else if (event.key === 'Tab') {
    closeList()
  }
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (inputRef.value?.contains(target) || listRef.value?.contains(target)) return
  closeList()
}

watch(
  () => props.modelValue,
  () => syncQueryFromModel(),
  { immediate: true },
)

watch(filteredOptions, () => {
  activeIndex.value = firstEnabledIndex(0)
})

// Re-sync the displayed label when the option set changes underneath us (parent
// filtering). selectedLabel() falls back to the remembered label, so this never
// blanks a still-selected value.
watch(
  () => props.options,
  () => syncQueryFromModel(),
)

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
})
</script>

<template>
  <div class="min-w-0">
    <label
      :id="`${id}-label`"
      class="mb-1 block text-sm font-bold text-ink"
      :class="labelClass"
      :for="id"
    >
      {{ label }}
    </label>
    <div class="relative">
      <span
        v-if="swatchColor"
        class="pointer-events-none absolute top-1/2 size-4 -translate-y-1/2 rounded border border-hairline"
        :class="compact ? 'left-2' : 'left-2.5'"
        :style="{ background: swatchColor }"
        aria-hidden="true"
      ></span>
      <input
        :id="id"
        ref="inputRef"
        class="w-full rounded-md border bg-elevated text-sm text-ink"
        :class="[
          error ? 'border-danger' : 'border-hairline-strong',
          compact ? 'min-h-9' : 'min-h-11',
          swatchColor ? (compact ? 'pl-8' : 'pl-9') : compact ? 'pl-2.5' : 'pl-3',
          showClear ? (compact ? 'pr-8' : 'pr-9') : compact ? 'pr-2.5' : 'pr-3',
        ]"
        :value="query"
        :placeholder="placeholder"
        :disabled="disabled"
        :aria-expanded="open"
        :aria-controls="`${id}-listbox`"
        :aria-activedescendant="open ? activeOptionId : undefined"
        :aria-describedby="errorId"
        role="combobox"
        autocomplete="off"
        aria-autocomplete="list"
        @focus="openList"
        @input="onInput"
        @keydown="onKeydown"
      />
      <button
        v-if="showClear"
        type="button"
        class="absolute top-1/2 grid -translate-y-1/2 place-items-center rounded-full text-ink-muted transition hover:bg-sunk hover:text-ink"
        :class="compact ? 'right-1.5 size-6' : 'right-2 size-7'"
        :aria-label="`${label} tanlovini tozalash`"
        @click="clearSelection"
      >
        <svg class="size-4" viewBox="0 0 20 20" aria-hidden="true">
          <path
            d="M6 6l8 8M14 6l-8 8"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-width="1.8"
          />
        </svg>
      </button>
      <ul
        v-if="open"
        :id="`${id}-listbox`"
        ref="listRef"
        role="listbox"
        class="absolute z-40 max-h-[min(18rem,40dvh)] w-full overflow-auto overscroll-contain rounded-md border border-hairline-strong bg-elevated p-1 shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)]"
        :class="dropUp ? 'bottom-full mb-1' : 'top-full mt-1'"
        :aria-labelledby="`${id}-label`"
      >
        <li
          v-for="(option, index) in filteredOptions"
          :id="`${id}-${option.value}`"
          :key="option.value"
          role="option"
          :aria-selected="option.value === modelValue"
          class="grid min-h-11 cursor-pointer grid-cols-[1fr_auto] items-center gap-3 rounded-md px-3 py-2 text-sm"
          :class="[
            option.disabled ? 'cursor-not-allowed text-ink-muted opacity-55' : '',
            index === activeIndex ? 'bg-sunk' : 'bg-elevated',
            option.value === modelValue ? 'text-accent' : 'text-ink',
          ]"
          @mouseenter="activeIndex = index"
          @click="choose(option)"
        >
          <span class="min-w-0">
            <span class="block truncate font-bold">{{ option.label }}</span>
            <span v-if="option.meta" class="block truncate font-mono text-[11px] text-ink-muted">
              {{ option.meta }}
            </span>
          </span>
          <svg
            v-if="option.value === modelValue"
            class="size-4"
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
        <li v-if="filteredOptions.length === 0" class="px-3 py-3 text-sm font-bold text-ink-muted">
          {{ noResultsText }}
        </li>
      </ul>
    </div>
    <p v-if="error" :id="errorId" class="mt-1 text-sm font-bold text-danger">
      {{ error }}
    </p>
  </div>
</template>
