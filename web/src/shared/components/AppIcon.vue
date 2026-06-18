<script setup lang="ts">
import { clientIconPath } from '@/shared/app/clientUi'

defineProps<{ name: string }>()
</script>

<template>
  <svg
    class="client-icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="clientIconPath(name)"
  />
</template>
