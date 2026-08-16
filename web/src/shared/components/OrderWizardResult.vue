<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  deriveSnapshotEdgeRegistry,
  numberSnapshot,
  panelDisplayIndex,
  panelFillPercent,
  resultTotals,
  sheetEdgeLine,
  squareMetres,
} from '@/shared/app/cuttingResultsDisplay'
import { materialSwatchStyle } from '@/shared/app/cuttingDisplay'
import { snapshotMaterialLabel, snapshotValue } from '@/shared/app/materialLabel'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import { metres, useCuttingStore, type CuttingResult } from '@/shared/stores/cutting'

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
  const length = numberSnapshot(snapshotValue(snapshot, 'uzunlik_mm', 'panel_length_mm'), 0)
  const width = numberSnapshot(snapshotValue(snapshot, 'eni_mm', 'panel_width_mm'), 0)
  const thickness = snapshotValue(snapshot, 'qalinlik_mm', 'thickness_mm')
  if (length <= 0 || width <= 0) return ''
  const base = `${length}×${width}`
  return thickness ? `${base}×${Number(thickness)}` : base
}

// Averaged over this material's own panels: a material is judged against itself,
// not against a result-wide figure two materials would have to share.
function materialFill(materialId: string) {
  const panels = props.result.panels.filter((panel) => panel.branch_material_id === materialId)
  const snapshot = props.result.material_snapshots[materialId]
  const length = numberSnapshot(snapshotValue(snapshot, 'uzunlik_mm', 'panel_length_mm'), 0)
  const width = numberSnapshot(snapshotValue(snapshot, 'eni_mm', 'panel_width_mm'), 0)
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

const summaryRows = computed(() => {
  const value = totals.value
  const missing = Math.max(0, value.requestedParts - value.placedParts)
  return [
    {
      key: 'parts',
      label: t('cutting.result.summaryParts'),
      // The shortfall is spelled out, not only coloured: on a placed order in
      // the client app this row is the only shortage signal on the screen.
      value: missing
        ? t('cutting.result.summaryPartsShort', {
            placed: value.placedParts,
            requested: value.requestedParts,
            n: missing,
          })
        : `${value.placedParts} ${t('cutting.unit.piece', value.placedParts)}`,
      short: missing > 0,
    },
    {
      key: 'sheets',
      label: t('cutting.result.summarySheets'),
      value: `${value.sheets} ${t('cutting.unit.sheet', value.sheets)}`,
      short: false,
    },
    {
      key: 'cut',
      label: t('cutting.result.summaryCutLength'),
      value: metres(value.cutLengthMm),
      short: false,
    },
    {
      key: 'edge',
      label: t('cutting.result.summaryEdge'),
      // Em-dash, not "0.00 m": a drawing with no banding has no tape figure,
      // and a zero invites the reader to look for one.
      value: value.edgeConsumedMm > 0 ? metres(value.edgeConsumedMm) : '—',
      short: false,
    },
    {
      key: 'offcuts',
      label: t('cutting.result.summaryOffcuts'),
      value: value.usableOffcutCount
        ? `${squareMetres(value.usableOffcutAreaMm2)} ${t('cutting.unit.areaM2')}`
        : '—',
      short: false,
    },
  ]
})

const edgeRegistry = computed(() => deriveSnapshotEdgeRegistry(props.result.parts_snapshot ?? []))

const sheets = computed(() =>
  props.result.panels.map((panel) => ({
    panel,
    index: panelDisplayIndex(props.result, panel),
    label: snapshotMaterialLabel(
      props.result.material_snapshots[panel.branch_material_id],
      panel.branch_material_id.slice(0, 8),
    ),
    swatch: swatchFor(panel.branch_material_id),
    size: materialSize(panel.branch_material_id),
    edgeLine: sheetEdgeLine(props.result, panel, edgeRegistry.value),
    fill: panelFillPercent(props.result, panel),
    own: (props.result.own_panel_counts?.[panel.branch_material_id] ?? 0) > 0,
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

        <div class="grid items-start gap-[26px] lg:grid-cols-[minmax(0,1.6fr)_minmax(0,0.85fr)]">
          <div>
            <div
              v-for="row in planRows"
              :key="row.id"
              class="flex items-center gap-3 border-t border-divider py-3"
            >
              <span
                class="size-[30px] shrink-0 rounded-lg border border-hairline"
                :style="row.swatch"
                aria-hidden="true"
              ></span>
              <span class="min-w-0 flex-1">
                <span class="block text-sm font-semibold leading-tight text-ink">
                  {{ row.label }}
                </span>
                <span
                  class="mt-[3px] inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold"
                  :class="
                    row.own ? 'bg-accent-soft text-accent-strong' : 'bg-neutral-soft text-ink-nav'
                  "
                >
                  {{ sourceLabel(row.own) }}
                </span>
                <span class="num block text-[12.5px] text-ink-muted">
                  {{ row.size }} · {{ row.parts }} {{ $t('cutting.unit.part', row.parts) }}
                </span>
              </span>
              <span class="w-[120px] min-w-[92px] shrink-0">
                <span class="mb-[5px] flex items-baseline justify-between gap-2">
                  <span class="num text-[13px] font-bold text-ink">
                    {{ row.sheets }} {{ $t('cutting.unit.sheet', row.sheets) }}
                  </span>
                  <!-- The bar restates the number beside it; a bar that fails
                       to paint costs the reader nothing. -->
                  <span
                    v-if="row.fill !== null"
                    class="num whitespace-nowrap text-[11.5px] text-ink-soft"
                  >
                    {{ $t('cutting.result.fillUsed', { fill: `${row.fill.toFixed(0)}%` }) }}
                  </span>
                </span>
                <span
                  v-if="row.fill !== null"
                  class="block h-[5px] overflow-hidden rounded-full bg-track"
                  aria-hidden="true"
                >
                  <span
                    class="block h-full rounded-full bg-accent"
                    :style="{ width: `${row.fill}%` }"
                  ></span>
                </span>
              </span>
            </div>
          </div>

          <dl class="lg:border-l lg:border-divider lg:pl-[26px]">
            <div
              v-for="row in summaryRows"
              :key="row.key"
              class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-[7px]"
            >
              <dt class="text-[13px] text-ink-soft">{{ row.label }}</dt>
              <dd
                class="num shrink-0 text-right text-[13.5px] font-semibold"
                :class="row.short ? 'text-danger' : 'text-ink'"
              >
                {{ row.value }}
              </dd>
            </div>
            <p class="mt-2.5 text-[12.5px] leading-[1.45] text-ink-muted">
              {{ $t('cutting.result.offcutHint') }}
            </p>
          </dl>
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
                :class="
                  sheet.own ? 'bg-accent-soft text-accent-strong' : 'bg-neutral-soft text-ink-nav'
                "
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
