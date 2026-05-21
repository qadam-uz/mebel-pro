<script setup lang="ts">
// Renders the shared toast queue. Mount once per app (in its layout). Uses the
// design system's .toast. Single-toast prototype look: shows the latest.
import { computed } from 'vue'
import { useToast } from '@/shared/composables/useToast'

const { toasts } = useToast()
const current = computed(() => toasts.value[toasts.value.length - 1] ?? null)
</script>

<template>
  <Teleport to="body">
    <div v-if="current" class="toast on" role="status" aria-live="polite">
      <span
        class="ic"
        :class="{ warn: current.kind === 'warn', danger: current.kind === 'danger' }"
      >
        {{ current.kind === 'ok' ? '✓' : '!' }}
      </span>
      <span class="msg">{{ current.message }}</span>
    </div>
  </Teleport>
</template>
