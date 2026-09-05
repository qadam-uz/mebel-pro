<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { snapshotMaterialLabel } from '@/shared/app/cuttingDisplay'
import { panelDisplayIndex, panelFillPercent } from '@/shared/app/cuttingResultsDisplay'
import Icon from '@/shared/components/AppIcon.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import CuttingSheetThumbnails from '@/shared/components/CuttingSheetThumbnails.vue'
import {
  useCuttingStore,
  type CuttingPanel,
  type CuttingPlacement,
  type CuttingResult,
} from '@/shared/stores/cutting'

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
const cutting = useCuttingStore()

const drawingCard = ref<HTMLElement | null>(null)

/**
 * §7.0, phones: the full sheet drawing collapses behind «Chizmani ko'rish».
 *
 * At 358px a 2800mm sheet renders about 7× reduced — its part labels and its
 * offcut captions are simply not readable, so it is a picture of a rectangle
 * occupying most of a screen the client is trying to read a price off. The
 * thumbnails stay in the open (they answer "how many sheets, roughly how
 * full"), and the drawing is one tap away for anyone who wants it. Client only:
 * a shop reads this on a counter monitor.
 *
 * `open` is per-viewer state and deliberately not remembered — the disclosure
 * costs one tap and a remembered-open drawing would undo the reason for it.
 */
const isClientView = computed(() => cutting.scope === 'client')
const drawingOpen = ref(false)

// A selection made from a list has to reveal the drawing it points at, so
// `revealDrawing` opens the disclosure before scrolling to it.
function openDrawing() {
  drawingOpen.value = true
}

const activePanel = computed(
  () => props.result.panels.find((panel) => panel.id === props.activePanelId) ?? null,
)

function panelCaption(result: CuttingResult, panel: CuttingPanel) {
  const material = snapshotMaterialLabel(
    result.material_snapshots[panel.material_id],
    panel.material_id.slice(0, 8),
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
  openDrawing()
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

    <!-- Phones, client only (§7.0): the drawing is unreadable at this width, so
         it sits behind a disclosure. At `md` and up the section below renders
         open, exactly as it always has. -->
    <button
      v-if="isClientView && !drawingOpen"
      type="button"
      class="flex min-h-12 items-center justify-between gap-3 rounded-[11px] border border-hairline bg-elevated px-3.5 text-sm font-bold text-ink md:hidden"
      :aria-expanded="false"
      @click="openDrawing"
    >
      <span>{{ $t('cutting.result.showDrawing') }}</span>
      <Icon name="chevron-down" class="size-4 text-ink-muted" />
    </button>

    <section
      ref="drawingCard"
      class="rounded-lg border border-hairline bg-elevated p-4"
      :class="isClientView && !drawingOpen ? 'max-md:hidden' : ''"
    >
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
