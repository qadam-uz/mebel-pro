<script setup lang="ts">
import { computed } from 'vue'

import { iconPath } from '@/shared/app/adminUi'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
    loading?: boolean
    label?: string
    loadingLabel?: string
  }>(),
  {
    disabled: false,
    loading: false,
    label: 'Yangilash',
    loadingLabel: 'Yangilanmoqda',
  },
)

defineEmits<{
  click: [event: MouseEvent]
}>()

const accessibleLabel = computed(() => (props.loading ? props.loadingLabel : props.label))
</script>

<template>
  <button
    type="button"
    class="admin-icon-button admin-refresh-button"
    :class="{ 'is-loading': loading }"
    :disabled="disabled || loading"
    :aria-label="accessibleLabel"
    :aria-busy="loading ? 'true' : undefined"
    :title="label"
    @click="$emit('click', $event)"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('refresh')"></svg>
  </button>
</template>
