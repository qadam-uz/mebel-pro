<script setup lang="ts">
import { useToast, type Toast } from '@/shared/composables/useToast'

// Single global toast outlet (CB-14). Mounted once in AppShell; renders the
// shared queue bottom-centre over everything via a body teleport.
const { toasts, dismiss } = useToast()

function runToastAction(toast: Toast) {
  toast.action?.()
  dismiss(toast.id)
}
</script>

<template>
  <Teleport to="body">
    <div class="mp-toast-host" aria-live="polite" aria-atomic="false">
      <TransitionGroup name="mp-toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="mp-toast"
          :class="`mp-toast-${toast.tone}`"
          role="status"
        >
          <span class="min-w-0 flex-1">{{ toast.message }}</span>
          <button
            v-if="toast.actionLabel && toast.action"
            type="button"
            class="shrink-0 text-sm font-extrabold underline"
            @click="runToastAction(toast)"
          >
            {{ toast.actionLabel }}
          </button>
          <button
            type="button"
            class="mp-toast-close"
            aria-label="Yopish"
            @click="dismiss(toast.id)"
          >
            ×
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
