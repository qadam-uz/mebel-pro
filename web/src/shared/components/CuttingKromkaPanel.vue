<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import Icon from '@/shared/components/AppIcon.vue'
import { colorForMaterial, edgeSearchText, sideLabels } from '@/shared/app/cuttingDisplay'
import { edgeTooNarrow, rankedEdges } from '@/shared/app/cuttingEdgeDisplay'
import { edgeRegistryKey, type EdgeRegistryEntry } from '@/shared/app/cuttingEditorDerived'
import { formatTiyin } from '@/shared/formatters'
import { metres } from '@/shared/stores/cutting'
import type {
  ClientCatalogMaterialOption,
  CuttingEdgeBand,
  CuttingPart,
} from '@/shared/stores/cutting'
import type { EdgeField } from '@/shared/app/cuttingDisplay'

// The order wizard's kromka editor, docked to the right of the parts board.
//
// It is the modal's twin, not its replacement: `CuttingEdgePickerModal` still
// serves the client editor, where the board is full-width and there is no rail
// to dock into. What changes here is only the frame — the operator keeps the row
// he is banding in view, and one detal costs one click instead of
// open → toggle → apply → close.
//
// Deliberately NOT carried over from the modal: the backdrop, the focus trap,
// the body scroll-lock, `role="dialog"`/`aria-modal`, and the Escape→close
// document listener. Every one of them is wrong for a surface that is simply
// part of the page — the scroll-lock in particular would freeze the very board
// this panel sits beside (`body.modal-open` pins the workshop frame's inner
// scroller, not just `body`).
const props = defineProps<{
  part: CuttingPart | null
  partNumber: number
  /** The board this detal is cut from — drives tape ranking and the figure's fill. */
  panelMaterial: ClientCatalogMaterialOption | null
  edgeOptions: ClientCatalogMaterialOption[]
  edgeRegistry: EdgeRegistryEntry[]
  /** How many detals share this detal's material, for the apply-to-group action. */
  groupSize: number
  /** The side the operator pointed at in the row, so its toggle can announce itself. */
  flashSide: EdgeField | null
}>()

const emit = defineEmits<{
  'edges-change': [
    { edges: Record<EdgeField, CuttingEdgeBand | null>; rememberedMaterialId: string | null },
  ]
  'apply-group': []
  close: []
}>()

const { t } = useI18n()

const tapeOpen = ref(false)
const search = ref('')

const EDGE_FIELDS: EdgeField[] = ['edge_top', 'edge_bottom', 'edge_left', 'edge_right']

const bands = computed<Record<EdgeField, CuttingEdgeBand | null>>(() => ({
  edge_top: props.part?.edge_top ?? null,
  edge_bottom: props.part?.edge_bottom ?? null,
  edge_left: props.part?.edge_left ?? null,
  edge_right: props.part?.edge_right ?? null,
}))

const bandedFields = computed(() => EDGE_FIELDS.filter((field) => bands.value[field] !== null))

/** The tape this panel is armed with: whatever is already banded, else the
 *  best-ranked candidate for the board. Arming is not an edit — nothing is
 *  emitted until a side is actually turned on. */
const activeTapeId = ref<string | null>(null)
const activeTape = computed(
  () => props.edgeOptions.find((edge) => edge.id === activeTapeId.value) ?? null,
)

const ranked = computed(() => rankedEdges(props.panelMaterial, props.edgeOptions))

function firstBandedTapeId(): string | null {
  for (const field of EDGE_FIELDS) {
    const band = bands.value[field]
    if (band?.material_id) return band.material_id
  }
  return null
}

// Re-seed on EVERY change of subject, not just null→part. The modal's watcher
// only fires on open and close, which is correct for a modal and silently wrong
// for a docked panel: walking from D1 to D2 would leave D1's armed tape in place
// and write it onto D2 with the first toggle.
watch(
  () => props.part?.part_ref ?? null,
  () => {
    tapeOpen.value = false
    search.value = ''
    activeTapeId.value = firstBandedTapeId() ?? ranked.value[0]?.material.id ?? null
  },
  { immediate: true },
)

