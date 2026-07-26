<script setup lang="ts">
/**
 * A two-or-three-way choice that reads as one control, for form fields whose
 * options change the shape of the rest of the form ("Kirim to'lovi" vs "Boshqa
 * xarajat"). A dropdown hides the alternative behind a click; a segmented
 * control shows both readings of the form at once.
 *
 * Radio semantics, not tabs: arrow keys move and select, the group takes one
 * tab stop, and the label is bound with `aria-label`.
 */
import { computed, nextTick } from 'vue'

import type { ChoiceOption } from '@/shared/components/controlTypes'

const props = defineProps<{
  modelValue: string
  options: ChoiceOption[]
  label: string
  idPrefix: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const enabled = computed(() => props.options.filter((option) => !option.disabled))

function optionId(value: string) {
  return `${props.idPrefix}-${value}-option`
}

async function select(value: string, focus = false) {
  if (props.disabled) return
  emit('update:modelValue', value)
  if (!focus) return
  await nextTick()
  document.getElementById(optionId(value))?.focus()
}

function onKeydown(event: KeyboardEvent) {
  if (enabled.value.length === 0) return
  const current = Math.max(
    0,
    enabled.value.findIndex((option) => option.value === props.modelValue),
  )
  let next: number | null = null
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    next = (current + 1) % enabled.value.length
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    next = (current - 1 + enabled.value.length) % enabled.value.length
  } else if (event.key === 'Home') {
    next = 0
  } else if (event.key === 'End') {
    next = enabled.value.length - 1
  }
  if (next === null) return
  event.preventDefault()
  void select(enabled.value[next].value, true)
}
</script>

<template>
  <div class="field">
    <span>{{ label }}</span>
    <div class="mp-segment" role="radiogroup" :aria-label="label" @keydown="onKeydown">
      <button
        v-for="option in options"
        :id="optionId(option.value)"
        :key="option.value"
        type="button"
        class="mp-segment-option"
        :class="{ on: modelValue === option.value }"
        role="radio"
        :aria-checked="modelValue === option.value"
        :tabindex="modelValue === option.value ? 0 : -1"
        :disabled="disabled || option.disabled"
        @click="select(option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>
