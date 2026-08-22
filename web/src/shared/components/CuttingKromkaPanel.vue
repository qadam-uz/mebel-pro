<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import Icon from '@/shared/components/AppIcon.vue'
import { colorForMaterial, edgeSearchText, sideLabels } from '@/shared/app/cuttingDisplay'
import { edgeTooNarrow, rankedEdges } from '@/shared/app/cuttingEdgeDisplay'
import { edgeRegistryKey, type EdgeRegistryEntry } from '@/shared/app/cuttingEditorDerived'
import type {
  ClientCatalogMaterialOption,
  CuttingEdgeBand,
  CuttingPart,
} from '@/shared/stores/cutting'
import type { EdgeField } from '@/shared/app/cuttingDisplay'

// The order wizard's kromka editor, docked beside the parts board.
//
// It is the modal's twin, not its replacement: `CuttingEdgePickerModal` still
// serves the client editor, where the board is full-width and there is no room
// beside it. What changes here is only the frame — the operator keeps the row he
// is banding in view, and one detal costs one click instead of open → toggle →
// close.
//
// Deliberately NOT carried over from the modal: the backdrop, the focus trap,
// the body scroll-lock, `role="dialog"`/`aria-modal`, and the Escape→close
// document listener. Every one of them is wrong for a surface that is simply
// part of the page — the scroll-lock in particular would freeze the very board
// this panel sits beside (`body.modal-open` pins the workshop frame's inner
// scroller, not just `body`).
//
// The panel appears only while a row is selected. It has no empty state and no
// placeholder: with nothing selected there is nothing to say, and a 300px column
// of explanatory text beside the board is width spent on a sentence the operator
// reads once.
const props = defineProps<{
  part: CuttingPart
  partNumber: number
  /** The board this detal is cut from — drives the tape ranking. */
  panelMaterial: ClientCatalogMaterialOption | null
  edgeOptions: ClientCatalogMaterialOption[]
  edgeRegistry: EdgeRegistryEntry[]
  /** The side the operator pointed at in the row, so its toggle can announce itself. */
  flashSide: EdgeField | null
}>()

const emit = defineEmits<{
  'edges-change': [
    { edges: Record<EdgeField, CuttingEdgeBand | null>; rememberedMaterialId: string | null },
  ]
  close: []
}>()

const tapeOpen = ref(false)
const search = ref('')

const EDGE_FIELDS: EdgeField[] = ['edge_top', 'edge_bottom', 'edge_left', 'edge_right']

const bands = computed<Record<EdgeField, CuttingEdgeBand | null>>(() => ({
  edge_top: props.part.edge_top,
  edge_bottom: props.part.edge_bottom,
  edge_left: props.part.edge_left,
  edge_right: props.part.edge_right,
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
  () => props.part.part_ref,
  () => {
    tapeOpen.value = false
    search.value = ''
    activeTapeId.value = firstBandedTapeId() ?? ranked.value[0]?.material.id ?? null
  },
  { immediate: true },
)

const tapeColor = computed(() => {
  const id = activeTapeId.value
  if (!id) return 'var(--color-hairline)'
  const entry = props.edgeRegistry.find((row) => row.key === edgeRegistryKey(id, 'shop'))
  if (entry) return entry.colorStyle.bg
  const option = props.edgeOptions.find((edge) => edge.id === id)
  return option ? colorForMaterial(option.name) : 'var(--color-hairline)'
})

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

// ── Side buttons ────────────────────────────────────────────────────────────
// Each button carries a small rectangle with ITS OWN side drawn heavy — the
// glyph says which edge the button means, not whether it is banded. The banded
// state is the button's own fill, which is the larger signal and the one the
// operator is scanning for.
const HEAVY = '3px solid var(--color-ink-nav)'
const LIGHT = '1.5px solid var(--color-hairline)'

const sides = computed(() =>
  EDGE_FIELDS.map((field) => ({
    field,
    label: sideLabels[field],
    on: bands.value[field] !== null,
    flash: props.flashSide === field,
    glyph: {
      borderTop: field === 'edge_top' ? HEAVY : LIGHT,
      borderBottom: field === 'edge_bottom' ? HEAVY : LIGHT,
      borderLeft: field === 'edge_left' ? HEAVY : LIGHT,
      borderRight: field === 'edge_right' ? HEAVY : LIGHT,
    },
  })),
)

const allOn = computed(() => bandedFields.value.length === 4)
const noneOn = computed(() => bandedFields.value.length === 0)

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
        color: entry ? entry.colorStyle.bg : colorForMaterial(row.material.name),
        tooNarrow: edgeTooNarrow(
          props.panelMaterial ? Number(props.panelMaterial.thickness_mm) : null,
          row.material,
        ),
        on: row.material.id === activeTapeId.value,
      }
    })
})

