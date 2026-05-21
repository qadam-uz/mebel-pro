<script setup lang="ts">
// Interactive SVG of one sheet's CuttingPlacement rectangles. Material tabs +
// sheet tabs + an SVG rendering placements (bottom-left origin → flipped for
// SVG) + a hover-linked legend. Mirrors the prototype's visualiser.
import { computed, ref } from 'vue'
import { t } from '@/shared/i18n'
import type { CuttingResult, Material } from '../api/types'
import { LIMITS, buildSvgLayout, materialById, materialShortLabel, partColor } from '../lib/cutting'

const props = defineProps<{
  result: CuttingResult
  materials: Material[]
}>()

const activeMaterialId = ref<string>('')
const activeSheetIndex = ref(1)
const hovered = ref<string | null>(null)

// Materials present in this result's sheets.
const materialIds = computed(() => [...new Set(props.result.sheets.map((s) => s.material_id))])

const currentMaterialId = computed(() => {
  if (activeMaterialId.value && materialIds.value.includes(activeMaterialId.value)) {
    return activeMaterialId.value
  }
  return materialIds.value[0] ?? ''
})

const sheetsForMaterial = computed(() =>
  props.result.sheets
    .filter((s) => s.material_id === currentMaterialId.value)
    .sort((a, b) => a.sheet_index - b.sheet_index),
)

const currentSheet = computed(
  () =>
    sheetsForMaterial.value.find((s) => s.sheet_index === activeSheetIndex.value) ??
    sheetsForMaterial.value[0],
)

const material = computed(() => materialById(props.materials, currentMaterialId.value))

const layout = computed(() => {
  const sheet = currentSheet.value
  const m = material.value
  if (!sheet || !m || !m.sheet_length_mm || !m.sheet_width_mm) return null
  return buildSvgLayout(
    sheet.placements,
    m.sheet_length_mm,
    m.sheet_width_mm,
    props.result.edge_trim_mm || LIMITS.EDGE_TRIM,
  )
})

// Legend: one entry per distinct part_ref on the active sheet.
const legend = computed(() => {
  const sheet = currentSheet.value
  if (!sheet) return []
  const seen = new Map<
    string,
    { color: string; lengthMm: number; widthMm: number; count: number }
  >()
  let i = 0
  for (const p of sheet.placements) {
    if (!seen.has(p.part_ref)) {
      seen.set(p.part_ref, {
        color: partColor(i),
        lengthMm: p.length_mm,
        widthMm: p.width_mm,
        count: 0,
      })
      i++
    }
    const entry = seen.get(p.part_ref)!
    entry.count++
  }
  return [...seen.entries()].map(([ref, v], idx) => ({ ref, n: idx + 1, ...v }))
})

function colorFor(partRef: string): string {
  const idx = legend.value.findIndex((l) => l.ref === partRef)
  return idx >= 0 ? partColor(idx) : partColor(0)
}

function labelFor(partRef: string): number {
  return legend.value.findIndex((l) => l.ref === partRef) + 1
}

function selectMaterial(id: string) {
  activeMaterialId.value = id
  activeSheetIndex.value = 1
}

function sheetCount(materialId: string): number {
  return Number(props.result.sheets_used_by_material[materialId] ?? 0)
}
</script>

