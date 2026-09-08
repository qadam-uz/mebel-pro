<script setup lang="ts">
/**
 * The o'lcham block: a type chip row, two dimension chip rows and an
 * «+ Qo'shish» that composes ONE format.
 *
 * Shared by the two places a workshop enters a size it cannot find in the
 * library — «Yangi dekor»'s O'lchamlar field (many at once, collected into a
 * list) and step 2's «+ Boshqa o'lcham» (one at a time, posted straight away).
 * Both compose exactly the same object, so they compose it here rather than
 * twice.
 *
 * **The type belongs to the format, not to the decor** (owner review of PR
 * #148): Egger H1145 is one decor carrying an LDSP board *and* a kromka. So the
 * chip row lives here, inside the composer, rather than once at the top of the
 * form — every format the operator composes states its own substrate, and one
 * creation can mix them. The host only says what the row should OPEN on.
 *
 * The chips come from `standardFormats.ts` and are a typing shortcut, not data:
 * anything a manufacturer makes off that list is typed under «Boshqa…», and the
 * two types with no standard set at all (yog'och, boshqa) open on the manual
 * inputs because there is nothing to offer them.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { DECOR_TYPES, decorTypeChoiceLabel, isTape } from '@/shared/app/materialLabel'
import {
  hasFinishedSides,
  normalizePanelSize,
  normalizeThickness,
  standardFormatSet,
  type FormatDraft,
} from '@/shared/app/standardFormats'
import ClientChipFilter from '@/shared/components/ClientChipFilter.vue'
import type { DecorType } from '@/shared/stores/admin'

const props = withDefaults(
  defineProps<{
    /**
     * What the type row opens on — the create form takes the default, the
     * attach sheet passes the decor group's first format type. It seeds the
     * row; it does not pin it, and the operator may switch to any substrate.
     */
    initialType?: DecorType
    /** A post is in flight — «+ Qo'shish» disables so it cannot double-fire. */
    busy?: boolean
    /** Rejection from the host (a duplicate, a refused create). */
    error?: string | null
    /** The block itself is the rejected field — draws the danger frame. */
    invalid?: boolean
    describedBy?: string
  }>(),
  { initialType: 'ldsp', busy: false, error: null, invalid: false, describedBy: undefined },
)

const emit = defineEmits<{ add: [draft: FormatDraft] }>()

const { t } = useI18n()

const type = ref<DecorType>(props.initialType)

/**
 * Seven substrates, so a chip row rather than a `SegmentedControl` — DESIGN.md
 * caps that primitive at three or four segments.
 */
const typeChips = computed(() =>
  DECOR_TYPES.map((value) => ({
    value,
    label: decorTypeChoiceLabel(value, t('inventory.attach.typeOther')),
  })),
)

const set = computed(() => standardFormatSet(type.value))
const tape = computed(() => isTape(type.value))
const boards = computed(() => hasFinishedSides(type.value))

const thickness = ref('')
const thicknessCustom = ref(false)
const thicknessText = ref('')
const sizeKey = ref('')
const sizeCustom = ref(false)
const lengthText = ref('')
const widthText = ref('')
const tapeWidthText = ref('')
const oneSided = ref(false)
const localError = ref<string | null>(null)

/** A size chip's identity — `2800x2070`, or the tape width as a plain number. */
function panelKey(length: number, width: number) {
  return `${length}x${width}`
}

/** With no standard set there is nothing to pick, so the fields open typed. */
const thicknessOpen = computed(() => thicknessCustom.value || set.value.qalinliklar.length === 0)
const sizeChips = computed(() =>
  tape.value
    ? set.value.kromkaEnlar.map((width) => ({ key: String(width), label: `${width} mm` }))
    : set.value.olchamlar.map((size) => ({
        key: panelKey(size.length_mm, size.width_mm),
        label: `${size.length_mm}×${size.width_mm}`,
      })),
)
const sizeOpen = computed(() => sizeCustom.value || sizeChips.value.length === 0)
const sizeLabel = computed(() =>
  tape.value ? t('inventory.attach.tapeWidthLabel') : t('inventory.attach.sizeLabel'),
)

