<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { firstEnabledIndex as findEnabledIndex, nextStableId } from '@/shared/app/listboxNav'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useDropdownPlacement } from '@/shared/composables/useDropdownPlacement'

const props = withDefaults(
  defineProps<{
    id?: string
    label: string
    modelValue: string | null
    options: ChoiceOption[]
    placeholder?: string
    error?: string | null
    disabled?: boolean
    required?: boolean
  }>(),
  {
    placeholder: 'Tanlang',
    error: null,
    disabled: false,
    required: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const buttonRef = ref<HTMLButtonElement | null>(null)
const listRef = ref<HTMLUListElement | null>(null)
const open = ref(false)
const activeIndex = ref(0)
const internalId = nextStableId('mp-form-select')
const controlId = computed(() => props.id ?? internalId)
const {
  dropUp,
  start: startPlacement,
  stop: stopPlacement,
} = useDropdownPlacement(buttonRef, listRef)

const selected = computed(() => props.options.find((option) => option.value === props.modelValue))
const activeOptionId = computed(() => {
  const option = props.options[activeIndex.value]
  return option ? `${internalId}-${option.value}` : undefined
})
const buttonText = computed(() => selected.value?.label ?? props.placeholder)
const errorId = computed(() => (props.error ? `${controlId.value}-error` : undefined))

function firstEnabledIndex(start = 0, direction = 1) {
  return findEnabledIndex(props.options, start, direction)
}

async function openList() {
  if (props.disabled || props.options.length === 0) return
  const currentIndex = props.options.findIndex((option) => option.value === props.modelValue)
  activeIndex.value = firstEnabledIndex(currentIndex >= 0 ? currentIndex : 0)
  open.value = true
  await nextTick()
  startPlacement()
  listRef.value?.focus()
}

function closeList(returnFocus = false) {
  open.value = false
  stopPlacement()
  if (returnFocus) buttonRef.value?.focus()
}

function choose(option: ChoiceOption) {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  closeList(true)
}

function move(direction: number) {
  if (!open.value) {
    void openList().then(() => {
      const next = firstEnabledIndex(activeIndex.value + direction, direction)
      if (next >= 0) activeIndex.value = next
    })
    return
  }
  const next = firstEnabledIndex(activeIndex.value + direction, direction)
  if (next >= 0) activeIndex.value = next
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    if (!open.value) {
      void openList()
      return
    }
    const option = props.options[activeIndex.value]
    if (option) choose(option)
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  } else if (event.key === 'Escape') {
    // Two-stage Escape: only swallow the key while the listbox is open, so a
    // second press can still close a host dialog.
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
  if (buttonRef.value?.contains(target) || listRef.value?.contains(target)) return
  closeList()
}

watch(
  () => props.options,
  () => {
    if (open.value && activeIndex.value >= props.options.length) activeIndex.value = 0
  },
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
      :id="`${internalId}-label`"
      class="form-select-label mb-1 block text-sm font-bold text-ink"
      :for="controlId"
    >
      {{ label }}
      <span v-if="required" class="mp-field-required" aria-hidden="true">*</span>
    </label>
    <div class="relative">
      <button
        :id="controlId"
        ref="buttonRef"
        type="button"
        class="grid min-h-11 w-full grid-cols-[1fr_auto] items-center gap-3 rounded-md border bg-elevated px-3 text-left text-sm transition hover:border-hairline-strong"
        :class="[
          error ? 'border-danger' : 'border-hairline-strong',
          disabled ? 'cursor-not-allowed opacity-60' : '',
          selected ? 'text-ink' : 'text-ink-muted',
        ]"
        :disabled="disabled"
        :aria-expanded="open"
        :aria-controls="`${internalId}-listbox`"
        :aria-labelledby="`${internalId}-label ${controlId}`"
        :aria-describedby="errorId"
        :aria-required="required ? 'true' : undefined"
        aria-haspopup="listbox"
        role="combobox"
        @click="open ? closeList() : openList()"
        @keydown="onKeydown"
      >
        <!-- Selected values read semibold like input values; the placeholder stays regular. -->
        <span class="min-w-0 truncate" :class="selected ? 'font-semibold' : ''">
          {{ buttonText }}
        </span>
        <svg class="size-4 text-ink-muted" viewBox="0 0 20 20" aria-hidden="true">
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

      <ul
        v-if="open"
        :id="`${internalId}-listbox`"
        ref="listRef"
        role="listbox"
        tabindex="0"
        class="absolute z-40 max-h-[min(18rem,40dvh)] w-full overflow-auto overscroll-contain rounded-md border border-hairline-strong bg-elevated p-1 shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)]"
        :class="dropUp ? 'bottom-full mb-1' : 'top-full mt-1'"
        :aria-labelledby="`${internalId}-label`"
        :aria-activedescendant="activeOptionId"
        @keydown="onKeydown"
      >
        <li
          v-for="(option, index) in options"
          :id="`${internalId}-${option.value}`"
          :key="option.value"
          role="option"
          :aria-selected="option.value === modelValue"
          class="grid min-h-11 grid-cols-[1fr_auto] items-center gap-3 rounded-md px-3 py-2 text-sm"
          :class="[
            option.disabled ? 'cursor-not-allowed text-ink-muted opacity-55' : 'cursor-pointer',
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
      </ul>
    </div>
    <p v-if="error" :id="errorId" class="mt-1 text-sm font-bold text-danger">
      {{ error }}
    </p>
  </div>
</template>
