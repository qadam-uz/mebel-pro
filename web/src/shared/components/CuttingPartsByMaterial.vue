<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  sideLabels,
  snapshotEdgeLabel,
  snapshotMaterialLabel,
  type EdgeField,
} from '@/shared/app/cuttingDisplay'
import {
  edgeRegistryKey,
  groupCuttingParts,
  partDisplayName,
  registryEntryForBand,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import { deriveSnapshotEdgeRegistry } from '@/shared/app/cuttingResultsDisplay'
import Icon from '@/shared/components/AppIcon.vue'
import { type CuttingPart, type CuttingResult } from '@/shared/stores/cutting'

// The drawing editor's parts list, read-only: grouped by panel material, same
// columns, the same rotation glyph and the same numbered edge-tape registry, so
// a client comparing a placed order against what they entered reads one layout
// rather than two.
//
// Takes a `CuttingResult` — parts and material snapshots both live on it — so
// it works anywhere a result exists, including after the draft was consumed by
// an order.
const props = defineProps<{ result: CuttingResult }>()

const { t } = useI18n()

const edgeSides: EdgeField[] = ['edge_top', 'edge_bottom', 'edge_left', 'edge_right']

const edgeRegistry = computed(() => deriveSnapshotEdgeRegistry(props.result.parts_snapshot ?? []))
const groups = computed(() =>
  groupCuttingParts(props.result.parts_snapshot ?? [], (materialId) =>
    materialId ? materialLabelFor(materialId) : t('cutting.material.unassigned'),
  ),
)

function materialLabelFor(materialId: string) {
  return snapshotMaterialLabel(props.result.material_snapshots[materialId] ?? {}, materialId)
}

/** The tape's label. `name` was the catalog's stored column — "Kromka Egger
 *  H1137 · Kulrang eman · 2×19 mm" — and it survives only inside pre-reshape
 *  snapshots, which are frozen history: reading it first is what keeps an old
 *  order rendering the exact string it always did. Post-reshape snapshots have
 *  no `name`, so they compose through `snapshotEdgeLabel`, the mirror of the
 *  backend's `edge_label()`. The two differ slightly (the composed form has no
 *  "Kromka" prefix), so an old and a new order can show the same tape a little
 *  differently — the alternative is rewriting history's labels. */
function edgeLabelFor(materialId: string) {
  const snapshot = props.result.material_snapshots[materialId]
  const name = typeof snapshot?.name === 'string' ? snapshot.name.trim() : ''
  return name || snapshotEdgeLabel(snapshot, materialId.slice(0, 8))
}

/** Only the tapes a given material group actually uses — the editor's rule. */
function groupEdgeEntries(group: { parts: Array<{ part: CuttingPart }> }) {
  const keys = new Set<string>()
  for (const { part } of group.parts) {
    for (const side of edgeSides) {
      const band = part[side]
      if (band?.material_id) keys.add(edgeRegistryKey(band.material_id, band.source))
    }
  }
  return edgeRegistry.value.filter((entry) => keys.has(entry.key))
}

/** The four-sided glyph: a coloured border per banded side, dashed where bare. */
function edgeGlyphStyle(part: CuttingPart) {
  const sideStyles = {
    edge_top: 'borderTop',
    edge_bottom: 'borderBottom',
    edge_left: 'borderLeft',
    edge_right: 'borderRight',
  } as const
  return Object.fromEntries(
    Object.entries(sideStyles).map(([side, property]) => {
      const band = part[side as EdgeField]
      const entry = registryEntryForBand(edgeRegistry.value, band?.material_id, band?.source)
      return [
        property,
        entry ? `3px solid ${entry.colorStyle.bg}` : '1px dashed var(--color-hairline-strong)',
      ]
    }),
  )
}

function edgeBadgeStyle(entry: EdgeRegistryEntry) {
  return { background: entry.colorStyle.bg, color: entry.colorStyle.fg }
}

/** Names the banded sides — the glyph alone is colour-only, which the design
 *  system does not accept as the sole signal. */
function edgeSidesLabel(part: CuttingPart) {
  const banded = edgeSides.filter((side) => part[side]?.material_id).map((side) => sideLabels[side])
  return banded.length
    ? t('cutting.parts.edgeSides', { sides: banded.join(' · ') })
    : t('cutting.parts.noEdge')
}
</script>

<template>
  <div v-if="!groups.length" class="text-sm text-ink-muted">
    {{ $t('cutting.parts.emptyResult') }}
  </div>
  <!-- Read-only twin of the drawing editor's list: same grouping by
               material, same columns and glyphs, so a client comparing the
               order against what they entered reads one layout, not two. -->
  <div v-else class="grid gap-4">
    <section
      v-for="group in groups"
      :key="group.key"
      class="overflow-hidden rounded-lg border border-hairline"
    >
      <div
        class="flex flex-wrap items-center justify-between gap-3 border-b border-hairline bg-sunk px-3 py-2"
      >
        <span class="text-sm font-bold text-ink">{{ group.label }}</span>
        <span class="shrink-0 text-xs text-ink-muted">
          {{ group.quantity }} {{ $t('cutting.unit.part', group.quantity) }} ·
          {{ group.areaM2.toFixed(2) }} {{ $t('cutting.unit.areaM2') }}
        </span>
      </div>

      <!-- Read-only twin of the editor's tape registry: same numbers
                   and colours, but plain spans — replacing a tape is an
                   editing action and this order is already placed. -->
      <div
        v-if="groupEdgeEntries(group).length"
        class="flex flex-wrap gap-x-4 gap-y-1.5 border-b border-hairline px-3 py-2"
      >
        <span
          v-for="entry in groupEdgeEntries(group)"
          :key="entry.key"
          class="inline-flex min-w-0 items-center gap-2"
        >
          <span
            class="grid size-5 shrink-0 place-items-center rounded-full text-xs font-black"
            :style="edgeBadgeStyle(entry)"
            >{{ entry.number }}</span
          >
          <span class="min-w-0 text-xs font-medium leading-tight text-ink-muted">
            {{ edgeLabelFor(entry.materialId) }}
          </span>
        </span>
      </div>

      <div
        class="hidden grid-cols-[34px_minmax(0,1fr)_repeat(5,minmax(44px,1fr))] gap-2 border-b border-hairline px-3 py-2 text-[11px] font-extrabold text-ink-muted sm:grid"
      >
        <span aria-hidden="true" class="text-center">#</span>
        <span aria-hidden="true">{{ $t('cutting.column.name') }}</span>
        <span aria-hidden="true" class="text-center">{{ $t('cutting.column.length') }}</span>
        <span aria-hidden="true" class="text-center">{{ $t('cutting.column.width') }}</span>
        <span aria-hidden="true" class="text-center">{{ $t('cutting.column.quantity') }}</span>
        <span aria-hidden="true" class="text-center">{{ $t('cutting.column.rotation') }}</span>
        <span aria-hidden="true" class="text-center">{{ $t('cutting.column.edge') }}</span>
      </div>

      <div
        v-for="row in group.parts"
        :key="row.part.part_ref"
        class="grid grid-cols-[34px_minmax(0,1fr)_repeat(5,minmax(44px,1fr))] items-center gap-2 border-b border-hairline px-3 py-2 text-sm last:border-b-0"
      >
        <span class="text-center text-xs text-ink-muted"> #{{ row.index + 1 }} </span>
        <span class="min-w-0 truncate text-ink">
          {{ partDisplayName(row.part, row.index) }}
        </span>
        <span class="text-center text-ink">{{ row.part.length_mm }}</span>
        <span class="text-center text-ink">{{ row.part.width_mm }}</span>
        <span class="text-center text-ink">{{ row.part.quantity }}</span>
        <span class="grid place-items-center">
          <!-- The signal marks the constraint, not the freedom: a part that may
               NOT rotate is what the cutter has to honour, so it carries the
               colour while a free part stays quiet. `signal` and not `accent`
               because the action colour is graphite now — against `ink-muted` an
               18px graphite glyph is no distinction at all. -->
          <Icon
            :name="row.part.follow_grain === false ? 'rotate' : 'grain'"
            class="size-[18px]"
            :class="row.part.follow_grain === false ? 'text-ink-muted' : 'text-signal'"
          />
        </span>
        <span class="grid place-items-center">
          <span
            class="size-8 rounded-md bg-sunk/30"
            :style="edgeGlyphStyle(row.part)"
            :title="edgeSidesLabel(row.part)"
            :aria-label="edgeSidesLabel(row.part)"
          ></span>
        </span>
      </div>
    </section>
  </div>
</template>