/** A type switch swaps both chip sets, so nothing picked under the old one survives. */
watch(type, () => reset())

/** The host re-seeded the row (a different decor group's composer). */
watch(
  () => props.initialType,
  (value) => {
    type.value = value
  },
)

function setType(value: string) {
  type.value = value as DecorType
}

function reset() {
  thickness.value = ''
  thicknessCustom.value = false
  thicknessText.value = ''
  sizeKey.value = ''
  sizeCustom.value = false
  lengthText.value = ''
  widthText.value = ''
  tapeWidthText.value = ''
  oneSided.value = false
  localError.value = null
}

defineExpose({ reset })

function pickThickness(value: string) {
  thickness.value = value
  thicknessCustom.value = false
  thicknessText.value = ''
  localError.value = null
}

function pickSize(key: string) {
  sizeKey.value = key
  sizeCustom.value = false
  lengthText.value = ''
  widthText.value = ''
  tapeWidthText.value = ''
  localError.value = null
}

function openThicknessCustom() {
  thicknessCustom.value = true
  thickness.value = ''
  localError.value = null
}

function openSizeCustom() {
  sizeCustom.value = true
  sizeKey.value = ''
  localError.value = null
}

/** A positive number, or `null` — the one place free text becomes a dimension. */
function positive(text: string): number | null {
  const value = Number(text.replace(',', '.').trim())
  return Number.isFinite(value) && value > 0 ? value : null
}

/**
 * The composed draft, or `null` with `localError` set.
 *
 * Every refusal names the missing half rather than the block as a whole: over
 * a thickness row and a size row, "something is wrong" leaves the operator
 * pressing chips at random.
 */
function compose(): FormatDraft | null {
  const thicknessValue = thicknessOpen.value ? positive(thicknessText.value) : null
  const rawThickness = thicknessOpen.value
    ? thicknessValue !== null
      ? String(thicknessValue)
      : ''
    : thickness.value
  if (!rawThickness) {
    localError.value = t('inventory.attach.thicknessRequired')
    return null
  }
  const finished = boards.value ? (oneSided.value ? 1 : 2) : null
  if (tape.value) {
    const width = sizeOpen.value ? positive(tapeWidthText.value) : Number(sizeKey.value)
    if (!width || !Number.isFinite(width)) {
      localError.value = t('inventory.attach.sizeRequired')
      return null
    }
    return {
      type: type.value,
      thickness_mm: normalizeThickness(rawThickness),
      length_mm: null,
      width_mm: null,
      tape_width_mm: width,
      finished_sides: finished,
    }
  }
  let length: number | null
  let width: number | null
  if (sizeOpen.value) {
    length = positive(lengthText.value)
    width = positive(widthText.value)
  } else {
    const [a, b] = sizeKey.value.split('x').map(Number)
    length = Number.isFinite(a) && a > 0 ? a : null
    width = Number.isFinite(b) && b > 0 ? b : null
  }
  if (length === null || width === null) {
    localError.value = t('inventory.attach.sizeRequired')
    return null
  }
  // Longer side first, so `1830×2750` typed by hand is the same o'lcham as the
  // `2750×1830` chip rather than a second row nobody can tell apart.
  const size = normalizePanelSize(length, width)
  return {
    type: type.value,
    thickness_mm: normalizeThickness(rawThickness),
    length_mm: size.length_mm,
    width_mm: size.width_mm,
    tape_width_mm: null,
    finished_sides: finished,
  }
}

function submit() {
  localError.value = null
  const draft = compose()
  if (!draft) return
  emit('add', draft)
}

const message = computed(() => localError.value ?? props.error)
</script>

