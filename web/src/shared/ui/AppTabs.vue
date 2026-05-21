<script setup lang="ts">
// Tab bar over the design system's .tabs/.tab. v-model is the active tab id.
// Keyboard: arrow keys move between tabs (roving tabindex).
import { ref } from 'vue'

export interface Tab {
  id: string
  label: string
}

const props = defineProps<{ tabs: Tab[]; modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const refs = ref<HTMLButtonElement[]>([])

function select(id: string) {
  emit('update:modelValue', id)
}

function onKeydown(e: KeyboardEvent, index: number) {
  if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
  e.preventDefault()
  const delta = e.key === 'ArrowRight' ? 1 : -1
  const next = (index + delta + props.tabs.length) % props.tabs.length
  select(props.tabs[next].id)
  refs.value[next]?.focus()
}
</script>

<template>
  <div class="tabs" role="tablist">
    <button
      v-for="(tab, index) in tabs"
      :key="tab.id"
      ref="refs"
      type="button"
      class="tab"
      :class="{ on: tab.id === modelValue }"
      role="tab"
      :aria-selected="tab.id === modelValue ? 'true' : 'false'"
      :tabindex="tab.id === modelValue ? 0 : -1"
      @click="select(tab.id)"
      @keydown="onKeydown($event, index)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>
