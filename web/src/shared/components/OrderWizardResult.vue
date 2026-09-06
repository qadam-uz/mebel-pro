<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  deriveSnapshotEdgeRegistry,
  panelDisplayIndex,
  panelFillPercent,
  resultTotals,
  sheetEdgeLine,
  squareMetres,
} from '@/shared/app/cuttingResultsDisplay'
import { materialSwatchStyle } from '@/shared/app/cuttingDisplay'
import { snapshotMaterialLabel, snapshotSheetSize, snapshotValue } from '@/shared/app/materialLabel'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import { useCuttingStore, type CuttingResult } from '@/shared/stores/cutting'

// Step 3 of the staff order flow, drawn to the handoff prototype: one card that
// answers "what will this cost me in boards", then one card that shows every
// sheet. Deliberately its own component rather than a mode of
// `CuttingResultsSection` — that one is the client SPA's and a revision's
// screen, built around a price receipt and a single selected drawing, and
// bending it into this shape would leave both halves compromised.
const props = defineProps<{ result: CuttingResult }>()

// One grid cell is 370px minimum; the map sits inside the cell's own box.
const CELL_MAP_WIDTH_PX = 356

const { t } = useI18n()
const cutting = useCuttingStore()

const totals = computed(() => resultTotals(props.result))

function swatchFor(materialId: string) {
  return materialSwatchStyle(props.result.material_snapshots[materialId])
}

function materialSize(materialId: string) {
  const snapshot = props.result.material_snapshots[materialId]
  const { length, width } = snapshotSheetSize(snapshot)
  const thickness = snapshotValue(snapshot, 'thickness_mm', 'qalinlik_mm')
  if (length <= 0 || width <= 0) return ''
  const base = `${length}×${width}`
  return thickness ? `${base}×${Number(thickness)}` : base
}

// Averaged over this material's own panels: a material is judged against itself,
// not against a result-wide figure two materials would have to share.
function materialFill(materialId: string) {
  const panels = props.result.panels.filter((panel) => panel.material_id === materialId)
  const { length, width } = snapshotSheetSize(props.result.material_snapshots[materialId])
  if (panels.length === 0 || length <= 0 || width <= 0) return null
  const waste = panels.reduce((sum, panel) => sum + panel.waste_area_mm2, 0)
  return Math.max(0, Math.min(100, 100 - (waste / (length * width * panels.length)) * 100))
}

const planRows = computed(() =>
  Object.entries(props.result.panels_used_by_material)
    .filter(([, count]) => count > 0)
    .map(([id, sheets]) => ({
      id,
      sheets,
      label: snapshotMaterialLabel(props.result.material_snapshots[id], id.slice(0, 8)),
      swatch: swatchFor(id),
      size: materialSize(id),
      own: (props.result.own_panel_counts?.[id] ?? 0) > 0,
      fill: materialFill(id),
      parts: (props.result.parts_snapshot ?? [])
        .filter((part) => part.material_id === id)
        .reduce((sum, part) => sum + part.quantity, 0),
    }))
    .sort((left, right) => left.label.localeCompare(right.label, 'uz')),
)

/** `metres()` carries its own unit, which the KPI cell prints separately — it
 *  would read "26.38 m m". */
function bareMetres(mm: number) {
  return (mm / 1000).toFixed(2)
}

/** The six figures the operator reads out loud, value first. They replaced a
 *  label/value list in an aside: the same numbers, but a list beside the plan
 *  rows made them look like a footnote to the materials rather than the result
 *  of the whole optimisation. */
