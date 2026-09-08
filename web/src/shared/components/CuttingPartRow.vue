<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { MIN_PART_MM } from '@/shared/app/constants'
import { sanitizeWholeNumberInput } from '@/shared/app/inputSanitizers'
import { type EdgeField } from '@/shared/app/cuttingDisplay'
import {
  partDisplayName,
  registryEntryForBand,
  type EdgeRegistryEntry,
} from '@/shared/app/cuttingEditorDerived'
import Icon from '@/shared/components/AppIcon.vue'
import { type CuttingPart } from '@/shared/stores/cutting'

// CB-93 seam: one parts-table row. Purely presentational — the editor stays the
// single owner of `parts`, validation (size/missing/optimiser errors),
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
  edgeRegistry: EdgeRegistryEntry[]
  /** The order wizard's row: a bare `1` rather than `#1`, and delete promoted
   *  out of the ⋯ menu into the row — the shape the design draws. */
  bareIndex?: boolean
  /** Drives the wizard's docked kromka panel. The row marks itself; it does not
   *  own the selection — the editor does, because the panel is its sibling. */
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
  'cell-enter': [cell: 'name' | 'length' | 'width' | 'quantity']
  'open-edge-picker': [Event | undefined]
  'open-material-picker': []
  'toggle-select': []
  /** "This row is the subject now." Fired by a pointer anywhere in the row and
   *  by focus landing in any of its cells, so the panel follows the caret through
   *  an Enter/Tab walk without the operator ever reaching for the mouse. */
  select: []
}>()

const { t } = useI18n()

// Writable computeds keep the original `v-model.number` semantics while emitting
// (a number input bound straight to the prop would mutate it).
// A fresh row carries 0 for the three numeric cells — the stored "not entered
// yet" value (`partIsInvalid` rejects it). Painting a literal 0 in the box makes
// an untouched row look filled in and forces the user to clear it before typing,
// so 0 renders as an empty field. `v-model.number` hands back '' when the field
// is cleared, hence the widened cell type.
type NumericCell = number | string | null

// The field is plain text now, so the alphabet has to be constrained here
// rather than by the input type. Rejecting at `beforeinput` keeps the caret
// where it was — rewriting `value` afterwards would jump it to the end.
function onWholeNumberBeforeInput(event: Event) {
  const input = event as InputEvent
  if (typeof input.data !== 'string' || input.data === '') return
  if (sanitizeWholeNumberInput(input.data) !== input.data) event.preventDefault()
}

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

function edgeRegistryEntry(side: EdgeField) {
  const band = props.part[side]
  return registryEntryForBand(props.edgeRegistry, band?.material_id, band?.source)
}

// The tape mark: a 20x15 rectangle whose banded sides are drawn thick and whose
// fill is the tape's own colour. Geometry, weights and the bare-side colour are
// the handoff's, to the pixel.
//
// One deviation, and it adds rather than removes: a banded side keeps its tape's
// registry colour instead of a flat ink. The handoff assumes one tape per row,
// but this editor lets four sides carry four different tapes and numbers them —
// flattening them here would delete the only place the row shows which is which.
// With a single tape the two are identical anyway, because the fill carries that
// same colour.
function edgeGlyphStyle() {
  const sideStyles = {
    edge_top: 'borderTop',
    edge_bottom: 'borderBottom',
    edge_left: 'borderLeft',
    edge_right: 'borderRight',
  } as const
  // The banded edge is drawn in ink, never in the tape's own colour: the fill
  // beneath it IS that colour, so a coloured border on it made the whole glyph
  // one flat block — a dark tape lost its sides entirely. Ink on the fill keeps
  // "which sides" readable whatever the tape is, and the fill still answers
  // "which tape".
  const entries = Object.entries(sideStyles).map(([side, property]) => {
    const entry = edgeRegistryEntry(side as EdgeField)
    return [
      property,
      entry ? '2.5px solid var(--color-accent)' : '1.5px solid var(--color-hairline)',
    ] as const
  })
  const fills = (Object.keys(sideStyles) as EdgeField[])
    .map((side) => edgeRegistryEntry(side)?.colorStyle.bg)
    .filter((fill): fill is string => Boolean(fill))
  return {
    ...Object.fromEntries(entries),
    // Only when the row is on one tape: two tapes have no single fill to be.
    background: fills.length > 0 && new Set(fills).size === 1 ? fills[0] : 'transparent',
  }
}

function toggleFollowGrain() {
  emit('update:follow-grain', rotationAllowed.value)
}

// ↑/↓ step the three numeric cells — how a mistyped `2749` becomes `2750` and how
// `soni` goes 4 → 6 without retyping. Shift steps by 10, as the handoff prototype
// does. `name` keeps the arrows for caret movement, and the cells sanitize their
// own input, so native `type="number"` spinners are not the fallback here.
//
// Floors only, no ceiling. The floor stops a step from manufacturing an invalid
// row (0 is "not entered"; a row needs at least one piece). The prototype also
// caps at 999/9999, and we deliberately don't: the editor already validates size
// and the 300-part budget with named, visible errors, and a silent cap would
// swallow the very message the UX bar requires the operator to see.
const NUMERIC_STEP_CELLS = ['length', 'width', 'quantity'] as const
type NumericStepCell = (typeof NUMERIC_STEP_CELLS)[number]

