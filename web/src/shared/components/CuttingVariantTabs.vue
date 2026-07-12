<script setup lang="ts">
import { variantLabel } from '@/shared/app/cuttingResultsDisplay'
import type { CuttingResult } from '@/shared/stores/cutting'

const props = defineProps<{
  results: CuttingResult[]
  activeResultId: string | null
  chosenResultId: string | null
}>()

const emit = defineEmits<{
  select: [resultId: string]
}>()

function selectByOffset(current: CuttingResult, offset: number) {
  const index = props.results.findIndex((result) => result.id === current.id)
  if (index < 0) return
  const next = props.results[(index + offset + props.results.length) % props.results.length]
  if (next) emit('select', next.id)
}
</script>

<template>
  <div class="flex flex-wrap gap-2" role="tablist" aria-label="Natija variantlari">
    <button
      v-for="result in results"
      :id="`cutting-result-tab-${result.id}`"
      :key="result.id"
      type="button"
      role="tab"
      class="inline-flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm font-extrabold transition"
      :class="
        result.id === activeResultId
          ? 'border-accent bg-accent-soft text-accent'
          : 'border-hairline bg-elevated text-ink-soft hover:border-accent hover:text-accent'
      "
      :aria-selected="result.id === activeResultId"
      :tabindex="result.id === activeResultId ? 0 : -1"
      @click="emit('select', result.id)"
      @keydown.left.prevent="selectByOffset(result, -1)"
      @keydown.right.prevent="selectByOffset(result, 1)"
    >
      <span v-if="result.id === chosenResultId" aria-hidden="true">✓</span>
      <span>{{ variantLabel(result) }}</span>
      <span
        v-if="result.source === 'imported_map'"
        class="rounded bg-info-soft px-1.5 py-0.5 text-[11px] text-info"
      >
        Fayldan
      </span>
    </button>
  </div>
</template>
