<script setup lang="ts">
import type { EdgeRegistryEntry } from '@/shared/app/cuttingEditorDerived'

defineProps<{
  entries: EdgeRegistryEntry[]
  labelForMaterial: (materialId: string) => string
  narrowWarningForEntry?: (entry: EdgeRegistryEntry) => string | null
}>()

const emit = defineEmits<{
  replace: [entry: EdgeRegistryEntry]
}>()

function entryStyle(entry: EdgeRegistryEntry) {
  return {
    background: entry.colorStyle.soft,
    borderColor: entry.colorStyle.bg,
    color: entry.colorStyle.bg,
  }
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-2" aria-label="Kromkalar">
    <button
      v-for="entry in entries"
      :key="entry.key"
      type="button"
      class="mp-chip border border-hairline-strong"
      :style="entryStyle(entry)"
      @click="emit('replace', entry)"
    >
      <span
        class="grid size-5 place-items-center rounded-full border border-current bg-elevated text-xs font-black text-current"
      >
        {{ entry.number }}
      </span>
      <span class="whitespace-normal text-left text-xs font-semibold leading-tight">
        {{ labelForMaterial(entry.materialId) }}
      </span>
      <span
        v-if="narrowWarningForEntry?.(entry)"
        class="rounded-full bg-warning-soft px-2 py-0.5 text-[10px] font-black text-warning"
        :title="narrowWarningForEntry?.(entry) ?? undefined"
      >
        Qirradan tor
      </span>
    </button>
  </div>
</template>
