<script setup lang="ts">
import { computed } from 'vue'

import { MIN_PART_MM } from '@/shared/app/constants'
import {
  colorForMaterial,
  edgeFields,
  edgeShortLabel,
  sideLabels,
  type EdgeField,
} from '@/shared/app/cuttingDisplay'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import {
  useCuttingStore,
  type CuttingEdgeBand,
  type CuttingPart,
  type MaterialSource,
} from '@/shared/stores/cutting'

// CB-93 seam: one parts-table row. Purely presentational — the editor stays the
// single owner of `parts`, validation (size/missing/not-carried/optimiser errors),
// and every mutation; this component renders the row and EMITS edits (granular, so
// it never mutates the `part` prop — vue/no-mutating-props). The pure swatch/edge
// display is derived from the catalog via the store + the shared cuttingDisplay
// helpers, identical to the pre-extraction parent logic.
const props = defineProps<{
  part: CuttingPart
  index: number
  panelChoices: ChoiceOption[]
  hasError: boolean
  sizeError: string | null
  materialMissing: boolean
  optimizeError: string | null
  notCarried: string[]
  preferredBranchName: string
}>()
const emit = defineEmits<{
  'update:length': [number]
  'update:width': [number]
  'update:quantity': [number]
  'update:material': [string | null]
  'update:source': [MaterialSource]
  duplicate: []
  delete: []
  'open-edge-picker': [Event | undefined]
  'bring-own': []
}>()

const cutting = useCuttingStore()

function materialById(id: string | null | undefined) {
  return cutting.panelOptions.find((material) => material.id === id) ?? null
}
function edgeById(id: string | null | undefined) {
  return cutting.edgeOptions.find((material) => material.id === id) ?? null
}

// Writable computeds keep the original `v-model.number` semantics while emitting
// (a number input bound straight to the prop would mutate it).
const lengthModel = computed({
  get: () => props.part.length_mm,
  set: (value: number) => emit('update:length', value),
})
const widthModel = computed({
  get: () => props.part.width_mm,
  set: (value: number) => emit('update:width', value),
})
const quantityModel = computed({
  get: () => props.part.quantity,
  set: (value: number) => emit('update:quantity', value),
})

const grain = computed(() => materialById(props.part.material_id)?.grain_direction ?? false)

const swatchStyle = computed(() => {
  const material = materialById(props.part.material_id)
  return {
    background: colorForMaterial(material?.color ?? material?.name ?? props.part.material_id),
  }
})

const notCarriedNonPanel = computed(() => props.notCarried.some((issue) => issue !== 'panel'))

function edgeCount() {
  return edgeFields.filter((side) => props.part[side]).length
}

function edgeSummary() {
  const part = props.part
  const count = edgeCount()
  if (count === 0) return "Krom yo'q"
  const sides = count === 4 ? '4 tomon' : `${count} tomon`
  // Name the tape in the visible cell, not just the hover title / 6.5px SVG text
  // (CB-91/CB-69): one label when every banded side shares a material, else
  // "Aralash" so a mixed row is obvious without opening the picker.
  const materialIds = [
    ...new Set(edgeFields.filter((side) => part[side]).map((side) => part[side]?.material_id)),
  ]
  if (materialIds.length === 1) {
    const material = edgeById(materialIds[0])
    if (material) return `${edgeShortLabel(material, true)} · ${sides}`
  } else if (materialIds.length > 1) {
    return `Aralash · ${sides}`
  }
  return sides
}

function edgeSourceSummary() {
  const part = props.part
  const active = edgeFields.filter((side) => part[side])
  if (active.length === 0) return 'tomonlar tanlanmagan'
  const own = active.filter((side) => part[side]?.source === 'own').length
  if (own === active.length) return "o'zim olib kelaman"
  if (own > 0) return 'aralash manba'
  return 'ustaxonadan'
}

function edgeCellTitle() {
  const part = props.part
  const lines = edgeFields.map((side) => {
    const edge = part[side]
    const material = edgeById(edge?.material_id)
    const source = edge?.source === 'own' ? " (o'zim)" : ''
    return `${sideLabels[side]}: ${edge ? `${edgeShortLabel(material, true)}${source}` : '-'}`
  })
  return `Krom yopishtirish - tahrirlash uchun bosing\n${lines.join(' · ')}`
}

