<script setup lang="ts">
import Icon from '@/shared/components/AppIcon.vue'
import type { EdgeRegistryEntry } from '@/shared/app/cuttingEditorDerived'

defineProps<{
  entries: EdgeRegistryEntry[]
  labelForMaterial: (materialId: string) => string
}>()

const emit = defineEmits<{
  replace: [entry: EdgeRegistryEntry]
  add: []
}>()
</script>

<template>
  <div class="flex flex-wrap items-center gap-2" aria-label="Kromkalar">
    <button
      v-for="entry in entries"
      :key="entry.key"
      type="button"
      class="mp-chip border border-hairline-strong bg-elevated"
      @click="emit('replace', entry)"
    >
      <span
        class="grid size-5 place-items-center rounded-full text-xs font-black"
        :class="entry.colorClass"
      >
        {{ entry.number }}
      </span>
      <span class="max-w-44 truncate">{{ labelForMaterial(entry.materialId) }}</span>
    </button>
    <button
      type="button"
      class="mp-chip border border-dashed border-hairline-strong"
      @click="emit('add')"
    >
      <Icon name="plus" class="size-3.5" />
      Kromka
    </button>
  </div>
</template>