// ── The detal figure ────────────────────────────────────────────────────────
// Drawn to the detal's real proportions so a 2000×300 plinth does not read like
// a door. `k` fits it inside 276×106 and the 58px floor keeps a very thin part
// from collapsing to a line the tape bands cannot be seen on.
const figure = computed(() => {
  const lengthMm = props.part?.length_mm ?? 0
  const widthMm = props.part?.width_mm ?? 0
  if (lengthMm <= 0 || widthMm <= 0) return { width: 210, height: 104 }
  const k = Math.min(276 / lengthMm, 106 / widthMm)
  return {
    width: Math.max(58, Math.round(lengthMm * k)),
    height: Math.max(58, Math.round(widthMm * k)),
  }
})

const figureFill = computed(() =>
  props.panelMaterial ? colorForMaterial(props.panelMaterial.nomi) : 'var(--color-sunk)',
)

const figureGrain = computed(() =>
  props.panelMaterial?.tolali
    ? 'repeating-linear-gradient(180deg, rgba(15,17,21,0.11) 0 1px, rgba(255,255,255,0) 1px 7px)'
    : 'none',
)

const tapeColor = computed(() => {
  const id = activeTapeId.value
  if (!id) return 'var(--color-hairline)'
  const entry = props.edgeRegistry.find((row) => row.key === edgeRegistryKey(id, 'shop'))
  if (entry) return entry.colorStyle.bg
  const option = props.edgeOptions.find((edge) => edge.id === id)
  return option ? colorForMaterial(option.nomi) : 'var(--color-hairline)'
})

function bandStyle(field: EdgeField) {
  const band = bands.value[field]
  if (!band) return undefined
  const entry = props.edgeRegistry.find(
    (row) => row.key === edgeRegistryKey(band.material_id, band.source),
  )
  return {
    background: entry ? entry.colorStyle.bg : tapeColor.value,
    // The inset ring is what keeps a white tape (`Kromka PVX Oq`) readable as a
    // band against a near-white dekor — without it the two disappear into
    // each other and the figure says "unbanded".
    boxShadow: 'inset 0 0 0 1px rgba(15,17,21,0.45)',
  }
}

// ── Writing ─────────────────────────────────────────────────────────────────
// One toggle, one write. `edges-change` carries the complete four-side record
// because that is the contract the editor already applies — a per-side delta
// would break `applyEdgesToRefs`.
function writeSides(next: Record<EdgeField, boolean>) {
  const tape = activeTapeId.value
  const edges = {} as Record<EdgeField, CuttingEdgeBand | null>
  for (const field of EDGE_FIELDS) {
    if (!next[field]) {
      edges[field] = null
      continue
    }
    const existing = bands.value[field]
    edges[field] = existing
      ? { ...existing }
      : tape
        ? { material_id: tape, source: 'shop' as const }
        : null
  }
  emit('edges-change', { edges, rememberedMaterialId: tape })
}

function currentSideMap(): Record<EdgeField, boolean> {
  return {
    edge_top: bands.value.edge_top !== null,
    edge_bottom: bands.value.edge_bottom !== null,
    edge_left: bands.value.edge_left !== null,
    edge_right: bands.value.edge_right !== null,
  }
}

function toggleTapeList() {
  tapeOpen.value = !tapeOpen.value
  search.value = ''
}

function toggleSide(field: EdgeField) {
  const next = currentSideMap()
  next[field] = !next[field]
  writeSides(next)
}

function applyPattern(on: boolean) {
  writeSides({ edge_top: on, edge_bottom: on, edge_left: on, edge_right: on })
}