function edgeStrokeWidth(edge: CuttingEdgeBand | null) {
  const material = edgeById(edge?.material_id)
  const thickness = Number(material?.thickness_mm ?? 0.4)
  return thickness >= 2 ? 3 : 1.3
}

function edgeCellLabel(side: EdgeField) {
  const material = edgeById(props.part[side]?.material_id)
  return material?.thickness_mm ?? ''
}
</script>

<template>
  <article
    :id="`part-row-${part.part_ref}`"
    class="rounded-lg border p-3 transition hover:border-ink-soft"
    :class="hasError ? 'border-danger-soft bg-danger-soft/30' : 'border-hairline bg-elevated'"
  >
    <div
      class="grid gap-3 lg:grid-cols-[34px_minmax(240px,1.6fr)_90px_90px_76px_minmax(280px,1fr)_96px] lg:items-start"
    >
      <div class="font-mono text-xs font-extrabold text-ink-muted">#{{ index + 1 }}</div>

      <div class="min-w-0">
        <SearchCombobox
          label="Panel materiali"
          label-class="lg:sr-only"
          :model-value="part.material_id"
          :options="panelChoices"
          placeholder="Panel tanlang"
          :error="!part.material_id ? 'Material tanlang' : null"
          @update:model-value="emit('update:material', $event)"
        />
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <span class="size-5 rounded border border-hairline" :style="swatchStyle"></span>
          <span
            v-if="grain"
            class="mp-chip bg-info-soft text-info"
            title="Tola yo'nalishi bor — bu qism burilmaydi"
            aria-label="Tola yo'nalishi bor — bu qism burilmaydi"
          >
            <span aria-hidden="true">↕</span> Tola
          </span>
          <button
            type="button"
            class="mp-chip"
            :class="part.material_source === 'shop' ? 'bg-accent-soft text-accent' : ''"
            @click="emit('update:source', 'shop')"
          >
            Ustaxona
          </button>
          <button
            type="button"
            class="mp-chip"
            :class="part.material_source === 'own' ? 'bg-accent-soft text-accent' : ''"
            @click="emit('update:source', 'own')"
          >
            O'zim olib kelaman
          </button>
        </div>
      </div>

      <!-- Sub-lg: the three dimensions share one row; lg:contents
           dissolves this wrapper so each input is a column of the
           parent grid again (desktop layout unchanged) — CB-60. -->
      <div class="grid grid-cols-3 gap-2 lg:contents">
        <label class="grid gap-1 text-xs font-bold text-ink-muted">
          <span class="lg:hidden">Uzunlik</span>
          <input
            v-model.number="lengthModel"
            type="number"
            :min="MIN_PART_MM"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input font-mono"
            :class="part.length_mm < MIN_PART_MM || sizeError ? 'border-danger' : ''"
            aria-label="Uzunlik millimetr"
          />
        </label>

        <label class="grid gap-1 text-xs font-bold text-ink-muted">
          <span class="lg:hidden">Eni</span>
          <input
            v-model.number="widthModel"
            type="number"
            :min="MIN_PART_MM"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input font-mono"
            :class="part.width_mm < MIN_PART_MM || sizeError ? 'border-danger' : ''"
            aria-label="Eni millimetr"
          />
        </label>

        <label class="grid gap-1 text-xs font-bold text-ink-muted">
          <span class="lg:hidden">Soni</span>
          <input
            v-model.number="quantityModel"
            type="number"
            min="1"
            inputmode="numeric"
            enterkeyhint="done"
            class="mp-input font-mono"
            :class="part.quantity < 1 ? 'border-danger' : ''"
            aria-label="Soni"
          />
        </label>
      </div>

      <div class="min-w-0">
        <span class="mb-1 block text-sm font-bold text-ink lg:hidden">Krom</span>
        <button
          type="button"
          class="client-edges-btn"
          :title="edgeCellTitle()"
          :aria-label="`Qism #${index + 1} kromini tahrirlash`"
          @click="emit('open-edge-picker', $event)"
        >
          <svg viewBox="0 0 76 48" class="client-edge-svg" aria-hidden="true">
            <rect class="frame" x="14" y="13" width="48" height="22" />
            <line
              v-if="part.edge_top"
              class="side"
              x1="14"
              y1="13"
              x2="62"
              y2="13"
              :stroke-width="edgeStrokeWidth(part.edge_top)"
              :class="{ own: part.edge_top.source === 'own' }"
            />
            <line
              v-if="part.edge_bottom"
              class="side"
              x1="14"
              y1="35"
              x2="62"
              y2="35"
              :stroke-width="edgeStrokeWidth(part.edge_bottom)"
              :class="{ own: part.edge_bottom.source === 'own' }"
            />
            <line
              v-if="part.edge_left"
              class="side"
              x1="14"
              y1="13"
              x2="14"
              y2="35"
              :stroke-width="edgeStrokeWidth(part.edge_left)"
              :class="{ own: part.edge_left.source === 'own' }"
            />
            <line
              v-if="part.edge_right"
              class="side"
              x1="62"
              y1="13"
              x2="62"
              y2="35"
              :stroke-width="edgeStrokeWidth(part.edge_right)"
              :class="{ own: part.edge_right.source === 'own' }"
            />
            <text v-if="part.edge_top" class="lbl" x="38" y="7" text-anchor="middle">
              {{ edgeCellLabel('edge_top') }}
            </text>
            <text v-if="part.edge_bottom" class="lbl" x="38" y="45" text-anchor="middle">
              {{ edgeCellLabel('edge_bottom') }}
            </text>
            <text v-if="part.edge_left" class="lbl" x="6" y="24" text-anchor="middle">
              {{ edgeCellLabel('edge_left') }}
            </text>
            <text v-if="part.edge_right" class="lbl" x="70" y="24" text-anchor="middle">
              {{ edgeCellLabel('edge_right') }}
            </text>
          </svg>
          <span class="client-edge-summary">
            <b>{{ edgeSummary() }}</b>
            <small>{{ edgeSourceSummary() }}</small>
          </span>
        </button>
      </div>

      <div class="grid grid-cols-2 gap-2 lg:grid-cols-1">
        <button type="button" class="mp-button mp-button-outline" @click="emit('duplicate')">
          Nusxa
        </button>
        <button
          type="button"
          class="mp-button mp-button-outline text-danger"
          @click="emit('delete')"
        >
          O'chirish
        </button>
      </div>
    </div>

    <p
      v-if="sizeError"
      class="mt-3 flex items-center gap-2 rounded-md border border-danger-soft bg-danger-soft p-3 text-sm font-bold text-danger"
    >
      <span aria-hidden="true">!</span>
      <span>{{ sizeError }}</span>
    </p>

    <p
      v-if="materialMissing"
      class="mt-3 flex items-center gap-2 rounded-md border border-danger-soft bg-danger-soft p-3 text-sm font-bold text-danger"
    >
      <span aria-hidden="true">!</span>
      <span>Bu qatordagi panel materiali endi katalogda yo'q — boshqasini tanlang.</span>
    </p>

    <p
      v-if="optimizeError"
      class="mt-3 flex items-center gap-2 rounded-md border border-danger-soft bg-danger-soft p-3 text-sm font-bold text-danger"
    >
      <span aria-hidden="true">!</span>
      <span>{{ optimizeError }}</span>
    </p>

    <div
      v-if="notCarried.length"
      class="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-warning-soft bg-warning-soft p-3 text-sm text-warning"
    >
      <span class="font-black">!</span>
      <span class="min-w-0 flex-1">
        Bu qator
        <b>{{ preferredBranchName }}</b>
        filialida mavjud bo'lmagan materialdan foydalanadi.
      </span>
      <button type="button" class="mp-button mp-button-outline" @click="emit('bring-own')">
        O'zim olib kelaman
      </button>
      <button
        v-if="notCarriedNonPanel"
        type="button"
        class="mp-button mp-button-outline"
        @click="emit('open-edge-picker', undefined)"
      >
        Boshqa krom tanlash
      </button>
    </div>
  </article>
</template>
