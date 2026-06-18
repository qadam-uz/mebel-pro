<script setup lang="ts">
import { computed } from 'vue'

import type { CuttingPanel, CuttingPlacement, CuttingResult } from '@/shared/stores/cutting'

// The viewBox stays in raw panel mm, but a label only renders when its placement
// is large enough at a normalized 800-unit width (mirrors the prototype): the
// font size and the visibility threshold are expressed against that scale so a
// 2800mm panel and a 900mm panel read the same on screen.
const NORM_WIDTH = 800
const LABEL_FONT = 11
const LABEL_MIN_W = 80
const LABEL_MIN_H = 30

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
const normScale = computed(() => NORM_WIDTH / panelLength.value)
const labelFontSize = computed(() => LABEL_FONT / normScale.value)

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

function labelFits(placement: CuttingPlacement) {
  return (
    placement.length_mm * normScale.value > LABEL_MIN_W &&
    placement.width_mm * normScale.value > LABEL_MIN_H
  )
}
</script>

<template>
  <svg
    class="block h-auto w-full rounded-md border border-hairline-strong bg-elevated"
    :viewBox="viewBox"
    style="touch-action: pinch-zoom"
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
    <g
      v-for="placement in panel.placements"
      :key="placement.id"
      class="placement"
      role="button"
      tabindex="0"
      :aria-label="label(placement)"
      @click="emit('select-placement', placement)"
      @keydown.enter.prevent="emit('select-placement', placement)"
      @keydown.space.prevent="emit('select-placement', placement)"
    >
      <rect
        :x="placement.x_mm"
        :y="svgY(placement)"
        :width="placement.length_mm"
        :height="placement.width_mm"
        :fill="placement.id === activePlacementId ? '#c8e8e3' : '#dbeafe'"
        stroke="#2563eb"
        stroke-width="1.5"
      />
      <text
        v-if="labelFits(placement)"
        :x="placement.x_mm + labelFontSize * 0.5"
        :y="svgY(placement) + labelFontSize * 1.15"
        fill="#0f172a"
        :font-size="labelFontSize"
        font-family="sans-serif"
        aria-hidden="true"
      >
        {{ label(placement) }}
      </text>
    </g>
  </svg>
</template>

<style scoped>
.placement {
  cursor: pointer;
  outline: none;
}

/* A clear, scale-independent focus ring for keyboard users (CB-07). */
.placement:focus-visible rect {
  stroke: #0f766e;
  stroke-width: 2.5;
  vector-effect: non-scaling-stroke;
}
</style>
