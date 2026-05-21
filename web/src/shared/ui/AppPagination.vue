<script setup lang="ts">
// Simple prev / page-of / next pager. v-model:page is 1-based.
import { computed } from 'vue'
import { t } from '@/shared/i18n'
import AppButton from './AppButton.vue'

const props = defineProps<{
  page: number
  pageCount: number
}>()

const emit = defineEmits<{ 'update:page': [value: number] }>()

const canPrev = computed(() => props.page > 1)
const canNext = computed(() => props.page < props.pageCount)

function go(next: number) {
  if (next >= 1 && next <= props.pageCount) emit('update:page', next)
}
</script>

<template>
  <nav
    class="flex"
    style="align-items: center; justify-content: flex-end"
    :aria-label="t('common.page')"
  >
    <AppButton variant="outline" size="sm" :disabled="!canPrev" @click="go(page - 1)">←</AppButton>
    <span class="muted num" style="font-size: 12.5px">{{ page }} / {{ pageCount }}</span>
    <AppButton variant="outline" size="sm" :disabled="!canNext" @click="go(page + 1)">→</AppButton>
  </nav>
</template>
