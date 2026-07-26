<script setup lang="ts">
import { computed, nextTick } from 'vue'

import { nextStableId } from '@/shared/app/listboxNav'
import type { ChoiceOption } from '@/shared/components/controlTypes'

// A closed set of two or three choices, all visible at once. A dropdown for
// two options is a click that reveals nothing the user couldn't already see;
// this trades the popover for the row it would have opened. Past three or four
// segments the row stops fitting — use FormSelect instead.
const props = withDefaults(
  defineProps<{
    label: string
    modelValue: string | null
    options: ChoiceOption[]
    disabled?: boolean
    required?: boolean
  }>(),
  {
    disabled: false,
    required: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const id = nextStableId('mp-segmented')
const enabledOptions = computed(() => props.options.filter((option) => !option.disabled))

function segmentId(value: string) {
  return `${id}-${value}`
}

// Roving tabindex: the group is one tab stop. When nothing is selected yet the
// first segment carries it, so the keyboard can always reach the control.
function isTabStop(option: ChoiceOption, index: number) {
  if (props.modelValue !== null) return option.value === props.modelValue
  return index === 0
}

async function select(value: string, focus = false) {
  if (props.disabled) return
  emit('update:modelValue', value)
  if (!focus) return
  await nextTick()
  document.getElementById(segmentId(value))?.focus()
}

function onKeydown(event: KeyboardEvent) {
  const options = enabledOptions.value
  if (options.length === 0 || props.disabled) return
  const currentIndex = Math.max(
    0,
    options.findIndex((option) => option.value === props.modelValue),
  )
  let nextIndex: number | null = null
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = (currentIndex + 1) % options.length
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = (currentIndex - 1 + options.length) % options.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = options.length - 1
  }
  if (nextIndex === null) return
  event.preventDefault()
  void select(options[nextIndex].value, true)
}
</script>

<template>
  <div class="min-w-0">
    <span :id="`${id}-label`" class="mb-1 block text-sm font-bold text-ink">
      {{ label }}
      <span v-if="required" class="mp-field-required" aria-hidden="true">*</span>
    </span>
    <div
      class="grid auto-cols-fr grid-flow-col gap-1 rounded-md border border-hairline-strong bg-sunk p-1"
      :class="disabled ? 'cursor-not-allowed opacity-60' : ''"
      role="radiogroup"
      :aria-labelledby="`${id}-label`"
      :aria-required="required ? 'true' : undefined"
      @keydown="onKeydown"
    >
      <button
        v-for="(option, index) in options"
        :id="segmentId(option.value)"
        :key="option.value"
        type="button"
        role="radio"
        class="min-h-9 truncate rounded-sm px-3 text-sm font-bold transition"
        :class="[
          option.value === modelValue
            ? 'bg-accent-soft text-accent-deep shadow-[inset_0_0_0_1px_var(--color-accent-tint)]'
            : 'text-ink-soft hover:bg-elevated hover:text-ink',
          disabled || option.disabled ? 'cursor-not-allowed' : 'cursor-pointer',
        ]"
        :aria-checked="option.value === modelValue"
        :tabindex="isTabStop(option, index) ? 0 : -1"
        :disabled="disabled || option.disabled"
        @click="select(option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>