<template>
  <div
    class="grid gap-2 rounded-md border px-3 py-3"
    :class="invalid || message ? 'border-danger bg-danger-soft/40' : 'border-hairline bg-sunk'"
    :aria-describedby="describedBy"
  >
    <!-- Turi leads: it drives the two chip rows under it, so choosing it later
         would swap a set the operator had already picked from. -->
    <div class="grid gap-1">
      <span class="text-xs font-bold text-ink-soft">{{ $t('inventory.attach.typeLabel') }}</span>
      <ClientChipFilter
        :label="$t('inventory.attach.typeLabel')"
        :model-value="type"
        :options="typeChips"
        @update:model-value="setType"
      />
    </div>

    <div class="grid gap-1">
      <span class="text-xs font-bold text-ink-soft">{{
        $t('inventory.attach.thicknessLabel')
      }}</span>
      <div class="flex flex-wrap items-center gap-1.5">
        <button
          v-for="value in set.qalinliklar"
          :key="value"
          type="button"
          class="mp-chip cursor-pointer transition-colors"
          :class="
            !thicknessCustom && thickness === value
              ? 'border-select-chip-line bg-select-chip text-ink'
              : 'hover:border-accent'
          "
          :aria-pressed="!thicknessCustom && thickness === value"
          @click="pickThickness(value)"
        >
          {{ value }}
        </button>
        <button
          v-if="set.qalinliklar.length > 0"
          type="button"
          class="text-xs font-bold text-accent-deep hover:underline"
          :aria-pressed="thicknessCustom"
          @click="openThicknessCustom"
        >
          {{ $t('inventory.attach.otherValue') }}
        </button>
      </div>
      <input
        v-if="thicknessOpen"
        v-model="thicknessText"
        class="mp-input max-w-[160px]"
        inputmode="decimal"
        placeholder="18"
        :aria-label="$t('inventory.attach.thicknessLabel')"
      />
    </div>

    <div class="grid gap-1">
      <span class="text-xs font-bold text-ink-soft">{{ sizeLabel }}</span>
      <div class="flex flex-wrap items-center gap-1.5">
        <button
          v-for="chip in sizeChips"
          :key="chip.key"
          type="button"
          class="mp-chip cursor-pointer transition-colors"
          :class="
            !sizeCustom && sizeKey === chip.key
              ? 'border-select-chip-line bg-select-chip text-ink'
              : 'hover:border-accent'
          "
          :aria-pressed="!sizeCustom && sizeKey === chip.key"
          @click="pickSize(chip.key)"
        >
          {{ chip.label }}
        </button>
        <button
          v-if="sizeChips.length > 0"
          type="button"
          class="text-xs font-bold text-accent-deep hover:underline"
          :aria-pressed="sizeCustom"
          @click="openSizeCustom"
        >
          {{ $t('inventory.attach.otherValue') }}
        </button>
      </div>
      <div v-if="sizeOpen" class="flex flex-wrap items-center gap-2">
        <template v-if="tape">
          <input
            v-model="tapeWidthText"
            class="mp-input max-w-[160px]"
            inputmode="decimal"
            placeholder="22"
            :aria-label="$t('inventory.attach.tapeWidthLabel')"
          />
        </template>
        <template v-else>
          <input
            v-model="lengthText"
            class="mp-input max-w-[130px]"
            inputmode="numeric"
            placeholder="2800"
            :aria-label="$t('inventory.attach.lengthLabel')"
          />
          <span class="text-ink-muted" aria-hidden="true">×</span>
          <input
            v-model="widthText"
            class="mp-input max-w-[130px]"
            inputmode="numeric"
            placeholder="2070"
            :aria-label="$t('inventory.attach.widthLabel')"
          />
        </template>
      </div>
    </div>

    <div class="flex flex-wrap items-center justify-between gap-3">
      <!-- A checkbox, not a switch: DESIGN.md requires a switch to carry its
           state as a word, and «1 tomonlama» is a fact about the sheet, not a
           setting that has an off-word. Two-sided is the silent default. -->
      <label
        v-if="boards"
        class="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold text-ink"
      >
        <input v-model="oneSided" type="checkbox" class="size-4 shrink-0 accent-accent" />
        {{ $t('inventory.attach.oneSided') }}
      </label>
      <span v-else></span>
      <button type="button" class="mp-button mp-button-outline" :disabled="busy" @click="submit">
        {{ busy ? $t('inventory.attach.saving') : $t('inventory.attach.addFormat') }}
      </button>
    </div>

    <p v-if="message" class="mp-field-error" role="alert">{{ message }}</p>
  </div>
</template>
