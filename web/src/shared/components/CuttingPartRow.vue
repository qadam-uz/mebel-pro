<script setup lang="ts">
import { computed } from 'vue'

import { MIN_PART_MM } from '@/shared/app/constants'
import { edgeShortLabel, type EdgeField } from '@/shared/app/cuttingDisplay'
import {
  partDisplayName,
  registryEntryForBand,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import Icon from '@/shared/components/AppIcon.vue'
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
  'update:follow-grain': [boolean]
  delete: []
  duplicate: []
  'cell-enter': [cell: 'name' | 'length' | 'width' | 'quantity' | 'edge']
  'open-edge-picker': [Event | undefined, side?: EdgeField]
  'open-material-picker': []
  'toggle-select': []
}>()

const cutting = useCuttingStore()
const edgeSideCells: Array<{ field: EdgeField; label: string }> = [
  { field: 'edge_top', label: 'U' },
  { field: 'edge_bottom', label: 'P' },
  { field: 'edge_left', label: 'CH' },
  { field: 'edge_right', label: "O'" },
]

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

const followsGrain = computed(() => props.part.follow_grain !== false)
const grainTitle = computed(() =>
  followsGrain.value
    ? "Tekstura yo'nalishi bo'yicha — burilmaydi"
    : 'Tekstura hisobga olinmaydi — burilishi mumkin',
)

const notCarriedNonPanel = computed(() => props.notCarried.some((issue) => issue !== 'panel'))

function edgeRegistryEntry(side: EdgeField) {
  const band = props.part[side]
  return registryEntryForBand(props.edgeRegistry, band?.material_id, band?.source)
}

function edgeCellTitle(side: EdgeField, label: string) {
  const band = props.part[side]
  const material = edgeById(band?.material_id)
  return band ? `${label}: ${edgeShortLabel(material, true)}` : `${label}: kromsiz`
}

function updateFollowGrain(event: Event) {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) return
  emit('update:follow-grain', input.checked)
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
      class="grid gap-3 lg:grid-cols-[30px_34px_minmax(150px,1.2fr)_82px_82px_66px_38px_140px_38px_38px_38px] lg:items-start lg:gap-2"
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
          <input
            data-test="follow-grain-mobile"
            type="checkbox"
            class="size-4"
            :checked="followsGrain"
            :title="grainTitle"
            :aria-label="grainTitle"
            @change="updateFollowGrain"
          />
        </div>
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

      <div class="hidden lg:flex lg:justify-center">
        <input
          data-test="follow-grain-desktop"
          type="checkbox"
          class="mt-2 size-4"
          :checked="followsGrain"
          :title="grainTitle"
          :aria-label="grainTitle"
          @change="updateFollowGrain"
        />
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
            class="grid h-9 place-items-center rounded-md border border-hairline-strong bg-elevated text-xs font-black transition hover:border-accent"
            :title="edgeCellTitle(cell.field, cell.label)"
            :aria-label="`${cell.label} kromini tahrirlash`"
            @click="emit('open-edge-picker', $event, cell.field)"
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

      <button
        type="button"
        class="mp-action-icon-button justify-self-end"
        :aria-label="`Qism #${index + 1} materialini almashtirish`"
        title="Materialni almashtirish"
        @click="emit('open-material-picker')"
      >
        <Icon name="swap" class="size-[18px]" />
      </button>

      <button
        type="button"
        class="mp-action-icon-button justify-self-end text-danger"
        :aria-label="`Qism #${index + 1} ni o'chirish`"
        title="O'chirish"
        @click="emit('delete')"
      >
        <Icon name="trash" class="size-[18px]" />
      </button>
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