function pickTape(id: string) {
  activeTapeId.value = id
  tapeOpen.value = false
  // Re-point the sides that are already banded; if none are, this is only an
  // arming step and must not write.
  if (bandedFields.value.length === 0) return
  const edges = {} as Record<EdgeField, CuttingEdgeBand | null>
  for (const field of EDGE_FIELDS) {
    edges[field] = bands.value[field] ? { material_id: id, source: 'shop' as const } : null
  }
  emit('edges-change', { edges, rememberedMaterialId: id })
}

// ── Side list, chips, footer ────────────────────────────────────────────────
const sides = computed(() =>
  EDGE_FIELDS.map((field) => ({
    field,
    label: sideLabels[field],
    on: bands.value[field] !== null,
    flash: props.flashSide === field,
  })),
)

const allOn = computed(() => bandedFields.value.length === 4)
const noneOn = computed(() => bandedFields.value.length === 0)

/** `(top + bottom) × length + (left + right) × width`, × quantity — the same
 *  arithmetic the server bills `edge_consumed_*` with. */
const consumedMm = computed(() => {
  const part = props.part
  if (!part) return 0
  const lengthSides = (part.edge_top ? 1 : 0) + (part.edge_bottom ? 1 : 0)
  const widthSides = (part.edge_left ? 1 : 0) + (part.edge_right ? 1 : 0)
  return (lengthSides * part.length_mm + widthSides * part.width_mm) * part.quantity
})

const footerMetres = computed(() =>
  consumedMm.value > 0
    ? t('cutting.edge.panelConsumed', { metres: metres(consumedMm.value) })
    : t('cutting.edge.patternNone'),
)

// What this detal's banding costs, at the armed tape's per-metre price. An
// em dash rather than 0 so an unbanded detal does not invite the reader to
// look for a figure that does not exist.
const footerCost = computed(() => {
  const tape = activeTape.value
  if (!tape || consumedMm.value <= 0 || tape.price_unset) return '—'
  return formatTiyin(Math.round((consumedMm.value / 1000) * tape.price_tiyin))
})

// ── The tape catalog ────────────────────────────────────────────────────────
const tapeRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  return ranked.value
    .filter((row) => (query ? edgeSearchText(row.material).includes(query) : true))
    .map((row) => {
      const entry = props.edgeRegistry.find(
        (registry) => registry.key === edgeRegistryKey(row.material.id, 'shop'),
      )
      return {
        material: row.material,
        color: entry ? entry.colorStyle.bg : colorForMaterial(row.material.nomi),
        number: entry?.number ?? null,
        tooNarrow: edgeTooNarrow(
          props.panelMaterial ? Number(props.panelMaterial.qalinlik_mm) : null,
          row.material,
        ),
        on: row.material.id === activeTapeId.value,
      }
    })
})

const activeTapeMeta = computed(() => {
  const tape = activeTape.value
  if (!tape) return ''
  return [tape.qalinlik_mm ? `${tape.qalinlik_mm} mm` : '', tape.kromka_eni_mm ?? '']
    .filter(Boolean)
    .join(' × ')
})

const subline = computed(() => {
  if (!props.part) return t('cutting.edge.panelNoSelection')
  const name = props.part.name?.trim()
  return name ? `D${props.partNumber} · ${name}` : `D${props.partNumber}`
})
</script>

