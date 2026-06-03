<script setup lang="ts">
import { computed } from 'vue'

import type { CuttingPanel, CuttingPlacement, CuttingResult } from '@/shared/stores/cutting'

const props = defineProps<{
  result: CuttingResult
  panel: CuttingPanel
  activePlacementId?: string | null
}>()

const emit = defineEmits<{
  'select-placement': [placement: CuttingPlacement]
}>()

const material = computed(() => props.result.material_snapshots[props.panel.material_id] ?? {})
const panelLength = computed(() => numberSnapshot(material.value.panel_length_mm, 1000))
const panelWidth = computed(() => numberSnapshot(material.value.panel_width_mm, 700))
const viewBox = computed(() => `0 0 ${panelLength.value} ${panelWidth.value}`)

function numberSnapshot(value: unknown, fallback: number) {
  if (typeof value === 'number') return value
  if (typeof value === 'string' && value.trim()) return Number(value)
  return fallback
}

function svgY(placement: CuttingPlacement) {
  return panelWidth.value - placement.y_mm - placement.width_mm
}

function label(placement: CuttingPlacement) {
  return `${placement.part_ref} #${placement.part_quantity_index}${placement.rotated ? ' R' : ''}`
}
</script>

<template>
  <svg
    class="block h-auto w-full rounded-md border border-hairline-strong bg-elevated"
    :viewBox="viewBox"
    role="img"
    :aria-label="`Panel ${panel.panel_index} layout`"
  >
    <rect
      x="0"
      y="0"
      :width="panelLength"
      :height="panelWidth"
      fill="white"
      stroke="#334155"
      stroke-width="2"
    />
    <g v-for="placement in panel.placements" :key="placement.id">
      <rect
        :x="placement.x_mm"
        :y="svgY(placement)"
        :width="placement.length_mm"
        :height="placement.width_mm"
        :fill="placement.id === activePlacementId ? '#c8e8e3' : '#dbeafe'"
        stroke="#2563eb"
        stroke-width="1.5"
        role="button"
        tabindex="0"
        @click="emit('select-placement', placement)"
        @keydown.enter.prevent="emit('select-placement', placement)"
        @keydown.space.prevent="emit('select-placement', placement)"
      />
      <text
        :x="placement.x_mm + 8"
        :y="svgY(placement) + 18"
        fill="#0f172a"
        font-size="14"
        font-family="sans-serif"
      >
        {{ label(placement) }}
      </text>
    </g>
  </svg>
</template>
