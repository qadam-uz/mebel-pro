<script setup lang="ts">
import {
  drawnSheetSize,
  panelDisplayIndex,
  panelFillPercent,
} from '@/shared/app/cuttingResultsDisplay'
import { snapshotMaterialLabel } from '@/shared/app/materialLabel'
import type { CuttingPanel, CuttingResult } from '@/shared/stores/cutting'

defineProps<{
  result: CuttingResult
  activePanelId: string | null
}>()

const emit = defineEmits<{
  select: [panelId: string]
}>()

function snapshot(result: CuttingResult, panel: CuttingPanel) {
  return result.material_snapshots[panel.material_id] ?? {}
}

// Same resolver the full map and the PDF use: any of the three frozen snapshot
// vocabularies, else the layout's own extent, then widened to cover anything
// that sticks out of the recorded sheet. Never a constant — a thumbnail sized
// by a guess is silently the wrong shape.
function panelLength(result: CuttingResult, panel: CuttingPanel) {
  return drawnSheetSize(result, panel).length
}

function panelWidth(result: CuttingResult, panel: CuttingPanel) {
  return drawnSheetSize(result, panel).width
}

function viewBox(result: CuttingResult, panel: CuttingPanel) {
  return `0 0 ${panelLength(result, panel)} ${panelWidth(result, panel)}`
}

function placementY(result: CuttingResult, panel: CuttingPanel, y: number, width: number) {
  return panelWidth(result, panel) - y - width
}

function panelGroups(result: CuttingResult) {
  const groups: Array<{ materialId: string; label: string; panels: CuttingPanel[] }> = []
  const indexByMaterial = new Map<string, number>()
  for (const panel of result.panels) {
    let group = groups[indexByMaterial.get(panel.material_id) ?? -1]
    if (!group) {
      group = {
        materialId: panel.material_id,
        label: snapshotMaterialLabel(snapshot(result, panel), panel.material_id.slice(0, 8)),
        panels: [],
      }
      indexByMaterial.set(panel.material_id, groups.length)
      groups.push(group)
    }
    group.panels.push(panel)
  }
  return groups
}
</script>

<template>
  <div class="grid gap-3" :aria-label="$t('cutting.result.sheets')">
    <section v-for="group in panelGroups(result)" :key="group.materialId" class="grid gap-1.5">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h4 class="min-w-0 flex-1 text-sm font-extrabold leading-tight text-ink">
          {{ group.label }}
        </h4>
        <span class="text-xs font-bold text-ink-muted"
          >{{ group.panels.length }} {{ $t('cutting.unit.sheet', group.panels.length) }}</span
        >
      </div>
      <div class="flex gap-2 overflow-x-auto pb-1">
        <button
          v-for="panel in group.panels"
          :key="panel.id"
          type="button"
          class="grid w-24 shrink-0 gap-1 rounded-md border p-1.5 text-left transition hover:border-accent"
          :class="
            panel.id === activePanelId
              ? 'border-accent-tint bg-accent-soft'
              : 'border-hairline bg-elevated'
          "
          :aria-pressed="panel.id === activePanelId"
          @click="emit('select', panel.id)"
        >
          <span class="relative block">
            <svg
              class="h-14 w-full rounded border border-hairline bg-sunk"
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
            <span
              class="absolute bottom-1 right-1 rounded bg-elevated/95 px-1 py-0.5 text-[10.5px] font-black text-ink shadow-sm"
            >
              {{ panelFillPercent(result, panel) }}
            </span>
          </span>
          <span class="truncate text-[11px] font-extrabold text-ink">
            {{ $t('cutting.result.sheetLabel', { n: panelDisplayIndex(result, panel) }) }}
          </span>
        </button>
      </div>
    </section>
  </div>
</template>
