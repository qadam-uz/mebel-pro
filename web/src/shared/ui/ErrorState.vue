<script setup lang="ts">
// Error state with room for a trace_id line + a retry button. Design system
// .st-error. Pass an ApiError (or any object with .traceId) or a raw traceId.
import { computed } from 'vue'
import { t } from '@/shared/i18n'
import AppButton from './AppButton.vue'

const props = defineProps<{
  title?: string
  message?: string
  traceId?: string
  error?: { traceId?: string; detail?: string }
  retry?: () => void
}>()

const trace = computed(() => props.traceId ?? props.error?.traceId)
const message = computed(() => props.message ?? props.error?.detail ?? t('common.loadFailedBody'))
</script>

<template>
  <div class="st-error" role="alert">
    <div class="ic" aria-hidden="true">!</div>
    <h3>{{ title ?? t('common.loadFailed') }}</h3>
    <p>{{ message }}</p>
    <p v-if="trace" class="trace">
      {{ t('common.traceId') }}: <b>{{ trace }}</b>
    </p>
    <AppButton v-if="retry" variant="outline" @click="retry">↻ {{ t('common.retry') }}</AppButton>
  </div>
</template>
