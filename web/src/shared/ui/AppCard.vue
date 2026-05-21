<script setup lang="ts">
// Wraps the design system's .card. Optional header (title + sub + actions
// slot) and a flush body (no padding) for tables.
withDefaults(
  defineProps<{
    title?: string
    sub?: string
    flush?: boolean
  }>(),
  { flush: false },
)
</script>

<template>
  <section class="card">
    <header v-if="title || sub || $slots.actions" class="card-h">
      <div>
        <h2 v-if="title">{{ title }}</h2>
        <div v-if="sub" class="sub">{{ sub }}</div>
      </div>
      <div v-if="$slots.actions" class="ts"><slot name="actions" /></div>
    </header>
    <div class="card-b" :class="{ flush }"><slot /></div>
  </section>
</template>
