<script setup lang="ts">
// Wizard progress over the design system's .stepper. `current` is the 0-based
// index of the active step; earlier steps render as done.
import { computed } from 'vue'

const props = defineProps<{ steps: string[]; current: number }>()

const items = computed(() =>
  props.steps.map((label, index) => ({
    label,
    n: index + 1,
    state: index < props.current ? 'done' : index === props.current ? 'on' : '',
  })),
)
</script>

<template>
  <ol class="stepper" style="list-style: none; padding: 0">
    <li v-for="item in items" :key="item.n" class="st" :class="item.state">
      <span class="n">{{ item.state === 'done' ? '✓' : item.n }}</span>
      {{ item.label }}
    </li>
  </ol>
</template>