const activeTapeMeta = computed(() => {
  const tape = activeTape.value
  if (!tape) return ''
  return [tape.thickness_mm ? `${tape.thickness_mm} mm` : '', tape.tape_width_mm ?? '']
    .filter(Boolean)
    .join(' × ')
})

/** `D3 · Yon panel · 1800×450` — number, name, size. The size is here because
 *  the panel dropped its diagram: without it nothing else on this surface says
 *  which detal's edges these are. */
const subline = computed(() => {
  const name = props.part.name?.trim()
  const size = `${props.part.length_mm || '—'}×${props.part.width_mm || '—'}`
  return [`D${props.partNumber}`, name, size].filter(Boolean).join(' · ')
})
</script>

<template>
  <aside
    role="region"
    :aria-label="$t('cutting.edge.panelTitle')"
    class="flex w-[300px] flex-none flex-col overflow-hidden rounded-2xl bg-elevated shadow-card"
  >
    <div class="flex items-start gap-2.5 border-b border-divider px-[15px] py-3.5">
      <div class="min-w-0 flex-1">
        <h3 class="font-display text-[17px] font-bold tracking-[-0.02em] text-ink">
          {{ $t('cutting.edge.panelTitle') }}
        </h3>
        <p class="num mt-0.5 text-[12.5px] text-ink-soft">{{ subline }}</p>
      </div>
      <button
        type="button"
        class="grid size-[30px] flex-none place-items-center rounded-[9px] text-ink-nav transition hover:bg-neutral-soft"
        :title="$t('cutting.edge.panelClearHint')"
        :aria-label="$t('cutting.edge.panelClear')"
        @click="emit('close')"
      >
        <Icon name="x" class="size-[15px]" />
      </button>
    </div>

    <div class="px-[15px] pt-[15px]">
      <div class="flex gap-[7px]">
        <div class="grid min-w-0 flex-1 grid-cols-2 gap-[7px]">
          <button
            v-for="side in sides"
            :key="side.field"
            type="button"
            :aria-pressed="side.on"
            class="flex h-11 items-center gap-[9px] rounded-[10px] border px-2.5 text-left transition"
            :class="[
              side.on
                ? 'border-select-chip-line bg-select-chip text-ink'
                : 'border-hairline-soft bg-sunk text-ink-nav hover:border-hairline-strong',
              side.flash ? 'ring-2 ring-select-chip-line' : '',
            ]"
            @click="toggleSide(side.field)"
          >
            <span
              aria-hidden="true"
              class="h-3.5 w-[19px] flex-none rounded-[2px] bg-elevated"
              :style="side.glyph"
            ></span>
            <span class="min-w-0 flex-1 text-[13px] font-semibold">{{ side.label }}</span>
          </button>
        </div>
        <span aria-hidden="true" class="w-px flex-none self-stretch bg-divider"></span>
        <!-- The two whole-part patterns, as glyphs rather than words: they say the
             same thing the four buttons beside them say, so a second column of
             labels would read as four more sides. -->
        <div class="grid w-[42px] flex-none gap-[7px]">
          <button
            type="button"
            :aria-pressed="allOn"
            class="grid h-11 place-items-center rounded-[10px] transition"
            :class="
              allOn ? 'bg-select-chip text-ink' : 'bg-sunk text-ink-nav hover:bg-neutral-soft'
            "
            :title="$t('cutting.edge.patternAll')"
            :aria-label="$t('cutting.edge.patternAll')"
            @click="applyPattern(true)"
          >
            <span
              aria-hidden="true"
              class="h-3.5 w-[19px] rounded-[2px] border-[3px] border-current"
            ></span>
          </button>
          <button
            type="button"
            :aria-pressed="noneOn"
            class="grid h-11 place-items-center rounded-[10px] transition"
            :class="
              noneOn ? 'bg-select-chip text-ink' : 'bg-sunk text-ink-nav hover:bg-neutral-soft'
            "
            :title="$t('cutting.edge.patternNone')"
            :aria-label="$t('cutting.edge.patternNone')"
            @click="applyPattern(false)"
          >
            <span
              aria-hidden="true"
              class="h-3.5 w-[19px] rounded-[2px] border-[1.5px] border-dashed border-current"
            ></span>
          </button>
        </div>
      </div>
    </div>

    <div class="mt-[15px] border-t border-divider px-[15px] py-[13px]">
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
            {{ activeTape ? activeTape.name : $t('cutting.edge.panelNoTape') }}
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
                {{ row.material.name }}
              </span>
              <span class="num block text-[11.5px] text-ink-muted">
                {{ row.material.thickness_mm }} mm × {{ row.material.tape_width_mm }}
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
  </aside>
</template>
