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
    // Visually hide the label block (it stays the radiogroup's accessible name)
    // for a host whose own heading row already says what the choice is — the
    // dashboard's 7 / 14 / 30 period switcher sits beside the page title.
    hideLabel?: boolean
  }>(),
  {
    disabled: false,
    required: false,
    hideLabel: false,
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
    <span
      :id="`${id}-label`"
      :class="hideLabel ? 'sr-only' : 'mb-1 block text-[13.5px] font-semibold text-ink'"
    >
      {{ label }}
      <span v-if="required" class="mp-field-required" aria-hidden="true">*</span>
    </span>
    <!-- A `track` trough with no border: the selected segment is a white chip
         lifted 1px off it, so an outline round the whole row would only double
         the edge the fill already draws. -->
    <div
      class="grid auto-cols-fr grid-flow-col gap-[3px] rounded-lg bg-track p-[3px]"
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
        class="truncate rounded-md px-[15px] py-[7px] text-[13.5px] font-semibold transition pointer-coarse:min-h-11"
        :class="[
          option.value === modelValue
            ? 'bg-elevated text-ink shadow-[0_1px_2px_color-mix(in_srgb,var(--color-ink)_8%,transparent)]'
            : 'text-ink-soft hover:text-ink',
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
