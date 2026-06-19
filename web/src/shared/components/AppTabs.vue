<script setup lang="ts">
import { nextTick } from 'vue'

import type { ChoiceOption } from '@/shared/components/controlTypes'

const props = defineProps<{
  modelValue: string
  tabs: ChoiceOption[]
  idPrefix: string
  label: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

function tabId(value: string) {
  return `${props.idPrefix}-${value}-tab`
}

function panelId(value: string) {
  return `${props.idPrefix}-${value}-panel`
}

async function select(value: string, focus = false) {
  emit('update:modelValue', value)
  if (!focus) return
  await nextTick()
  document.getElementById(tabId(value))?.focus()
}

function onKeydown(event: KeyboardEvent) {
  const enabled = props.tabs.filter((tab) => !tab.disabled)
  if (enabled.length === 0) return
  const currentIndex = Math.max(
    0,
    enabled.findIndex((tab) => tab.value === props.modelValue),
  )
  let nextIndex: number | null = null

  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = (currentIndex + 1) % enabled.length
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = (currentIndex - 1 + enabled.length) % enabled.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = enabled.length - 1
  }

  if (nextIndex === null) return
  event.preventDefault()
  void select(enabled[nextIndex].value, true)
}
</script>

<template>
  <div class="tabs" role="tablist" :aria-label="label" @keydown="onKeydown">
    <button
      v-for="tab in tabs"
      :id="tabId(tab.value)"
      :key="tab.value"
      type="button"
      class="tab"
      :class="{ on: modelValue === tab.value }"
      role="tab"
      :aria-selected="modelValue === tab.value"
      :aria-controls="panelId(tab.value)"
      :tabindex="modelValue === tab.value ? 0 : -1"
      :disabled="tab.disabled"
      @click="select(tab.value)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>
