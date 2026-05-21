<script setup lang="ts">
// Searchable material picker over /c/materials. Mirrors prototype modal.
import { computed, ref, watch } from 'vue'
import { AppModal } from '@/shared/ui'
import { t } from '@/shared/i18n'
import type { Material } from '../api/types'
import { swatchFor } from '../lib/cutting'

const props = defineProps<{ open: boolean; materials: Material[] }>()
const emit = defineEmits<{ 'update:open': [v: boolean]; pick: [m: Material] }>()

const query = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) query.value = ''
  },
)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  return props.materials.filter(
    (m) =>
      !q || `${m.name}${m.thickness_mm}${m.color}${m.decor_code ?? ''}`.toLowerCase().includes(q),
  )
})

function pick(m: Material) {
  emit('pick', m)
  emit('update:open', false)
}
</script>

<template>
  <AppModal
    :open="open"
    :title="t('client.materialPickTitle')"
    @update:open="emit('update:open', $event)"
  >
    <input v-model="query" class="mat-search" :placeholder="t('client.materialSearch')" />
    <div class="mat-list">
      <div v-if="filtered.length === 0" class="empty">
        <p>{{ t('client.materialNotFound') }}</p>
      </div>
      <button
        v-for="m in filtered"
        v-else
        :key="m.id"
        type="button"
        class="mat-opt"
        @click="pick(m)"
      >
        <span class="sw" :style="{ background: swatchFor(m.id) }" />
        <div class="lab">
          <div class="nm">{{ m.name }}</div>
          <div class="meta">
            {{ m.thickness_mm }}mm · {{ m.sheet_length_mm }}×{{ m.sheet_width_mm
            }}{{ m.grain_direction ? ` · ${t('client.grain')}` : '' }}
          </div>
        </div>
      </button>
    </div>
  </AppModal>
</template>

<style scoped>
.mat-search {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--sunk);
  font: 500 13px var(--f-ui);
  color: var(--ink-12);
  margin-bottom: 10px;
  box-sizing: border-box;
}
.mat-search:focus {
  outline: 0;
  border-color: var(--ink-12);
}
.mat-list {
  max-height: 60vh;
  overflow-y: auto;
  padding: 4px 0;
}
.mat-opt {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  width: 100%;
  text-align: left;
  background: none;
  border: 0;
}
.mat-opt:hover {
  background: var(--sunk);
}
.mat-opt .sw {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}
.mat-opt .lab .nm {
  font: 500 13px var(--f-ui);
  color: var(--ink-12);
}
.mat-opt .lab .meta {
  font: 400 11.5px var(--f-mono);
  color: var(--ink-6);
  margin-top: 2px;
}
</style>
