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

function badgeStyle(entry: EdgeRegistryEntry) {
  return {
    background: entry.colorStyle.bg,
    color: entry.colorStyle.fg,
  }
}
</script>

<template>
  <div
    class="flex flex-wrap items-center gap-x-5 gap-y-2"
    :aria-label="$t('cutting.edge.listAria')"
  >
    <button
      v-for="entry in entries"
      :key="entry.key"
      type="button"
      class="inline-flex min-w-0 items-center gap-2 rounded-md px-1 py-0.5 text-left transition hover:bg-sunk"
      @click="emit('replace', entry)"
    >
      <span
        class="grid size-5 shrink-0 place-items-center rounded-full text-xs font-black"
        :style="badgeStyle(entry)"
      >
        {{ entry.number }}
      </span>
      <span
        class="min-w-0 whitespace-normal text-left text-xs font-medium leading-tight text-ink-muted"
      >
        {{ labelForMaterial(entry.materialId) }}
      </span>
      <span
        v-if="narrowWarningForEntry?.(entry)"
        class="rounded-full bg-warning-soft px-2 py-0.5 text-[10px] font-black text-warning"
        :title="narrowWarningForEntry?.(entry) ?? undefined"
      >
        {{ $t('cutting.edge.tooNarrow') }}
      </span>
    </button>
  </div>
</template>
