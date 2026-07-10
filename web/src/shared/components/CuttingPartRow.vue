<script setup lang="ts">
import { computed } from 'vue'

import { MIN_PART_MM } from '@/shared/app/constants'
import {
  colorForMaterial,
  edgeShortLabel,
  edgeFields,
  sideLabels,
  type EdgeField,
} from '@/shared/app/cuttingDisplay'
import {
  partDisplayName,
  registryEntryForBand,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import Icon from '@/shared/components/AppIcon.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useCuttingStore, type CuttingPart } from '@/shared/stores/cutting'

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
  edgeRegistry: EdgeRegistryEntry[]
  selected?: boolean
}>()
const emit = defineEmits<{
  'update:name': [string | null]
  'update:length': [number]
  'update:width': [number]
  'update:quantity': [number]
  'update:material': [string | null]
  'update:follow-grain': [boolean]
  delete: []
  duplicate: []
  'cell-enter': [cell: 'name' | 'length' | 'width' | 'quantity' | 'edge']
  'open-edge-picker': [Event | undefined]
  'toggle-select': []
}>()

const cutting = useCuttingStore()
const edgeSideCells: Array<{ field: EdgeField; label: string }> = [
  { field: 'edge_top', label: 'U' },
  { field: 'edge_bottom', label: 'P' },
  { field: 'edge_left', label: 'CH' },
  { field: 'edge_right', label: "O'" },
]

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
const nameModel = computed({
  get: () => props.part.name ?? '',
  set: (value: string) => {
    const next = value.trim()
    emit('update:name', next || null)
  },
})

const grain = computed(() => materialById(props.part.material_id)?.grain_direction ?? false)
const followsGrain = computed(() => props.part.follow_grain !== false)
const grainTitle = computed(() =>
  !grain.value
    ? "Tekstura yo'nalishi bu materialda yo'q — sozlama saqlanadi, lekin natijaga ta'sir qilmaydi"
    : followsGrain.value
      ? "Tekstura yo'nalishi bo'yicha — burilmaydi"
      : 'Tekstura hisobga olinmaydi — burilishi mumkin',
)
const grainToggleClass = computed(() =>
  !grain.value
    ? 'border border-hairline-strong bg-elevated text-ink-muted'
    : followsGrain.value
      ? 'bg-info-soft text-info'
      : 'border border-hairline-strong bg-sunk text-ink-muted opacity-80',
)
const grainLabelClass = computed(() =>
  followsGrain.value ? (grain.value ? '' : 'opacity-70') : 'line-through opacity-70',
)

const swatchStyle = computed(() => {
  const material = materialById(props.part.material_id)
  return {
    background: colorForMaterial(material?.color ?? material?.name ?? props.part.material_id),
  }
})

const notCarriedNonPanel = computed(() => props.notCarried.some((issue) => issue !== 'panel'))

function edgeCellTitle() {
  const part = props.part
  const lines = edgeFields.map((side) => {
    const edge = part[side]
    const material = edgeById(edge?.material_id)
    return `${sideLabels[side]}: ${edge ? edgeShortLabel(material, true) : '-'}`
  })
  return `Krom yopishtirish - tahrirlash uchun bosing\n${lines.join(' · ')}`
}

function edgeRegistryEntry(side: EdgeField) {
  const band = props.part[side]
  return registryEntryForBand(props.edgeRegistry, band?.material_id, band?.source)
}
</script>

