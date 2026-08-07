<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { snapshotMaterialLabel } from '@/shared/app/cuttingDisplay'
import { panelDisplayIndex, panelFillPercent } from '@/shared/app/cuttingResultsDisplay'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import CuttingSheetThumbnails from '@/shared/components/CuttingSheetThumbnails.vue'
import type { CuttingPanel, CuttingPlacement, CuttingResult } from '@/shared/stores/cutting'

// The sheet view of a finished result — thumbnail strip, the active sheet's
// drawing, and the cut settings it was produced with. Extracted so the cutting
// result page and a placed order's drawing tab render from one source: they had
// drifted into two different screens (chips vs. thumbnails, two near-identical
// caption helpers) while showing the same object.
//
// Takes a `CuttingResult` and nothing else — no draft, no quote, no checkout —
// so it works after the draft is consumed by an order.
const props = defineProps<{
  result: CuttingResult
  activePanelId: string | null
  activePartRef?: string | null
  activePlacementId?: string | null
}>()

const emit = defineEmits<{
  'update:activePanelId': [string | null]
  'select-placement': [CuttingPlacement]
  'clear-selection': []
}>()

const { t } = useI18n()

const drawingCard = ref<HTMLElement | null>(null)

const activePanel = computed(
  () => props.result.panels.find((panel) => panel.id === props.activePanelId) ?? null,
)

function panelCaption(result: CuttingResult, panel: CuttingPanel) {
  const material = snapshotMaterialLabel(
    result.material_snapshots[panel.branch_material_id],
    panel.branch_material_id.slice(0, 8),
  )
  return t('cutting.result.sheetCaption', {
    n: panelDisplayIndex(result, panel),
    material,
    fill: panelFillPercent(result, panel),
  })
}

/** Bring the drawing into view — the caller decides when (e.g. after a
 *  selection made from a list that sits above or below it). */
function revealDrawing() {
  void nextTick(() => {
    drawingCard.value?.scrollIntoView({ block: 'center', behavior: 'auto' })
  })
}

defineExpose({ revealDrawing })
</script>

<template>
  <div class="grid gap-4">
    <section class="rounded-lg border border-hairline bg-elevated p-4">
      <CuttingSheetThumbnails
        :result="result"
        :active-panel-id="activePanelId"
        @select="emit('update:activePanelId', $event)"
      />
    </section>

    <section ref="drawingCard" class="rounded-lg border border-hairline bg-elevated p-4">
      <p v-if="activePanel" class="mb-3 text-sm font-extrabold text-ink">
        {{ panelCaption(result, activePanel) }}
      </p>
      <CuttingPanelSvg
        v-if="activePanel"
        :result="result"
        :panel="activePanel"
        :active-part-ref="activePartRef ?? null"
        :active-placement-id="activePlacementId ?? null"
        fit="viewport"
        @select-placement="emit('select-placement', $event)"
        @clear-selection="emit('clear-selection')"
      />
      <p class="mt-2 text-right text-xs text-ink-muted">
        {{ $t('cutting.result.cutSettings', { kerf: result.kerf_mm, trim: result.edge_trim_mm }) }}
      </p>
    </section>
  </div>
</template>