const kpiRows = computed(() => {
  const value = totals.value
  const fills = planRows.value
    .map((row) => row.fill)
    .filter((fill): fill is number => fill !== null)
  const usedPercent = fills.length
    ? Math.round(fills.reduce((sum, fill) => sum + fill, 0) / fills.length)
    : 0
  return [
    {
      key: 'sheets',
      value: String(value.sheets),
      unit: t('cutting.unit.sheet', value.sheets),
      label: t('cutting.result.kpiSheets'),
    },
    {
      key: 'parts',
      value: String(value.placedParts),
      unit: t('cutting.unit.part', value.placedParts),
      label: t('cutting.result.kpiPlaced'),
    },
    { key: 'fill', value: String(usedPercent), unit: '%', label: t('cutting.result.kpiFill') },
    // An em dash rather than 0: a drawing with no banding has no tape figure,
    // and a zero invites the reader to look for one.
    {
      key: 'edge',
      value: value.edgeConsumedMm > 0 ? bareMetres(value.edgeConsumedMm) : '\u2014',
      unit: value.edgeConsumedMm > 0 ? t('cutting.unit.metre') : '',
      label: t('cutting.result.kpiEdge'),
    },
    {
      key: 'offcuts',
      value: value.usableOffcutCount ? squareMetres(value.usableOffcutAreaMm2) : '\u2014',
      unit: value.usableOffcutCount ? t('cutting.unit.areaM2') : '',
      label: t('cutting.result.kpiOffcuts'),
    },
    {
      key: 'cut',
      value: bareMetres(value.cutLengthMm),
      unit: t('cutting.unit.metre'),
      label: t('cutting.result.kpiCut'),
    },
  ]
})

const edgeRegistry = computed(() => deriveSnapshotEdgeRegistry(props.result.parts_snapshot ?? []))

const sheets = computed(() =>
  props.result.panels.map((panel) => ({
    panel,
    index: panelDisplayIndex(props.result, panel),
    label: snapshotMaterialLabel(
      props.result.material_snapshots[panel.material_id],
      panel.material_id.slice(0, 8),
    ),
    swatch: swatchFor(panel.material_id),
    size: materialSize(panel.material_id),
    edgeLine: sheetEdgeLine(props.result, panel, edgeRegistry.value),
    fill: panelFillPercent(props.result, panel),
    own: (props.result.own_panel_counts?.[panel.material_id] ?? 0) > 0,
  })),
)

// Three literal keys — an interpolated one escapes `pnpm i18n:check` entirely.
function sourceLabel(own: boolean) {
  if (!own) return t('cutting.source.shop')
  return cutting.scope === 'client' ? t('cutting.source.ownClient') : t('cutting.source.own')
}
</script>