<template>
  <article
    :id="`part-row-${part.part_ref}`"
    class="rounded-md border p-2 transition hover:border-ink-soft"
    :class="
      hasError
        ? 'border-danger-soft bg-danger-soft/30'
        : selected
          ? 'border-accent-tint bg-accent-soft/40'
          : 'border-hairline bg-elevated'
    "
  >
    <div
      class="grid gap-3 lg:grid-cols-[30px_34px_minmax(150px,1.2fr)_82px_82px_66px_72px_140px_38px_38px] lg:items-start lg:gap-2"
    >
      <div class="hidden lg:flex lg:justify-center">
        <input
          type="checkbox"
          class="size-4"
          :checked="selected"
          :aria-label="`Qism #${index + 1} ni tanlash`"
          @change="emit('toggle-select')"
        />
      </div>
      <div class="font-mono text-xs font-extrabold text-ink-muted">#{{ index + 1 }}</div>

      <div class="min-w-0">
        <label class="grid gap-1 text-xs font-bold text-ink-muted">
          <span class="lg:hidden">Nomi</span>
          <input
            v-model="nameModel"
            :data-part-index="index"
            data-cell="name"
            class="mp-input lg:min-h-9 lg:px-2"
            :placeholder="partDisplayName(part, index)"
            aria-label="Nomi"
            @keydown.enter.prevent="emit('cell-enter', 'name')"
          />
        </label>
        <div class="mt-2 flex flex-wrap items-center gap-2 lg:hidden">
          <button
            v-if="grain"
            type="button"
            data-test="follow-grain-mobile"
            class="mp-chip"
            :class="grainToggleClass"
            :title="grainTitle"
            :aria-label="grainTitle"
            :aria-pressed="followsGrain"
            @click="emit('update:follow-grain', !followsGrain)"
          >
            <span aria-hidden="true">↕</span>
            <span :class="grainLabelClass">Tekstura</span>
          </button>
        </div>
      </div>

      <div class="hidden lg:flex lg:justify-center">
        <button
          v-if="grain"
          type="button"
          data-test="follow-grain-desktop"
          class="inline-flex h-9 w-full items-center justify-center gap-1 rounded-md px-2 text-xs font-bold"
          :class="grainToggleClass"
          :title="grainTitle"
          :aria-label="grainTitle"
          :aria-pressed="followsGrain"
          @click="emit('update:follow-grain', !followsGrain)"
        >
          <span aria-hidden="true">↕</span>
          <span :class="grainLabelClass">Tekstura</span>
        </button>
      </div>

      <!-- Sub-lg: the three dimensions share one row; lg:contents
           dissolves this wrapper so each input is a column of the
           parent grid again (desktop layout unchanged) — CB-60. -->
      <div class="grid grid-cols-3 gap-2 lg:contents">
        <label class="grid gap-1 text-xs font-bold text-ink-muted">
          <span class="lg:hidden">Bo'y</span>
          <input
            v-model.number="lengthModel"
            :data-part-index="index"
            data-cell="length"
            type="number"
            :min="MIN_PART_MM"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input font-mono lg:min-h-9 lg:px-2"
            :class="part.length_mm < MIN_PART_MM || sizeError ? 'border-danger' : ''"
            aria-label="Bo'y millimetr"
            @keydown.enter.prevent="emit('cell-enter', 'length')"
          />
        </label>

        <label class="grid gap-1 text-xs font-bold text-ink-muted">
          <span class="lg:hidden">Eni</span>
          <input
            v-model.number="widthModel"
            :data-part-index="index"
            data-cell="width"
            type="number"
            :min="MIN_PART_MM"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input font-mono lg:min-h-9 lg:px-2"
            :class="part.width_mm < MIN_PART_MM || sizeError ? 'border-danger' : ''"
            aria-label="Eni millimetr"
            @keydown.enter.prevent="emit('cell-enter', 'width')"
          />
        </label>

        <label class="grid gap-1 text-xs font-bold text-ink-muted">
          <span class="lg:hidden">Soni</span>
          <input
            v-model.number="quantityModel"
            :data-part-index="index"
            data-cell="quantity"
            type="number"
            min="1"
            inputmode="numeric"
            enterkeyhint="done"
            class="mp-input font-mono lg:min-h-9 lg:px-2"
            :class="part.quantity < 1 ? 'border-danger' : ''"
            aria-label="Soni"
            @keydown.enter.prevent="emit('cell-enter', 'quantity')"
          />
        </label>
      </div>

      <div class="min-w-0">
        <span class="mb-1 block text-sm font-bold text-ink lg:hidden">Krom</span>
        <div class="grid grid-cols-4 gap-1">
          <button
            v-for="cell in edgeSideCells"
            :key="cell.field"
            type="button"
            :data-part-index="index"
            data-cell="edge"
            class="grid h-9 place-items-center rounded-md border border-hairline-strong bg-elevated text-xs font-black hover:border-accent"
            :title="edgeCellTitle()"
            :aria-label="`${cell.label} kromini tahrirlash`"
            @click="emit('open-edge-picker', $event)"
            @keydown.enter.prevent="emit('cell-enter', 'edge')"
          >
            <span
              v-if="edgeRegistryEntry(cell.field)"
              class="grid size-5 place-items-center rounded-full"
              :class="edgeRegistryEntry(cell.field)?.colorClass"
            >
              {{ edgeRegistryEntry(cell.field)?.number }}
            </span>
            <span v-else class="text-ink-muted">·</span>
          </button>
        </div>
      </div>

      <button
        type="button"
        class="mp-action-icon-button justify-self-end"
        :aria-label="`Qism #${index + 1} ni nusxalash`"
        @click="emit('duplicate')"
      >
        ⧉
      </button>

      <details class="relative justify-self-end">
        <summary
          class="mp-action-icon-button list-none"
          :aria-label="`Qism #${index + 1} amallari`"
        >
          ⋯
        </summary>
        <div
          class="absolute right-0 z-30 mt-1 grid w-72 gap-3 rounded-md border border-hairline-strong bg-elevated p-3 shadow-[0_18px_40px_-24px_rgb(15_27_45_/_55%)]"
        >
          <SearchCombobox
            label="Materialni almashtirish"
            compact
            clearable
            :swatch-color="part.material_id ? swatchStyle.background : null"
            :model-value="part.material_id"
            :options="panelChoices"
            placeholder="Panel tanlang"
            :error="!part.material_id ? 'Material tanlang' : null"
            @update:model-value="emit('update:material', $event)"
          />
          <button
            type="button"
            class="mp-button mp-button-outline justify-start text-danger"
            :aria-label="`Qism #${index + 1} ni o'chirish`"
            @click="emit('delete')"
          >
            <Icon name="trash" class="size-[18px]" /> O'chirish
          </button>
        </div>
      </details>
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
        filialida mavjud bo'lmagan materialdan foydalanadi — boshqa material tanlang yoki filialni
        o'zgartiring.
      </span>
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
