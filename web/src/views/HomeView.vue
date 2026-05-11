<script setup lang="ts">
import { onMounted } from 'vue'
import { useHealthStore } from '@/stores/health'

const health = useHealthStore()
onMounted(health.fetchHealth)
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold">Mebel Pro</h1>
    <p class="text-gray-600">Frontend scaffold is up.</p>

    <div class="rounded-md border border-gray-200 bg-gray-50 p-4 text-sm">
      <p v-if="health.loading">Checking backend…</p>
      <p v-else-if="health.error" class="text-red-600">Backend unreachable: {{ health.error }}</p>
      <p v-else-if="health.health">
        Backend: <span class="font-mono">{{ health.health.status }}</span> ({{ health.health.env }})
      </p>
    </div>
  </section>
</template>
