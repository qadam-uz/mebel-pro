<script setup lang="ts">
// A toggle .chip. `active` drives the .on state; click toggles via v-model or
// emits `click`. `ghost` uses the accent-tint active style.
defineProps<{ active?: boolean; ghost?: boolean }>()
const emit = defineEmits<{ click: [] }>()
</script>

<template>
  <button
    type="button"
    class="chip"
    :class="{ on: active, ghost }"
    :aria-pressed="active ? 'true' : 'false'"
    @click="emit('click')"
  >
    <slot />
  </button>
</template>