<template>
  <div>
    <section class="card">
      <div class="card-b !pt-[22px]">
        <div class="mb-[18px] flex flex-wrap items-baseline gap-3.5">
          <h2 class="font-display text-[19px] font-bold tracking-[-0.02em] text-ink">
            {{ $t('cutting.result.title') }}
          </h2>
          <span
            class="inline-flex items-center rounded-full px-2.5 py-[3px] text-[12.5px] font-semibold"
            :class="
              totals.placedParts >= totals.requestedParts
                ? 'bg-success-soft text-success'
                : 'bg-danger-soft text-danger'
            "
          >
            {{
              $t('cutting.result.placed', {
                placed: totals.placedParts,
                requested: totals.requestedParts,
              })
            }}
          </span>
        </div>

        <!-- Six figures across the top, hairline-separated. The gap IS the rule:
             a 1px grid gap over a divider-coloured backdrop draws the lines, so
             the cells reflow at any count without a border that ends up doubled
             or orphaned at a wrap. -->
        <dl
          class="mb-5 grid gap-px overflow-hidden rounded-xl bg-divider [grid-template-columns:repeat(auto-fit,minmax(132px,1fr))]"
        >
          <div v-for="row in kpiRows" :key="row.key" class="bg-sunk px-3.5 pb-[13px] pt-3">
            <dd class="flex items-baseline gap-1">
              <span
                class="num font-display text-[23px] font-bold leading-none tracking-[-0.03em] text-ink"
              >
                {{ row.value }}
              </span>
              <span v-if="row.unit" class="text-xs font-semibold text-ink-soft">{{
                row.unit
              }}</span>
            </dd>
            <dt class="mt-[5px] text-[11.5px] text-ink-muted">{{ row.label }}</dt>
          </div>
        </dl>

        <div
          v-for="row in planRows"
          :key="row.id"
          class="grid items-center gap-3.5 border-t border-divider py-[13px] [grid-template-columns:30px_minmax(0,1fr)_auto_168px]"
        >
          <span
            class="size-[30px] rounded-lg border border-hairline"
            :style="row.swatch"
            aria-hidden="true"
          ></span>
          <span class="min-w-0">
            <span class="block truncate text-sm font-semibold text-ink">{{ row.label }}</span>
            <span class="num block text-[12.5px] text-ink-muted">
              {{ row.size }} · {{ row.parts }} {{ $t('cutting.unit.part', row.parts) }}
            </span>
          </span>
          <span
            class="inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-[3px] text-[11px] font-bold"
            :class="row.own ? 'bg-track text-ink' : 'bg-neutral-soft text-ink-nav'"
          >
            {{ sourceLabel(row.own) }}
          </span>
          <span class="flex items-center gap-2.5">
            <span
              v-if="row.fill !== null"
              class="block h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-track"
              aria-hidden="true"
            >
              <span
                class="block h-full rounded-full bg-accent"
                :style="{ width: `${row.fill}%` }"
              ></span>
            </span>
            <span
              v-if="row.fill !== null"
              class="num flex-none whitespace-nowrap text-xs text-ink-soft"
            >
              {{ row.fill.toFixed(0) }}%
            </span>
            <span
              class="num w-[52px] flex-none whitespace-nowrap text-right text-[13px] font-bold text-ink"
            >
              {{ row.sheets }} {{ $t('cutting.unit.sheet', row.sheets) }}
            </span>
          </span>
        </div>
      </div>
    </section>

    <section v-if="sheets.length > 0" class="card mt-[18px]">
      <div class="card-b !pt-[22px]">
        <h2 class="mb-[18px] font-display text-[19px] font-bold tracking-[-0.02em] text-ink">
          {{ $t('cutting.result.mapTitle') }}
        </h2>
        <div class="grid gap-[22px] [grid-template-columns:repeat(auto-fill,minmax(370px,1fr))]">
          <div v-for="sheet in sheets" :key="sheet.panel.id" class="min-w-0">
            <div class="mb-2 flex items-center gap-2.5">
              <span
                class="size-[26px] shrink-0 rounded-[7px] border border-hairline"
                :style="sheet.swatch"
                aria-hidden="true"
              ></span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-[13.5px] font-semibold text-ink">
                  {{ $t('cutting.result.sheetLabel', { n: sheet.index }) }} · {{ sheet.label }}
                </span>
                <span v-if="sheet.size || sheet.edgeLine" class="num block text-xs text-ink-muted">
                  {{ [sheet.size, sheet.edgeLine].filter(Boolean).join(' · ') }}
                </span>
              </span>
              <span
                class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold"
                :class="sheet.own ? 'bg-track text-ink' : 'bg-neutral-soft text-ink-nav'"
              >
                {{ sourceLabel(sheet.own) }}
              </span>
              <span
                class="num shrink-0 rounded-full bg-success-soft px-2.5 py-[3px] text-[12.5px] font-bold text-success"
              >
                {{ sheet.fill }}
              </span>
            </div>
            <!-- Told its real width: the label thresholds are expressed against
                 an 800px drawing, and left at that a 2800mm sheet would print
                 5px text in a 356px cell. -->
            <CuttingPanelSvg
              :result="result"
              :panel="sheet.panel"
              :render-width-px="CELL_MAP_WIDTH_PX"
            />
          </div>
        </div>
        <p class="num mt-3 text-right text-xs text-ink-muted">
          {{
            $t('cutting.result.cutSettings', { kerf: result.kerf_mm, trim: result.edge_trim_mm })
          }}
        </p>
      </div>
    </section>
  </div>
</template>