function isNumericStepCell(cell: string): cell is NumericStepCell {
  return (NUMERIC_STEP_CELLS as readonly string[]).includes(cell)
}

function stepNumericCell(cell: NumericStepCell, delta: number) {
  if (cell === 'quantity') {
    emit('update:quantity', Math.max(1, props.part.quantity + delta))
    return
  }
  if (cell === 'length') {
    emit('update:length', Math.max(0, props.part.length_mm + delta))
    return
  }
  emit('update:width', Math.max(0, props.part.width_mm + delta))
}

function onRapidEntryKeydown(event: KeyboardEvent, cell: 'name' | 'length' | 'width' | 'quantity') {
  if ((event.key === 'ArrowUp' || event.key === 'ArrowDown') && isNumericStepCell(cell)) {
    event.preventDefault()
    const magnitude = event.shiftKey ? 10 : 1
    stepNumericCell(cell, event.key === 'ArrowUp' ? magnitude : -magnitude)
    return
  }
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
    class="group/row rounded-[10px] py-[3px] pl-0 pr-1.5 transition"
    :class="[
      hasError ? 'bg-danger-soft/60' : 'bg-elevated',
      // Outline, never border: a border would add a pixel to the row box and
      // shift every column against the header above it. An error still wins the
      // background — a row that cannot be cut outranks a row being edited.
      selected
        ? 'outline outline-1 -outline-offset-1 outline-select-line ' +
          (hasError ? '' : '!bg-select-wash')
        : 'focus-within:bg-sunk',
    ]"
    @focusin="emit('select')"
    @pointerdown="emit('select')"
  >
    <div
      class="grid gap-2 @min-[660px]:grid-cols-[26px_208px_80px_80px_56px_62px_54px_44px] @min-[660px]:w-max @min-[660px]:items-center @min-[660px]:gap-[7px]"
    >
      <div
        class="text-xs font-extrabold @min-[660px]:col-start-1 @min-[660px]:row-start-1"
        :class="selected ? 'text-ink' : 'text-ink-muted'"
      >
        <span v-if="bareIndex">{{ (displayIndex ?? index) + 1 }}</span>
        <span v-else>#{{ (displayIndex ?? index) + 1 }}</span>
      </div>

      <div
        class="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_auto_auto] items-center gap-3 @min-[660px]:contents"
      >
        <label
          class="grid min-w-0 gap-1 text-xs font-bold text-ink-muted @min-[660px]:col-start-2 @min-[660px]:row-start-1"
        >
          <span class="@min-[660px]:hidden">{{ $t('cutting.column.name') }}</span>
          <input
            v-model="nameModel"
            :data-part-index="index"
            data-cell="name"
            class="mp-input bg-elevated/40 @min-[660px]:min-h-[38px] @min-[660px]:rounded-[9px] @min-[660px]:px-[10px] hover:border-hairline-strong"
            :placeholder="partDisplayName(part, index)"
            :aria-label="$t('cutting.column.name')"
            @keydown="onRapidEntryKeydown($event, 'name')"
          />
        </label>
        <div
          class="grid justify-items-center gap-1 text-[10px] font-bold text-ink-muted @min-[660px]:col-start-6 @min-[660px]:row-start-1"
        >
          <span class="@min-[660px]:hidden">{{ $t('cutting.column.rotation') }}</span>
          <!-- A bare checkbox under a one-word header never said which way it
               meant; the glyph shows the state itself. `switch` (not a checkbox)
               because the two states are both meaningful, not on/absent.
               Icon-only: this is a state the operator scans down a column of 25
               rows, and a bordered chip on every locked row builds a second
               column of boxes beside the inputs. The glyph alone carries it;
               background appears on hover, where it means "clickable". -->
          <button
            data-test="follow-grain"
            type="button"
            role="switch"
            :aria-checked="rotationAllowed"
            class="grid h-[38px] w-full place-items-center rounded-[9px] transition hover:bg-sunk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
            :class="rotationAllowed ? 'text-ink-muted' : 'text-ink'"
            :title="grainTitle"
            :aria-label="grainTitle"
            @click="toggleFollowGrain"
          >
            <Icon :name="rotationAllowed ? 'rotate' : 'grain'" class="size-[18px]" />
          </button>
        </div>
        <div
          class="grid justify-items-center gap-1 text-[10px] font-bold text-ink-muted @min-[660px]:col-start-7 @min-[660px]:row-start-1"
        >
          <span class="@min-[660px]:hidden">{{ $t('cutting.column.edge') }}</span>
          <button
            type="button"
            :data-part-index="index"
            data-cell="edge"
            class="grid h-[38px] w-full place-items-center rounded-md transition hover:bg-sunk"
            :title="part.thickened ? $t('cutting.thickening.label') : $t('cutting.column.edge')"
            :aria-label="
              part.thickened
                ? `${$t('cutting.edge.sidesAria')} · ${$t('cutting.thickening.label')}`
                : $t('cutting.edge.sidesAria')
            "
            aria-haspopup="dialog"
            @click="emit('open-edge-picker', $event)"
          >
            <!-- The 20x15 rectangle is the mark; the button around it is the
                 hit target, which has to stay big enough to press. The stamp
                 sits inside the rectangle because thickening is a property of
                 the part, not of a side. -->
            <span
              data-test="edge-glyph"
              class="grid h-[15px] w-5 place-items-center rounded-[3px] text-[8px] font-black leading-none text-ink"
              :style="edgeGlyphStyle()"
            >
              <span v-if="part.thickened" aria-hidden="true">{{
                $t('cutting.thickening.mark')
              }}</span>
            </span>
          </button>
        </div>
        <div
          class="relative grid justify-items-center gap-1 text-[10px] font-bold text-ink-muted @min-[660px]:col-start-8 @min-[660px]:row-start-1 @min-[660px]:flex @min-[660px]:justify-end"
        >
          <span class="@min-[660px]:hidden">{{ $t('cutting.column.actions') }}</span>
          <!-- Delete is the row's own action and reads as one click, the way the
               design draws it. There is no ⋯ behind it: its only unique entries
               were duplicate and "move to another material", and a menu that
               exists for two rarely-used actions is a second thing to learn on
               the row the operator types into all day. -->
          <button
            type="button"
            class="mp-action-icon-button size-8 min-h-0 text-ink-muted hover:bg-danger-soft hover:text-danger"
            :aria-label="$t('cutting.action.delete')"
            :title="$t('cutting.action.delete')"
            @click="emit('delete')"
          >
            <Icon name="trash" class="size-4" />
          </button>
        </div>
      </div>

      <!-- Below the single-row fit width: the three dimensions share one row;
           @min-[660px]:contents dissolves this wrapper so each input is a
           column of the parent grid again (single-row layout unchanged) — CB-60. -->
      <div class="grid grid-cols-3 gap-2 @min-[660px]:contents">
        <label
          class="grid gap-1 text-xs font-bold text-ink-muted @min-[660px]:col-start-3 @min-[660px]:row-start-1"
        >
          <span class="@min-[660px]:hidden">{{ $t('cutting.column.length') }}</span>
          <input
            v-model.number="lengthModel"
            :data-part-index="index"
            data-cell="length"
            type="text"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input bg-elevated/40 text-right @min-[660px]:min-h-[38px] @min-[660px]:rounded-[9px] @min-[660px]:px-[10px] hover:border-hairline-strong"
            :class="part.length_mm < MIN_PART_MM || sizeError ? 'border-danger' : ''"
            :aria-label="$t('cutting.parts.lengthAria')"
            @beforeinput="onWholeNumberBeforeInput"
            @mousedown="focusNumericFromPointer"
            @focus="placeNumericCaretAtEnd"
            @keydown="onRapidEntryKeydown($event, 'length')"
          />
        </label>

        <label
          class="grid gap-1 text-xs font-bold text-ink-muted @min-[660px]:col-start-4 @min-[660px]:row-start-1"
        >
          <span class="@min-[660px]:hidden">{{ $t('cutting.column.width') }}</span>
          <input
            v-model.number="widthModel"
            :data-part-index="index"
            data-cell="width"
            type="text"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input bg-elevated/40 text-right @min-[660px]:min-h-[38px] @min-[660px]:rounded-[9px] @min-[660px]:px-[10px] hover:border-hairline-strong"
            :class="part.width_mm < MIN_PART_MM || sizeError ? 'border-danger' : ''"
            :aria-label="$t('cutting.parts.widthAria')"
            @beforeinput="onWholeNumberBeforeInput"
            @mousedown="focusNumericFromPointer"
            @focus="placeNumericCaretAtEnd"
            @keydown="onRapidEntryKeydown($event, 'width')"
          />
        </label>

        <label
          class="grid gap-1 text-xs font-bold text-ink-muted @min-[660px]:col-start-5 @min-[660px]:row-start-1"
        >
          <span class="@min-[660px]:hidden">{{ $t('cutting.column.quantity') }}</span>
          <input
            v-model.number="quantityModel"
            :data-part-index="index"
            data-cell="quantity"
            type="text"
            inputmode="numeric"
            enterkeyhint="done"
            class="mp-input bg-elevated/40 text-right @min-[660px]:min-h-[38px] @min-[660px]:rounded-[9px] @min-[660px]:px-[10px] hover:border-hairline-strong"
            :class="part.quantity < 1 ? 'border-danger' : ''"
            :aria-label="$t('cutting.column.quantity')"
            @beforeinput="onWholeNumberBeforeInput"
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
  </article>
</template>
