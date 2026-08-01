<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { MIN_PART_MM } from '@/shared/app/constants'
import { type EdgeField } from '@/shared/app/cuttingDisplay'
import {
  partDisplayName,
  registryEntryForBand,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import Icon from '@/shared/components/AppIcon.vue'
import { type CuttingPart } from '@/shared/stores/cutting'

// CB-93 seam: one parts-table row. Purely presentational — the editor stays the
// single owner of `parts`, validation (size/missing/not-carried/optimiser errors),
// and every mutation; this component renders the row and EMITS edits (granular, so
// it never mutates the `part` prop — vue/no-mutating-props). The pure swatch/edge
// display is derived from the catalog via the store + the shared cuttingDisplay
// helpers, identical to the pre-extraction parent logic.
const props = defineProps<{
  part: CuttingPart
  index: number
  displayIndex?: number
  hasError: boolean
  sizeError: string | null
  materialMissing: boolean
  optimizeError: string | null
  notCarried: string[]
  preferredBranchName: string
  edgeRegistry: EdgeRegistryEntry[]
}>()
const emit = defineEmits<{
  'update:name': [string | null]
  'update:length': [number]
  'update:width': [number]
  'update:quantity': [number]
  'update:follow-grain': [boolean]
  delete: []
  duplicate: []
  'cell-enter': [cell: 'name' | 'length' | 'width' | 'quantity' | 'edge', side?: EdgeField]
  'open-edge-picker': [Event | undefined, side?: EdgeField]
  'apply-edge-number': [side: EdgeField, number: number]
  'open-material-picker': []
  'toggle-select': []
}>()

const { t } = useI18n()

const actionsOpen = ref(false)
// Writable computeds keep the original `v-model.number` semantics while emitting
// (a number input bound straight to the prop would mutate it).
// A fresh row carries 0 for the three numeric cells — the stored "not entered
// yet" value (`partIsInvalid` rejects it). Painting a literal 0 in the box makes
// an untouched row look filled in and forces the user to clear it before typing,
// so 0 renders as an empty field. `v-model.number` hands back '' when the field
// is cleared, hence the widened cell type.
type NumericCell = number | string | null

function toStoredNumber(value: NumericCell): number {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function blankWhenUnset(value: number): number | null {
  return value > 0 ? value : null
}

const lengthModel = computed<NumericCell>({
  get: () => blankWhenUnset(props.part.length_mm),
  set: (value) => emit('update:length', toStoredNumber(value)),
})
const widthModel = computed<NumericCell>({
  get: () => blankWhenUnset(props.part.width_mm),
  set: (value) => emit('update:width', toStoredNumber(value)),
})
const quantityModel = computed<NumericCell>({
  get: () => blankWhenUnset(props.part.quantity),
  set: (value) => emit('update:quantity', toStoredNumber(value)),
})
const nameModel = computed({
  get: () => props.part.name ?? '',
  set: (value: string) => {
    const next = value.trim()
    emit('update:name', next || null)
  },
})

const followsGrain = computed(() => props.part.follow_grain !== false)
// The cell names the permission («Burilish»), not the material property, so the
// switch is ON when rotation is ALLOWED — the inverse of `follow_grain`. The
// stored field keeps its meaning; only this control is flipped.
const rotationAllowed = computed(() => !followsGrain.value)
const grainTitle = computed(() =>
  rotationAllowed.value ? t('cutting.parts.rotationAllowed') : t('cutting.parts.rotationLocked'),
)

const notCarriedNonPanel = computed(() => props.notCarried.some((issue) => issue !== 'panel'))

function edgeRegistryEntry(side: EdgeField) {
  const band = props.part[side]
  return registryEntryForBand(props.edgeRegistry, band?.material_id, band?.source)
}

function edgeGlyphStyle() {
  const sideStyles = {
    edge_top: 'borderTop',
    edge_bottom: 'borderBottom',
    edge_left: 'borderLeft',
    edge_right: 'borderRight',
  } as const
  return Object.fromEntries(
    Object.entries(sideStyles).map(([side, property]) => {
      const entry = edgeRegistryEntry(side as EdgeField)
      return [
        property,
        entry ? `3px solid ${entry.colorStyle.bg}` : '1px dashed var(--color-hairline-strong)',
      ]
    }),
  )
}

function toggleFollowGrain() {
  emit('update:follow-grain', rotationAllowed.value)
}

function duplicateFromMenu() {
  actionsOpen.value = false
  emit('duplicate')
}

function moveFromMenu() {
  actionsOpen.value = false
  emit('open-material-picker')
}

function deleteFromMenu() {
  actionsOpen.value = false
  emit('delete')
}

function onRapidEntryKeydown(event: KeyboardEvent, cell: 'name' | 'length' | 'width' | 'quantity') {
  if (event.key !== 'Enter' && (event.key !== 'Tab' || event.shiftKey)) return
  event.preventDefault()
  emit('cell-enter', cell)
}

function placeNumericCaretAtEnd(event: FocusEvent) {
  const input = event.target
  if (input instanceof HTMLInputElement) {
    const end = input.value.length
    input.setSelectionRange(end, end)
  }
}

function focusNumericFromPointer(event: MouseEvent) {
  const input = event.currentTarget
  if (!(input instanceof HTMLInputElement) || document.activeElement === input) return
  // A native click positions the caret after `focus`, overriding the focus
  // handler. Own the initial pointer focus; subsequent clicks stay native.
  event.preventDefault()
  input.focus()
  const end = input.value.length
  input.setSelectionRange(end, end)
}
</script>

<template>
  <article
    :id="`part-row-${part.part_ref}`"
    class="border-b border-hairline px-2 py-1.5 transition last:border-b-0 focus-within:bg-accent-soft/40"
    :class="hasError ? 'border-danger-soft bg-danger-soft/60' : 'border-hairline bg-elevated'"
  >
    <div
      class="grid gap-2 @min-[680px]:grid-cols-[28px_minmax(150px,50%)_repeat(6,minmax(32px,1fr))] @min-[680px]:items-center @min-[680px]:gap-1.5"
    >
      <div
        class="font-mono text-xs font-extrabold text-ink-muted @min-[680px]:col-start-1 @min-[680px]:row-start-1"
      >
        #{{ (displayIndex ?? index) + 1 }}
      </div>

      <div
        class="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_auto_auto] items-center gap-3 @min-[680px]:contents"
      >
        <label
          class="grid min-w-0 gap-1 text-xs font-bold text-ink-muted @min-[680px]:col-start-2 @min-[680px]:row-start-1"
        >
          <span class="@min-[920px]:hidden">{{ $t('cutting.column.name') }}</span>
          <input
            v-model="nameModel"
            :data-part-index="index"
            data-cell="name"
            class="mp-input border-hairline bg-elevated/40 @min-[680px]:min-h-9 @min-[680px]:px-1 hover:border-hairline-strong focus:border-accent"
            :placeholder="partDisplayName(part, index)"
            :aria-label="$t('cutting.column.name')"
            @keydown="onRapidEntryKeydown($event, 'name')"
          />
        </label>
        <div
          class="grid justify-items-center gap-1 text-[10px] font-bold text-ink-muted @min-[680px]:col-start-6 @min-[680px]:row-start-1"
        >
          <span class="@min-[920px]:hidden">{{ $t('cutting.column.rotation') }}</span>
          <!-- A bare checkbox under a one-word header never said which way it
               meant; the glyph shows the state itself. `switch` (not a checkbox)
               because the two states are both meaningful, not on/absent. -->
          <button
            data-test="follow-grain"
            type="button"
            role="switch"
            :aria-checked="rotationAllowed"
            class="grid size-8 place-items-center rounded-md border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-tint"
            :class="
              rotationAllowed
                ? 'border-hairline bg-sunk/30 text-ink-muted hover:border-hairline-strong hover:bg-sunk'
                : 'border-accent-tint bg-accent-soft text-accent hover:border-accent'
            "
            :title="grainTitle"
            :aria-label="grainTitle"
            @click="toggleFollowGrain"
          >
            <Icon :name="rotationAllowed ? 'rotate' : 'grain'" class="size-[18px]" />
          </button>
        </div>
        <div
          class="grid justify-items-center gap-1 text-[10px] font-bold text-ink-muted @min-[680px]:col-start-7 @min-[680px]:row-start-1"
        >
          <span class="@min-[680px]:hidden">{{ $t('cutting.column.edge') }}</span>
          <button
            type="button"
            :data-part-index="index"
            data-cell="edge"
            class="size-8 rounded-md bg-sunk/30 transition hover:bg-sunk"
            :style="edgeGlyphStyle()"
            :title="$t('cutting.column.edge')"
            :aria-label="$t('cutting.edge.sidesAria')"
            aria-haspopup="dialog"
            @click="emit('open-edge-picker', $event)"
          ></button>
        </div>
        <div
          class="relative grid justify-items-center gap-1 text-[10px] font-bold text-ink-muted @min-[680px]:col-start-8 @min-[680px]:row-start-1 @min-[680px]:flex @min-[680px]:justify-end"
        >
          <span class="@min-[680px]:hidden">{{ $t('cutting.column.actions') }}</span>
          <button
            v-if="actionsOpen"
            type="button"
            class="fixed inset-0 z-20 cursor-default"
            :aria-label="$t('cutting.parts.closeActions')"
            @click="actionsOpen = false"
          ></button>
          <button
            type="button"
            class="mp-action-icon-button size-8 min-h-0"
            :aria-label="$t('cutting.parts.rowActionsAria', { n: index + 1 })"
            :title="$t('cutting.column.actions')"
            @click="actionsOpen = !actionsOpen"
          >
            ⋯
          </button>
          <div
            v-if="actionsOpen"
            class="absolute bottom-9 right-0 z-30 grid min-w-48 overflow-hidden rounded-md border border-hairline-strong bg-elevated py-1 shadow-lg"
          >
            <button
              type="button"
              class="relative z-30 flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-sunk"
              @click="duplicateFromMenu"
            >
              <Icon name="layers" class="size-4 text-ink-muted" />
              {{ $t('cutting.parts.duplicate') }}
            </button>
            <button
              type="button"
              class="relative z-30 flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-sunk"
              @click="moveFromMenu"
            >
              <Icon name="swap" class="size-4 text-ink-muted" />
              {{ $t('cutting.parts.moveToMaterial') }}
            </button>
            <button
              type="button"
              class="relative z-30 flex items-center gap-2 px-3 py-2 text-left text-sm text-danger hover:bg-danger-soft"
              @click="deleteFromMenu"
            >
              <Icon name="trash" class="size-4" />
              {{ $t('cutting.action.delete') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Below the single-row fit width: the three dimensions share one row;
           @min-[920px]:contents dissolves this wrapper so each input is a
           column of the parent grid again (single-row layout unchanged) — CB-60. -->
      <div class="grid grid-cols-3 gap-2 @min-[680px]:contents">
        <label
          class="grid gap-1 text-xs font-bold text-ink-muted @min-[680px]:col-start-3 @min-[680px]:row-start-1"
        >
          <span class="@min-[920px]:hidden">{{ $t('cutting.column.length') }}</span>
          <input
            v-model.number="lengthModel"
            :data-part-index="index"
            data-cell="length"
            type="number"
            :min="MIN_PART_MM"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input border-hairline bg-elevated/40 text-right font-mono @min-[680px]:min-h-9 @min-[680px]:px-1 hover:border-hairline-strong focus:border-accent"
            :class="part.length_mm < MIN_PART_MM || sizeError ? 'border-danger' : ''"
            :aria-label="$t('cutting.parts.lengthAria')"
            @mousedown="focusNumericFromPointer"
            @focus="placeNumericCaretAtEnd"
            @keydown="onRapidEntryKeydown($event, 'length')"
          />
        </label>

        <label
          class="grid gap-1 text-xs font-bold text-ink-muted @min-[680px]:col-start-4 @min-[680px]:row-start-1"
        >
          <span class="@min-[920px]:hidden">{{ $t('cutting.column.width') }}</span>
          <input
            v-model.number="widthModel"
            :data-part-index="index"
            data-cell="width"
            type="number"
            :min="MIN_PART_MM"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input border-hairline bg-elevated/40 text-right font-mono @min-[680px]:min-h-9 @min-[680px]:px-1 hover:border-hairline-strong focus:border-accent"
            :class="part.width_mm < MIN_PART_MM || sizeError ? 'border-danger' : ''"
            :aria-label="$t('cutting.parts.widthAria')"
            @mousedown="focusNumericFromPointer"
            @focus="placeNumericCaretAtEnd"
            @keydown="onRapidEntryKeydown($event, 'width')"
          />
        </label>

        <label
          class="grid gap-1 text-xs font-bold text-ink-muted @min-[680px]:col-start-5 @min-[680px]:row-start-1"
        >
          <span class="@min-[920px]:hidden">{{ $t('cutting.column.quantity') }}</span>
          <input
            v-model.number="quantityModel"
            :data-part-index="index"
            data-cell="quantity"
            type="number"
            min="1"
            inputmode="numeric"
            enterkeyhint="done"
            class="mp-input border-hairline bg-elevated/40 text-right font-mono @min-[680px]:min-h-9 @min-[680px]:px-1 hover:border-hairline-strong focus:border-accent"
            :class="part.quantity < 1 ? 'border-danger' : ''"
            :aria-label="$t('cutting.column.quantity')"
            @mousedown="focusNumericFromPointer"
            @focus="placeNumericCaretAtEnd"
            @keydown="onRapidEntryKeydown($event, 'quantity')"
          />
        </label>
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
      <span>{{ $t('cutting.parts.materialMissing') }}</span>
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
      <!-- `i18n-t` rather than `$t`: the branch name is bold *inside* the
           sentence, and Russian does not put it where Uzbek does — splitting the
           message around the <b> would make the word order untranslatable. -->
      <i18n-t keypath="cutting.parts.notCarried" tag="span" scope="global" class="min-w-0 flex-1">
        <template #branch>
          <b>{{ preferredBranchName }}</b>
        </template>
      </i18n-t>
      <button
        v-if="notCarriedNonPanel"
        type="button"
        class="mp-button mp-button-outline"
        @click="emit('open-edge-picker', undefined)"
      >
        {{ $t('cutting.parts.pickAnotherEdge') }}
      </button>
    </div>
  </article>
</template>