<template>
  <div class="viz">
    <div class="viz-tabs">
      <button
        v-for="id in materialIds"
        :key="id"
        type="button"
        :class="{ on: id === currentMaterialId }"
        @click="selectMaterial(id)"
      >
        {{ materialShortLabel(materialById(materials, id)) || id.slice(0, 6) }}
        <span class="ct">{{ t('client.sheetNCt', { n: sheetCount(id) }) }}</span>
      </button>
    </div>

    <div class="sheet-tabs">
      <button
        v-for="s in sheetsForMaterial"
        :key="s.id"
        type="button"
        :class="{ on: s.sheet_index === (currentSheet?.sheet_index ?? 1) }"
        @click="activeSheetIndex = s.sheet_index"
      >
        {{ t('client.sheetN', { n: s.sheet_index }) }}
      </button>
    </div>

    <div class="sheet-svg-wrap">
      <div>
        <svg
          v-if="layout"
          :viewBox="`0 0 ${layout.viewW} ${layout.viewH}`"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          :aria-label="`${materialShortLabel(material)} ${t('client.sheetN', { n: currentSheet?.sheet_index ?? 1 })}`"
        >
          <rect
            :x="0"
            :y="0"
            :width="layout.viewW"
            :height="layout.viewH"
            fill="#fff8ee"
            stroke="#caa97a"
            stroke-width="2"
          />
          <rect
            :x="layout.usable.x"
            :y="layout.usable.y"
            :width="layout.usable.w"
            :height="layout.usable.h"
            fill="none"
            stroke="#caa97a"
            stroke-width="1"
            stroke-dasharray="4 4"
          />
          <g
            v-for="(r, i) in layout.rects"
            :key="`${r.partRef}-${r.qtyIndex}-${i}`"
            @mouseenter="hovered = r.partRef"
            @mouseleave="hovered = null"
          >
            <rect
              :x="r.x"
              :y="r.y"
              :width="r.w"
              :height="r.h"
              :fill="colorFor(r.partRef)"
              :fill-opacity="hovered === r.partRef ? 0.95 : 0.78"
              stroke="#221d18"
              :stroke-width="hovered === r.partRef ? 1.6 : 0.8"
            />
            <text
              v-if="r.w > 80 && r.h > 30"
              :x="r.x + r.w / 2"
              :y="r.y + r.h / 2"
              fill="#fff"
              font-family="JetBrains Mono"
              font-size="11"
              text-anchor="middle"
              dominant-baseline="middle"
            >
              #{{ labelFor(r.partRef) }}·{{ r.lengthMm }}×{{ r.widthMm }}{{ r.rotated ? ' ↻' : '' }}
            </text>
          </g>
        </svg>
      </div>

      <div class="sheet-legend">
        <h4>
          {{
            t('client.legendSheet', {
              mat: materialShortLabel(material),
              n: currentSheet?.sheet_index ?? 1,
            })
          }}
        </h4>
        <ul>
          <li
            v-for="item in legend"
            :key="item.ref"
            :class="{ hl: hovered === item.ref }"
            @mouseenter="hovered = item.ref"
            @mouseleave="hovered = null"
          >
            <span class="sw" :style="{ background: item.color }" />
            {{
              t('client.legendItem', {
                n: item.n,
                l: item.lengthMm,
                w: item.widthMm,
                qty: item.count,
              })
            }}
          </li>
        </ul>
      </div>
    </div>

    <div v-if="material" class="sheet-info">
      <span
        >{{ t('client.sheetSize') }}:
        <b>{{ material.sheet_length_mm }} × {{ material.sheet_width_mm }} mm</b></span
      >
      <span :title="t('client.kerfTitle')"
        >{{ t('client.kerf') }}: <b>{{ result.kerf_mm }} mm</b></span
      >
      <span :title="t('client.edgeTrimTitle')"
        >{{ t('client.edgeTrim') }}: <b>{{ result.edge_trim_mm }} mm</b></span
      >
    </div>
  </div>
</template>

<style scoped>
.viz {
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
}
.viz-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.viz-tabs button {
  padding: 6px 12px;
  background: var(--sunk);
  border: 1px solid var(--line);
  border-radius: 6px;
  font: 500 12px var(--f-ui);
  color: var(--ink-8);
  cursor: pointer;
  white-space: nowrap;
}
.viz-tabs button.on {
  background: var(--ink-12);
  color: #fff;
  border-color: var(--ink-12);
}
.viz-tabs button .ct {
  margin-left: 6px;
  padding: 1px 6px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 999px;
  font-size: 10px;
}
.viz-tabs button.on .ct {
  background: rgba(255, 255, 255, 0.2);
}
.sheet-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.sheet-tabs button {
  padding: 4px 10px;
  background: var(--sunk);
  border: 1px solid var(--line);
  border-radius: 4px;
  font: 500 11.5px var(--f-mono);
  color: var(--ink-8);
  cursor: pointer;
}
.sheet-tabs button.on {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.sheet-svg-wrap {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr;
}
@media (min-width: 900px) {
  .sheet-svg-wrap {
    grid-template-columns: minmax(0, 1fr) 220px;
  }
}
.sheet-svg-wrap svg {
  width: 100%;
  max-height: 460px;
  background: var(--sunk);
  border-radius: 6px;
  border: 1px solid var(--line);
}
.sheet-legend h4 {
  font: 600 11px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-6);
  margin: 0 0 10px;
}
.sheet-legend ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 6px;
}
.sheet-legend li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: var(--sunk);
  border-radius: 4px;
  font: 500 11.5px var(--f-mono);
  color: var(--ink-10);
  cursor: default;
}
.sheet-legend li.hl {
  background: var(--accent-soft);
  border: 1px solid var(--accent-tint);
}
.sheet-legend li .sw {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  flex-shrink: 0;
}
.sheet-info {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font: 500 11.5px var(--f-mono);
  color: var(--ink-6);
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}
.sheet-info b {
  color: var(--ink-12);
  font-weight: 600;
}
</style>
