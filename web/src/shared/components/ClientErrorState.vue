<script setup lang="ts">
// Shared client-facing load-error block (CB-22). Replaces the hand-copied
// `.client-error` markup across the client views so the title, trace label, and
// retry affordance stay consistent.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { traceLine } from '@/shared/app/errorTrace'

const props = withDefaults(
  defineProps<{
    title: string
    traceId?: string | null
    message?: string
  }>(),
  { traceId: null },
)

defineEmits<{ retry: [] }>()

const { t } = useI18n()

// Resolved on render, not as a prop default: a default is evaluated once and
// would keep whichever locale was active when the module first ran.
const messageText = computed(() => props.message ?? t('shell.errorState.message'))
</script>

<template>
  <div class="client-error">
    <div class="client-error-icon">!</div>
    <h3>{{ title }}</h3>
    <p>{{ messageText }}</p>
    <p class="client-trace">{{ traceLine(traceId) }}</p>
    <button type="button" class="mp-button mp-button-outline mt-4" @click="$emit('retry')">
      {{ $t('shell.action.retry') }}
    </button>
  </div>
</template>
