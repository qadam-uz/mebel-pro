<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { firstEnabledIndex, nextStableId } from '@/shared/app/listboxNav'
import type { ChoiceOption } from '@/shared/components/controlTypes'

const props = defineProps<{
  label: string
  modelValue: string[]
  options: ChoiceOption[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const buttonRef = ref<HTMLButtonElement | null>(null)
const listRef = ref<HTMLUListElement | null>(null)
const open = ref(false)
const activeIndex = ref(0)
const id = nextStableId('mp-multi-filter')

const selectedOptions = computed(() =>
  props.options.filter((option) => props.modelValue.includes(option.value)),
)
const summary = computed(() => {
  if (selectedOptions.value.length === 0) return 'Any'
  if (selectedOptions.value.length === 1) return selectedOptions.value[0]?.label ?? '1 selected'
  return `${selectedOptions.value.length} selected`
})
const activeOptionId = computed(() => {
  const option = props.options[activeIndex.value]
  return option ? `${id}-${option.value}` : undefined
})

async function openList() {
  open.value = true
  await nextTick()
  listRef.value?.focus()
}

function closeList(returnFocus = false) {
  open.value = false
  if (returnFocus) buttonRef.value?.focus()
}

function toggle(option: ChoiceOption) {
  if (option.disabled) return
  const next = props.modelValue.includes(option.value)
    ? props.modelValue.filter((value) => value !== option.value)
    : [...props.modelValue, option.value]
  emit('update:modelValue', next)
}

function move(direction: number) {
  if (!open.value) {
    void openList()
    return
  }
  // Skip disabled options instead of landing on them (CB-96).
  const next = firstEnabledIndex(props.options, activeIndex.value + direction, direction)
  if (next >= 0) activeIndex.value = next
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  } else if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    if (!open.value) {
      void openList()
      return
    }
    const option = props.options[activeIndex.value]
    if (option) toggle(option)
  } else if (event.key === 'Escape') {
    closeList(true)
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

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
})
</script>

<template>
  <div class="relative min-w-0">
    <span :id="`${id}-label`" class="mb-1 block text-sm font-bold text-ink">{{ label }}</span>
    <button
      ref="buttonRef"
      type="button"
      class="grid min-h-11 w-full grid-cols-[1fr_auto] items-center gap-3 rounded-md border border-hairline-strong bg-elevated px-3 text-left text-sm transition hover:border-hairline-strong"
      :aria-expanded="open"
      :aria-controls="`${id}-listbox`"
      :aria-labelledby="`${id}-label`"
      aria-haspopup="listbox"
      @click="open ? closeList() : openList()"
      @keydown="onKeydown"
    >
      <span class="truncate text-ink">{{ summary }}</span>
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
      :id="`${id}-listbox`"
      ref="listRef"
      role="listbox"
      aria-multiselectable="true"
      tabindex="0"
      class="absolute z-40 mt-1 max-h-72 w-full overflow-auto rounded-md border border-hairline-strong bg-elevated p-1 shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)]"
      :aria-labelledby="`${id}-label`"
      :aria-activedescendant="activeOptionId"
      @keydown="onKeydown"
    >
      <li
        v-for="(option, index) in options"
        :id="`${id}-${option.value}`"
        :key="option.value"
        role="option"
        :aria-selected="modelValue.includes(option.value)"
        class="grid min-h-11 cursor-pointer grid-cols-[auto_1fr] items-center gap-3 rounded-md px-3 py-2 text-sm"
        :class="[
          option.disabled ? 'cursor-not-allowed text-ink-muted opacity-55' : '',
          index === activeIndex ? 'bg-sunk' : 'bg-elevated',
        ]"
        @mouseenter="activeIndex = index"
        @click="toggle(option)"
      >
        <span
          class="grid size-5 place-items-center rounded border"
          :class="
            modelValue.includes(option.value)
              ? 'border-accent bg-accent text-white'
              : 'border-hairline-strong bg-elevated text-transparent'
          "
          aria-hidden="true"
        >
          <svg class="size-3.5" viewBox="0 0 20 20">
            <path
              d="m4.5 10.5 3.2 3.2L15.5 6"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
            />
          </svg>
        </span>
        <span class="min-w-0">
          <span class="block truncate font-bold">{{ option.label }}</span>
          <span v-if="option.meta" class="block truncate font-mono text-[11px] text-ink-muted">
            {{ option.meta }}
          </span>
        </span>
      </li>
    </ul>
  </div>
</template>
