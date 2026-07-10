<script setup lang="ts">
import type { CuttingPanel, CuttingResult } from '@/shared/stores/cutting'

defineProps<{
  result: CuttingResult
  activePanelId: string | null
}>()

const emit = defineEmits<{
  select: [panelId: string]
}>()

function numberSnapshot(value: unknown, fallback: number) {
  if (typeof value === 'number') return value
  if (typeof value === 'string' && value.trim()) return Number(value)
  return fallback
}

function snapshot(result: CuttingResult, panel: CuttingPanel) {
  return result.material_snapshots[panel.material_id] ?? {}
}

function panelLength(result: CuttingResult, panel: CuttingPanel) {
  return numberSnapshot(snapshot(result, panel).panel_length_mm, 1000)
}

function panelWidth(result: CuttingResult, panel: CuttingPanel) {
  return numberSnapshot(snapshot(result, panel).panel_width_mm, 700)
}

function viewBox(result: CuttingResult, panel: CuttingPanel) {
  return `0 0 ${panelLength(result, panel)} ${panelWidth(result, panel)}`
}

function placementY(result: CuttingResult, panel: CuttingPanel, y: number, width: number) {
  return panelWidth(result, panel) - y - width
}

function materialShortName(result: CuttingResult, panel: CuttingPanel) {
  const row = snapshot(result, panel)
  const decor = typeof row.decor_code === 'string' ? row.decor_code : ''
  const name = typeof row.name === 'string' ? row.name : ''
  return decor || name || panel.material_id.slice(0, 8)
}
</script>

<template>
  <div class="flex gap-3 overflow-x-auto pb-1" aria-label="Listlar">
    <button
      v-for="panel in result.panels"
      :key="panel.id"
      type="button"
      class="grid w-32 shrink-0 gap-1 rounded-md border p-2 text-left transition hover:border-accent"
      :class="
        panel.id === activePanelId ? 'border-accent bg-accent-soft' : 'border-hairline bg-elevated'
      "
      :aria-pressed="panel.id === activePanelId"
      @click="emit('select', panel.id)"
    >
      <svg
        class="h-20 w-full rounded border border-hairline bg-sunk"
        :viewBox="viewBox(result, panel)"
        aria-hidden="true"
      >
        <rect
          x="0"
          y="0"
          :width="panelLength(result, panel)"
          :height="panelWidth(result, panel)"
          fill="var(--color-elevated)"
          stroke="var(--color-accent)"
          stroke-width="10"
        />
        <rect
          v-for="placement in panel.placements"
          :key="placement.id"
          :x="placement.x_mm"
          :y="placementY(result, panel, placement.y_mm, placement.width_mm)"
          :width="placement.length_mm"
          :height="placement.width_mm"
          fill="var(--color-accent-soft)"
          stroke="var(--color-accent)"
          stroke-width="5"
        />
      </svg>
      <span class="truncate text-xs font-extrabold text-ink">
        {{ materialShortName(result, panel) }} · {{ panel.panel_index }}
      </span>
    </button>
  </div>
</template>
