<script setup lang="ts">
// Shared client-facing load-error block (CB-22). Replaces the hand-copied
// `.client-error` markup across the client views so the title, trace label, and
// retry affordance stay consistent.
withDefaults(
  defineProps<{
    title: string
    traceId?: string | null
    message?: string
  }>(),
  {
    traceId: null,
    message: "Ulanishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.",
  },
)

defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="client-error">
    <div class="client-error-icon">!</div>
    <h3>{{ title }}</h3>
    <p>{{ message }}</p>
    <p class="client-trace">trace_id: {{ traceId ?? 'unavailable' }}</p>
    <button type="button" class="mp-button mp-button-outline mt-4" @click="$emit('retry')">
      Qayta urinish
    </button>
  </div>
</template>
