<script setup lang="ts">
// Friendly empty state (no data yet, not an error). Design system .st-empty.
import { t } from '@/shared/i18n'

withDefaults(
  defineProps<{
    icon?: string
    title?: string
    body?: string
  }>(),
  { icon: '∅' },
)
</script>

<template>
  <div class="st-empty">
    <div class="ic" aria-hidden="true">{{ icon }}</div>
    <h3>{{ title ?? t('common.empty') }}</h3>
    <p v-if="body">{{ body }}</p>
    <slot />
  </div>
</template>