<template>
  <aside
    role="region"
    :aria-label="$t('cutting.edge.panelTitle')"
    class="flex flex-col overflow-hidden rounded-2xl bg-elevated shadow-card"
  >
    <div class="flex items-start gap-2.5 border-b border-divider px-[18px] py-[15px]">
      <div class="min-w-0 flex-1">
        <h3 class="font-display text-[17px] font-bold tracking-[-0.02em] text-ink">
          {{ $t('cutting.edge.panelTitle') }}
        </h3>
        <p class="num mt-0.5 text-[12.5px] text-ink-soft">{{ subline }}</p>
      </div>
      <button
        v-if="part"
        type="button"
        class="grid size-[30px] flex-none place-items-center rounded-[9px] text-ink-nav transition hover:bg-neutral-soft"
        :title="$t('cutting.edge.panelClearHint')"
        :aria-label="$t('cutting.edge.panelClear')"
        @click="emit('close')"
      >
        <Icon name="x" class="size-[15px]" />
      </button>
    </div>

    <p v-if="!part" class="px-[18px] pb-[18px] pt-4 text-[13px] leading-relaxed text-ink-soft">
      {{ $t('cutting.edge.panelEmpty') }}
    </p>

    <template v-else>
      <div class="px-[18px] pt-4">
        <div class="grid h-[136px] place-items-center pl-3.5">
          <div
            class="relative"
            :style="{ width: `${figure.width}px`, height: `${figure.height}px` }"
          >
            <span
              aria-hidden="true"
              class="absolute inset-0 rounded-[2px]"
              :style="{
                background: figureFill,
                boxShadow:
                  'inset 0 0 0 1px rgba(15,17,21,0.32), 0 2px 6px -2px rgba(16,24,40,0.35)',
              }"
            ></span>
            <span
              aria-hidden="true"
              class="absolute inset-0 rounded-[2px]"
              :style="{ background: figureGrain }"
            ></span>
            <span
              v-if="bands.edge_top"
              aria-hidden="true"
              class="absolute inset-x-0 top-0 h-[7px]"
              :style="bandStyle('edge_top')"
            ></span>
            <span
              v-if="bands.edge_bottom"
              aria-hidden="true"
              class="absolute inset-x-0 bottom-0 h-[7px]"
              :style="bandStyle('edge_bottom')"
            ></span>
            <span
              v-if="bands.edge_left"
              aria-hidden="true"
              class="absolute inset-y-0 left-0 w-[7px]"
              :style="bandStyle('edge_left')"
            ></span>
            <span
              v-if="bands.edge_right"
              aria-hidden="true"
              class="absolute inset-y-0 right-0 w-[7px]"
              :style="bandStyle('edge_right')"
            ></span>
            <!-- Outside the figure, not on it: a label printed over the panel
                 would sit on top of the dekor colour the figure exists to show. -->
            <span
              aria-hidden="true"
              class="num absolute inset-x-0 top-[-17px] text-center text-[10.5px] text-ink-muted"
            >
              {{ part.length_mm || '—' }}
            </span>
            <span
              aria-hidden="true"
              class="num absolute inset-y-0 left-[-16px] grid place-items-center text-[10.5px] text-ink-muted [writing-mode:vertical-rl]"
              style="transform: rotate(180deg)"
            >
              {{ part.width_mm || '—' }}
            </span>
          </div>
        </div>

        <div class="mt-[11px] grid grid-cols-2 gap-[7px]">
          <button
            v-for="side in sides"
            :key="side.field"
            type="button"
            :aria-pressed="side.on"
            class="flex h-10 items-center rounded-[10px] border px-3 text-left text-[13px] font-semibold transition"
            :class="[
              side.on
                ? 'border-accent-edge bg-accent-soft text-accent-strong'
                : 'border-hairline-soft bg-sunk text-ink-nav hover:border-hairline-strong',
              side.flash ? 'ring-2 ring-accent-line' : '',
            ]"
            @click="toggleSide(side.field)"
          >
            {{ side.label }}
          </button>
        </div>

        <div class="mt-[9px] flex flex-wrap gap-1.5">
          <button
            type="button"
            class="h-8 rounded-[9px] px-[11px] text-[12.5px] font-semibold transition"
            :class="
              allOn
                ? 'bg-accent-soft text-accent-strong'
                : 'bg-neutral-soft text-ink hover:bg-hairline'
            "
            @click="applyPattern(true)"
          >
            {{ $t('cutting.edge.patternAll') }}
          </button>
          <button
            type="button"
            class="h-8 rounded-[9px] px-[11px] text-[12.5px] font-semibold transition"
            :class="
              noneOn
                ? 'bg-accent-soft text-accent-strong'
                : 'bg-neutral-soft text-ink hover:bg-hairline'
            "
            @click="applyPattern(false)"
          >
            {{ $t('cutting.edge.patternNone') }}
          </button>
        </div>
      </div>

      <div class="mt-4 border-t border-divider px-[18px] py-3.5">
        <p class="mb-[7px] text-[12.5px] font-semibold text-ink">
          {{ $t('cutting.edge.panelTapeLabel') }}
        </p>
        <button
          type="button"
          :aria-expanded="tapeOpen"
          class="flex h-12 w-full items-center gap-2.5 rounded-[11px] border border-hairline bg-elevated px-[11px] text-left transition hover:bg-sunk"
          @click="toggleTapeList"
        >
          <span
            class="size-[22px] flex-none rounded-[7px] border border-hairline-strong"
            :style="{ background: tapeColor }"
          ></span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-[13px] font-semibold text-ink">
              {{ activeTape ? activeTape.nomi : $t('cutting.edge.panelNoTape') }}
            </span>
            <span class="num block text-[11.5px] text-ink-muted">{{ activeTapeMeta }}</span>
          </span>
          <Icon
            name="chevron-down"
            class="size-[15px] flex-none text-ink-muted transition"
            :class="tapeOpen ? 'rotate-180' : ''"
          />
        </button>

        <div v-if="tapeOpen" class="mt-2">
          <label
            class="flex h-10 items-center gap-[9px] rounded-[10px] border border-hairline bg-elevated px-[11px] text-ink-muted focus-within:border-accent"
          >
            <Icon name="search" class="size-[15px] flex-none" />
            <input
              v-model="search"
              class="min-w-0 flex-1 border-0 bg-transparent text-[13px] text-ink outline-none"
              :placeholder="$t('cutting.edge.panelSearch')"
              :aria-label="$t('cutting.edge.panelSearch')"
            />
          </label>
          <div class="mt-1.5 flex max-h-[176px] flex-col gap-0.5 overflow-y-auto">
            <p
              v-if="tapeRows.length === 0"
              class="px-3 py-[18px] text-center text-[12.5px] text-ink-soft"
            >
              {{ $t('cutting.edge.panelNoHits') }}
            </p>
            <button
              v-for="row in tapeRows"
              :key="row.material.id"
              type="button"
              :aria-pressed="row.on"
              class="flex w-full items-center gap-[9px] rounded-[10px] px-[9px] py-2 text-left transition hover:bg-neutral-soft"
              :class="row.on ? 'bg-neutral-soft' : ''"
              @click="pickTape(row.material.id)"
            >
              <span
                class="size-5 flex-none rounded-md border border-hairline-strong"
                :style="{ background: row.color }"
              ></span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-[12.5px] font-semibold text-ink">
                  {{ row.material.nomi }}
                </span>
                <span class="num block text-[11.5px] text-ink-muted">
                  {{ row.material.qalinlik_mm }} mm × {{ row.material.kromka_eni_mm }}
                  <span v-if="row.tooNarrow" class="text-danger">
                    · {{ $t('cutting.edge.tooNarrow') }}
                  </span>
                </span>
              </span>
              <Icon v-if="row.on" name="check" class="size-3.5 flex-none text-ink" />
            </button>
          </div>
        </div>
      </div>

      <div v-if="groupSize > 0" class="border-t border-divider px-[18px] py-3">
        <button
          type="button"
          class="h-[38px] w-full rounded-[10px] border border-dashed border-hairline-strong text-[12.5px] font-semibold text-ink transition hover:border-accent"
          @click="emit('apply-group')"
        >
          {{ $t('cutting.edge.panelApplyGroup', { count: groupSize }) }}
        </button>
      </div>

      <div
        class="flex items-baseline justify-between gap-2.5 border-t border-divider bg-sunk px-[18px] py-[13px]"
      >
        <span class="num text-[12.5px] text-ink-soft">{{ footerMetres }}</span>
        <span class="num flex-none text-[13.5px] font-bold text-ink">{{ footerCost }}</span>
      </div>
    </template>
  </aside>
</template>
