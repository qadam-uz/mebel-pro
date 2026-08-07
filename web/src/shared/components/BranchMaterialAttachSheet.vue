<script setup lang="ts">
/**
 * "+ Material" — attach one dekor to this branch in one or more formats.
 *
 * Two steps, because the catalog reshape split identity from format: step 1 picks
 * the *dekor* (a platform fact — manufacturer, tur, kod, nomi, photo), step 2
 * picks the *formats* (a branch fact — thickness × size, or thickness × tape
 * width). A dekor the branch already carries is never hidden: carrying 18 mm does
 * not stop you adding 16 mm, so it stays in the list with its carried-format count.
 *
 * The standard chip sets are hard-coded in the web app (`standardFormats.ts`) and
 * anything else the branch types in with "+ qo'shish" — it simply becomes that
 * branch's row, with no approval step. Price and threshold are optional and
 * default to 0: a branch routinely registers its whole format list before it
 * knows prices.
 */
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { apiTraceId, ApiError } from '@/shared/api/client'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { sanitizeMoneyInput, sanitizeQuantityInput } from '@/shared/app/inputSanitizers'
import { DEKOR_TYPES, dekorTurLabel, isTape } from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import {
  carriedFormatKeys,
  formatKey,
  nonStandardFacets,
  normalizePanelSize,
  normalizeQalinlik,
  standardFormatSet,
  type StandardFormatSet,
  type StandardPanelSize,
} from '@/shared/app/standardFormats'
import AppModal from '@/shared/components/AppModal.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import FormSelect from '@/shared/components/FormSelect.vue'
import { parseDisplayQuantity, parseSomToTiyin } from '@/shared/formatters'
import type { Dekor } from '@/shared/stores/admin'
import {
  defaultLowStockThreshold,
  thresholdUnit,
  lowStockThresholdColumn,
  lowStockThresholdHint,
  lowStockThresholdLabel,
} from '@/shared/app/lowStockThreshold'
import {
  useWorkshopStore,
  type BranchCatalogOption,
  type BranchMaterialFormatInput,
} from '@/shared/stores/workshop'

const props = defineProps<{ open: boolean; branchId: string }>()
const emit = defineEmits<{
  close: []
  // Both halves travel: a duplicate format is *skipped* server-side, never an
  // error, so the caller has to be able to say "3 added, 1 already there".
  attached: [result: { created: number; skipped: number }]
}>()

// Server-side page size for the dekor picker; "Ko'proq yuklash" pages past it.
const PAGE_LIMIT = 100

const { t } = useI18n()
const workshop = useWorkshopStore()

const EMPTY_SET: StandardFormatSet = { qalinliklar: [], olchamlar: [], kromkaEnlar: [] }

const step = ref<1 | 2>(1)
const search = ref('')
const manufacturerFilter = ref<string | null>('all')
const turFilter = ref<string | null>('all')
const options = ref<BranchCatalogOption[]>([])
const total = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const loadError = ref(false)
const selectedDekor = ref<Dekor | null>(null)
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveTraceId = ref<string | null>(null)
const bulkFill = reactive({ price: '', threshold: '' })

// Chip selections. Sizes are held as `L×W` keys so a size chip is one value on
// one axis; `sizeByKey` resolves it back when the cross product is built.
const pickedQalinliklar = ref<string[]>([])
const pickedSizeKeys = ref<string[]>([])
const pickedTapeWidths = ref<number[]>([])
// "+ qo'shish" additions, live only until the sheet closes — once submitted they
// become branch rows and `nonStandardFacets` picks them up from there.
const customQalinliklar = ref<string[]>([])
const customSizes = ref<StandardPanelSize[]>([])
const customTapeWidths = ref<number[]>([])

const customOpen = ref<'thickness' | 'size' | 'tape' | null>(null)
const customDraft = reactive({ thickness: '', length: '', width: '', tape: '' })
const customError = ref<string | null>(null)

// Price / threshold text per format key, read with a default rather than
// pre-seeded: the cross product changes on every chip click, and a synced map
// would either mutate during render or lose what the operator already typed.
const priceByKey = ref<Record<string, string>>({})
const thresholdByKey = ref<Record<string, string>>({})
const priceErrorKeys = ref<Set<string>>(new Set())
const thresholdErrorKeys = ref<Set<string>>(new Set())

// `FormSelect`, not `ProjectDropdown`: the latter teleports its panel at z-50 and
// would render behind the modal layer (z-80) — see web/DESIGN.md → Shapes.
const manufacturerOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: t('inventory.attach.manufacturerAll') },
  ...workshop.catalogFilters.manufacturers.map((row) => ({ value: row.id, label: row.name })),
])
// Every `tur` is offered, including `dsp` — it is a distinct wire value even
// though it shares the `LDSP` label, and dropping it would leave those dekorlar
// unreachable by filter.
const turOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: t('inventory.attach.turAll') },
  ...DEKOR_TYPES.map((value) => ({ value, label: dekorTurLabel(value) })),
])

const tur = computed(() => selectedDekor.value?.tur ?? null)
const tape = computed(() => isTape(tur.value))
const standard = computed(() => (tur.value ? standardFormatSet(tur.value) : EMPTY_SET))

/**
 * The branch's own non-standard facets plus anything added in this session.
 *
 * Derived from `workshop.branchMaterials`, the rows the catalog page has loaded.
 * That list is paged and filtered, so a format beyond it can slip through as
 * "not carried" — which is exactly why the response's `skipped` is surfaced as a
 * notice rather than an error.
 */
const customFacets = computed<StandardFormatSet>(() => {
  const dekor = selectedDekor.value
  if (!dekor || !tur.value) return EMPTY_SET
  const branch = nonStandardFacets(tur.value, workshop.branchMaterials, dekor.id)
  const qalinliklar = [...new Set([...branch.qalinliklar, ...customQalinliklar.value])].sort(
    (left, right) => Number(left) - Number(right),
  )
  const sizes = new Map<string, StandardPanelSize>()
  for (const size of [...branch.olchamlar, ...customSizes.value]) {
    sizes.set(sizeKey(size), size)
  }
  const kromkaEnlar = [...new Set([...branch.kromkaEnlar, ...customTapeWidths.value])].sort(
    (left, right) => left - right,
  )
  return { qalinliklar, olchamlar: tape.value ? [] : [...sizes.values()], kromkaEnlar }
})

const allSizes = computed(() => [...standard.value.olchamlar, ...customFacets.value.olchamlar])
const hasAnyThickness = computed(
  () => standard.value.qalinliklar.length + customFacets.value.qalinliklar.length > 0,
)
const hasAnySize = computed(() =>
  tape.value
    ? standard.value.kromkaEnlar.length + customFacets.value.kromkaEnlar.length > 0
    : allSizes.value.length > 0,
)

const carried = computed(() =>
  selectedDekor.value
    ? carriedFormatKeys(workshop.branchMaterials, selectedDekor.value.id)
    : new Set<string>(),
)

interface FormatCombo {
  key: string
  qalinlik: string
  size: StandardPanelSize | null
  kromkaEni: number | null
  label: string
  carried: boolean
}

const combinations = computed<FormatCombo[]>(() => {
  if (!tur.value || pickedQalinliklar.value.length === 0) return []
  const rows: FormatCombo[] = []
  for (const qalinlik of pickedQalinliklar.value) {
    if (tape.value) {
      for (const width of pickedTapeWidths.value) {
        const key = formatKey({ qalinlik_mm: qalinlik, kromka_eni_mm: width })
        rows.push({
          key,
          qalinlik,
          size: null,
          kromkaEni: width,
          label: t('catalog.meta.tapeFormat', { thickness: qalinlik, width }),
          carried: carried.value.has(key),
        })
      }
      continue
    }
    for (const sizeKeyValue of pickedSizeKeys.value) {
      const size = sizeByKey(sizeKeyValue)
      if (!size) continue
      const key = formatKey({
        qalinlik_mm: qalinlik,
        uzunlik_mm: size.uzunlik_mm,
        eni_mm: size.eni_mm,
      })
      rows.push({
        key,
        qalinlik,
        size,
        kromkaEni: null,
        label: t('catalog.meta.panelFormat', {
          length: size.uzunlik_mm,
          width: size.eni_mm,
          thickness: qalinlik,
        }),
        carried: carried.value.has(key),
      })
    }
  }
  return rows
})

const pendingCombos = computed(() => combinations.value.filter((row) => !row.carried))

function sizeKey(size: StandardPanelSize) {
  return `${size.uzunlik_mm}x${size.eni_mm}`
}

function sizeByKey(key: string) {
  return allSizes.value.find((size) => sizeKey(size) === key) ?? null
}

function swatchSource(dekor: Dekor) {
  return { id: dekor.id, nomi: dekor.nomi, kod: dekor.kod }
}

function priceUnit() {
  return tape.value ? t('inventory.attach.priceUnitMetre') : t('inventory.attach.priceUnitSheet')
}

function priceOf(key: string) {
  return priceByKey.value[key] ?? ''
}

function thresholdOf(key: string) {
  return thresholdByKey.value[key] ?? String(defaultLowStockThreshold())
}

function setPrice(key: string, value: string) {
  priceByKey.value = { ...priceByKey.value, [key]: sanitizeMoneyInput(value) }
  if (priceErrorKeys.value.has(key)) {
    const next = new Set(priceErrorKeys.value)
    next.delete(key)
    priceErrorKeys.value = next
  }
}

function setThreshold(key: string, value: string) {
  thresholdByKey.value = { ...thresholdByKey.value, [key]: sanitizeQuantityInput(value) }
  if (thresholdErrorKeys.value.has(key)) {
    const next = new Set(thresholdErrorKeys.value)
    next.delete(key)
    thresholdErrorKeys.value = next
  }
}

function toggle<T>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
}

function toggleQalinlik(value: string) {
  pickedQalinliklar.value = toggle(pickedQalinliklar.value, value)
}

function toggleSize(value: string) {
  pickedSizeKeys.value = toggle(pickedSizeKeys.value, value)
}

function toggleTapeWidth(value: number) {
  pickedTapeWidths.value = toggle(pickedTapeWidths.value, value)
}

function openCustom(kind: 'thickness' | 'size' | 'tape') {
  customOpen.value = customOpen.value === kind ? null : kind
  customError.value = null
  customDraft.thickness = ''
  customDraft.length = ''
  customDraft.width = ''
  customDraft.tape = ''
}

function positiveInt(value: string) {
  const parsed = Number(value.trim())
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function addCustomThickness() {
  const raw = customDraft.thickness.trim().replace(',', '.')
  const parsed = Number(raw)
  if (!raw || !Number.isFinite(parsed) || parsed <= 0) {
    customError.value = t('inventory.attach.customInvalid')
    return
  }
  const value = normalizeQalinlik(raw)
  const known = new Set([
    ...standard.value.qalinliklar.map(normalizeQalinlik),
    ...customFacets.value.qalinliklar,
  ])
  if (known.has(value)) {
    customError.value = t('inventory.attach.customDuplicate')
    // Still select it — the operator asked for this thickness and it exists.
    if (!pickedQalinliklar.value.includes(value)) toggleQalinlik(value)
    return
  }
  customQalinliklar.value = [...customQalinliklar.value, value]
  toggleQalinlik(value)
  customOpen.value = null
}

function addCustomSize() {
  const length = positiveInt(customDraft.length)
  const width = positiveInt(customDraft.width)
  if (length === null || width === null) {
    customError.value = t('inventory.attach.customInvalid')
    return
  }
  // Longer side first, so 1830×2750 and 2750×1830 are one chip, not two.
  const size = normalizePanelSize(length, width)
  const key = sizeKey(size)
  if (allSizes.value.some((known) => sizeKey(known) === key)) {
    customError.value = t('inventory.attach.customDuplicate')
    if (!pickedSizeKeys.value.includes(key)) toggleSize(key)
    return
  }
  customSizes.value = [...customSizes.value, size]
  toggleSize(key)
  customOpen.value = null
}

function addCustomTapeWidth() {
  const value = positiveInt(customDraft.tape)
  if (value === null) {
    customError.value = t('inventory.attach.customInvalid')
    return
  }
  const known = new Set([...standard.value.kromkaEnlar, ...customFacets.value.kromkaEnlar])
  if (known.has(value)) {
    customError.value = t('inventory.attach.customDuplicate')
    if (!pickedTapeWidths.value.includes(value)) toggleTapeWidth(value)
    return
  }
  customTapeWidths.value = [...customTapeWidths.value, value]
  toggleTapeWidth(value)
  customOpen.value = null
}

function filters(offset = 0) {
  return {
    search: search.value,
    tur: turFilter.value === 'all' ? null : (turFilter.value as Dekor['tur']),
    manufacturer_id: manufacturerFilter.value === 'all' ? null : manufacturerFilter.value,
    limit: PAGE_LIMIT,
    offset,
  }
}

async function loadOptions() {
  if (!props.branchId) return
  loading.value = true
  loadError.value = false
  try {
    const page = await workshop.fetchCatalogOptions(props.branchId, filters())
    options.value = page.items
    total.value = page.total
  } catch {
    loadError.value = true
    options.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadMoreOptions() {
  if (!props.branchId) return
  loadingMore.value = true
  try {
    const page = await workshop.fetchCatalogOptions(props.branchId, filters(options.value.length))
    options.value = [...options.value, ...page.items]
    total.value = page.total
  } catch {
    loadError.value = true
  } finally {
    loadingMore.value = false
  }
}

function selectDekor(dekor: Dekor) {
  if (selectedDekor.value?.id !== dekor.id) resetFormatPicks()
  selectedDekor.value = dekor
}

function resetFormatPicks() {
  pickedQalinliklar.value = []
  pickedSizeKeys.value = []
  pickedTapeWidths.value = []
  customQalinliklar.value = []
  customSizes.value = []
  customTapeWidths.value = []
  customOpen.value = null
  customError.value = null
  priceByKey.value = {}
  thresholdByKey.value = {}
  priceErrorKeys.value = new Set()
  thresholdErrorKeys.value = new Set()
  bulkFill.price = ''
  bulkFill.threshold = ''
  saveError.value = null
  saveTraceId.value = null
}

function applyBulkFill() {
  const price = bulkFill.price.trim()
  const threshold = bulkFill.threshold.trim()
  const nextPrice = { ...priceByKey.value }
  const nextThreshold = { ...thresholdByKey.value }
  for (const row of pendingCombos.value) {
    if (price) nextPrice[row.key] = price
    if (threshold) nextThreshold[row.key] = threshold
  }
  priceByKey.value = nextPrice
  thresholdByKey.value = nextThreshold
  priceErrorKeys.value = new Set()
  thresholdErrorKeys.value = new Set()
}

function apiMessage(error: unknown): string | null {
  if (!(error instanceof ApiError) || typeof error.body !== 'object' || error.body === null) {
    return null
  }
  const message = (error.body as { message?: unknown }).message
  return typeof message === 'string' && message.trim() ? message : null
}

/** Empty means "price it later" — 0 tiyin, not a validation failure. */
function parsePrice(text: string): number | null {
  const trimmed = text.trim()
  if (!trimmed) return 0
  const parsed = parseSomToTiyin(trimmed)
  if (parsed !== null) return parsed
  // `parseSomToTiyin` rejects 0 so a 0 so'm material can never reach the client
  // catalog by accident; here an explicit 0 is the documented "unpriced" value.
  return /^0+([.,]0+)?$/.test(trimmed) ? 0 : null
}

function parseThreshold(text: string): number | null {
  const trimmed = text.trim()
  if (!trimmed) return 0
  const parsed = parseDisplayQuantity(trimmed, tape.value ? 'm' : 'pcs')
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
}

async function submit() {
  saveError.value = null
  saveTraceId.value = null
  const dekor = selectedDekor.value
  if (!dekor) return
  if (pendingCombos.value.length === 0) {
    saveError.value = t('inventory.attach.selectFormats')
    return
  }
  const formats: BranchMaterialFormatInput[] = []
  const badPrices = new Set<string>()
  const badThresholds = new Set<string>()
  for (const row of pendingCombos.value) {
    const price = parsePrice(priceOf(row.key))
    const threshold = parseThreshold(thresholdOf(row.key))
    if (price === null) badPrices.add(row.key)
    if (threshold === null) badThresholds.add(row.key)
    if (price === null || threshold === null) continue
    formats.push({
      qalinlik_mm: row.qalinlik,
      ...(row.size ? { uzunlik_mm: row.size.uzunlik_mm, eni_mm: row.size.eni_mm } : {}),
      ...(row.kromkaEni !== null ? { kromka_eni_mm: row.kromkaEni } : {}),
      price_tiyin: price,
      min_stock: threshold,
    })
  }
  priceErrorKeys.value = badPrices
  thresholdErrorKeys.value = badThresholds
  if (badPrices.size > 0 || badThresholds.size > 0) {
    // Name the field that actually failed — over a dozen rows, "something is
    // wrong" leaves the operator hunting.
    saveError.value =
      badPrices.size > 0 ? t('catalog.form.priceInvalid') : t('inventory.attach.thresholdInvalid')
    return
  }
  saving.value = true
  try {
    const result = await workshop.attachBranchMaterials(props.branchId, {
      dekor_id: dekor.id,
      formats,
    })
    emit('attached', { created: result.created.length, skipped: result.skipped.length })
  } catch (caught) {
    saveError.value = apiMessage(caught) ?? t('inventory.attach.saveFailed')
    saveTraceId.value = apiTraceId(caught)
  } finally {
    saving.value = false
  }
}

function reset() {
  step.value = 1
  search.value = ''
  manufacturerFilter.value = 'all'
  turFilter.value = 'all'
  selectedDekor.value = null
  loadError.value = false
  resetFormatPicks()
}

let searchTimer: number | undefined
watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void loadOptions(), SEARCH_DEBOUNCE_MS)
})
watch([manufacturerFilter, turFilter], () => void loadOptions())

watch(
  () => bulkFill.price,
  (value) => {
    const clean = sanitizeMoneyInput(value)
    if (clean !== value) bulkFill.price = clean
  },
)
watch(
  () => bulkFill.threshold,
  (value) => {
    const clean = sanitizeQuantityInput(value)
    if (clean !== value) bulkFill.threshold = clean
  },
)

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    reset()
    await Promise.all([
      loadOptions(),
      workshop.loadCatalogFilters(props.branchId).catch(() => undefined),
    ])
  },
  { immediate: true },
)
</script>

<template>
  <AppModal
    :open="open"
    :title="
      step === 1 ? $t('inventory.attach.stepPickTitle') : $t('inventory.attach.stepPriceTitle')
    "
    max-width="max-w-4xl"
    @close="emit('close')"
  >
    <!-- Step 1 — pick the dekor. Photo-first: an operator recognises a decor by
         its surface long before its code. -->
    <div v-if="step === 1" class="grid gap-3">
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label class="field">
          <span>{{ $t('inventory.attach.searchLabel') }}</span>
          <input
            v-model="search"
            class="mp-input"
            :placeholder="$t('inventory.attach.searchPlaceholder')"
          />
        </label>
        <FormSelect
          v-model="turFilter"
          :label="$t('inventory.attach.turLabel')"
          :options="turOptions"
        />
        <FormSelect
          v-model="manufacturerFilter"
          :label="$t('inventory.attach.manufacturerLabel')"
          :options="manufacturerOptions"
        />
      </div>

      <div v-if="loading" class="grid gap-3 p-2" aria-live="polite">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
      <div v-else-if="loadError" class="st-error">
        <h3>{{ $t('inventory.attach.loadErrorTitle') }}</h3>
        <p>{{ $t('inventory.attach.loadErrorBody') }}</p>
      </div>
      <div v-else-if="options.length === 0" class="st-empty !py-8">
        <h3>{{ $t('inventory.attach.emptyTitle') }}</h3>
        <p>{{ $t('inventory.attach.emptyBody') }}</p>
      </div>
      <template v-else>
        <ul class="grid max-h-[44dvh] gap-2 overflow-y-auto overflow-x-hidden sm:grid-cols-2">
          <li v-for="option in options" :key="option.dekor.id" class="min-w-0">
            <button
              type="button"
              class="flex w-full min-w-0 items-center gap-3 rounded-md border px-3 py-2 text-left transition-colors"
              :class="
                selectedDekor?.id === option.dekor.id
                  ? 'border-accent bg-accent-soft'
                  : 'border-hairline bg-elevated hover:border-accent'
              "
              :aria-pressed="selectedDekor?.id === option.dekor.id"
              @click="selectDekor(option.dekor)"
            >
              <AuthFileImage
                v-if="option.dekor.image_file_id"
                :file-id="option.dekor.image_file_id"
                :alt="option.dekor.label"
                class="size-[34px] shrink-0 rounded-md object-cover"
              />
              <span v-else class="sw" :class="materialSwatchClass(swatchSource(option.dekor))" />
              <span class="grid min-w-0 flex-1 gap-0.5">
                <span class="break-words text-sm font-bold text-ink">{{ option.dekor.label }}</span>
                <small class="break-words text-ink-muted">
                  {{ option.dekor.manufacturer_name }} · {{ dekorTurLabel(option.dekor.tur) }}
                </small>
              </span>
              <!-- Carried dekorlar stay in the list: carrying 18 mm does not stop
                   you adding 16 mm. The count says how many formats are already in. -->
              <span v-if="option.carried_format_count > 0" class="mp-chip shrink-0">
                {{ $t('inventory.attach.carriedCount', { n: option.carried_format_count }) }}
              </span>
            </button>
          </li>
        </ul>
        <div v-if="options.length < total" class="flex justify-center">
          <button
            type="button"
            class="mp-button mp-button-outline"
            :disabled="loadingMore"
            @click="loadMoreOptions"
          >
            {{ loadingMore ? $t('catalog.action.loadingMore') : $t('catalog.action.loadMore') }}
          </button>
        </div>
      </template>

      <div class="flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
        <button
          type="button"
          class="mp-button mp-button-primary"
          :disabled="!selectedDekor"
          @click="step = 2"
        >
          {{ $t('inventory.attach.continue') }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="emit('close')">
          {{ $t('inventory.action.cancel') }}
        </button>
      </div>
    </div>

    <!-- Step 2 — pick the formats, then price them (both optional). -->
    <div v-else class="grid gap-3">
      <div
        v-if="selectedDekor"
        class="flex min-w-0 items-center gap-3 rounded-md border border-hairline bg-sunk px-3 py-2"
      >
        <AuthFileImage
          v-if="selectedDekor.image_file_id"
          :file-id="selectedDekor.image_file_id"
          :alt="selectedDekor.label"
          class="size-[34px] shrink-0 rounded-md object-cover"
        />
        <span v-else class="sw" :class="materialSwatchClass(swatchSource(selectedDekor))" />
        <span class="grid min-w-0 gap-0.5">
          <span class="break-words text-sm font-bold text-ink">{{ selectedDekor.label }}</span>
          <small class="text-ink-muted">
            {{ selectedDekor.manufacturer_name }} · {{ dekorTurLabel(selectedDekor.tur) }}
          </small>
        </span>
      </div>

      <fieldset class="grid gap-2">
        <legend class="text-sm font-bold text-ink">
          {{ $t('inventory.attach.standardThickness') }}
        </legend>
        <div class="flex flex-wrap items-center gap-2">
          <button
            v-for="value in standard.qalinliklar"
            :key="`std-q-${value}`"
            type="button"
            class="inline-flex min-h-10 items-center rounded-full border px-4 text-sm font-extrabold transition-colors"
            :class="
              pickedQalinliklar.includes(value)
                ? 'border-accent bg-accent-soft text-accent'
                : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
            "
            :aria-pressed="pickedQalinliklar.includes(value)"
            @click="toggleQalinlik(value)"
          >
            {{ value }} mm
          </button>
          <button
            type="button"
            class="inline-flex min-h-10 items-center rounded-full border border-dashed border-hairline-strong px-4 text-sm font-extrabold text-ink-soft transition-colors hover:border-accent hover:text-accent"
            :aria-expanded="customOpen === 'thickness'"
            @click="openCustom('thickness')"
          >
            {{ $t('inventory.attach.addCustom') }}
          </button>
        </div>

        <!-- "Nostandart · faqat sizda": this branch's own thicknesses, kept
             visually apart so a standard set never silently grows. -->
        <template v-if="customFacets.qalinliklar.length > 0">
          <span class="text-xs font-bold text-ink-muted">
            {{ $t('inventory.attach.customGroup') }}
          </span>
          <div class="flex flex-wrap items-center gap-2">
            <button
              v-for="value in customFacets.qalinliklar"
              :key="`own-q-${value}`"
              type="button"
              class="inline-flex min-h-10 items-center rounded-full border border-dashed px-4 text-sm font-extrabold transition-colors"
              :class="
                pickedQalinliklar.includes(value)
                  ? 'border-accent bg-accent-soft text-accent'
                  : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
              "
              :aria-pressed="pickedQalinliklar.includes(value)"
              @click="toggleQalinlik(value)"
            >
              {{ value }} mm
            </button>
          </div>
        </template>

        <p v-if="!hasAnyThickness" class="text-xs text-ink-muted">
          {{ $t('inventory.attach.noStandardFormats') }}
        </p>

        <div
          v-if="customOpen === 'thickness'"
          class="flex flex-wrap items-end gap-2 rounded-md border border-hairline bg-sunk px-3 py-2"
        >
          <label class="grid min-w-0 flex-1 basis-40 gap-1">
            <span class="text-xs font-bold text-ink-muted">
              {{ $t('inventory.attach.customThicknessLabel') }}
            </span>
            <input v-model="customDraft.thickness" class="mp-input" inputmode="decimal" />
          </label>
          <button type="button" class="mp-button mp-button-outline" @click="addCustomThickness">
            {{ $t('inventory.action.add') }}
          </button>
          <small v-if="customError" class="mp-field-error basis-full">{{ customError }}</small>
        </div>
      </fieldset>

      <fieldset class="grid gap-2">
        <legend class="text-sm font-bold text-ink">
          {{
            tape ? $t('inventory.attach.standardTapeWidth') : $t('inventory.attach.standardSize')
          }}
        </legend>
        <div class="flex flex-wrap items-center gap-2">
          <template v-if="tape">
            <button
              v-for="value in standard.kromkaEnlar"
              :key="`std-w-${value}`"
              type="button"
              class="inline-flex min-h-10 items-center rounded-full border px-4 text-sm font-extrabold transition-colors"
              :class="
                pickedTapeWidths.includes(value)
                  ? 'border-accent bg-accent-soft text-accent'
                  : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
              "
              :aria-pressed="pickedTapeWidths.includes(value)"
              @click="toggleTapeWidth(value)"
            >
              {{ value }} mm
            </button>
          </template>
          <template v-else>
            <button
              v-for="size in standard.olchamlar"
              :key="`std-s-${sizeKey(size)}`"
              type="button"
              class="inline-flex min-h-10 items-center rounded-full border px-4 text-sm font-extrabold transition-colors"
              :class="
                pickedSizeKeys.includes(sizeKey(size))
                  ? 'border-accent bg-accent-soft text-accent'
                  : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
              "
              :aria-pressed="pickedSizeKeys.includes(sizeKey(size))"
              @click="toggleSize(sizeKey(size))"
            >
              {{ size.uzunlik_mm }}×{{ size.eni_mm }}
            </button>
          </template>
          <button
            type="button"
            class="inline-flex min-h-10 items-center rounded-full border border-dashed border-hairline-strong px-4 text-sm font-extrabold text-ink-soft transition-colors hover:border-accent hover:text-accent"
            :aria-expanded="customOpen === (tape ? 'tape' : 'size')"
            @click="openCustom(tape ? 'tape' : 'size')"
          >
            {{ $t('inventory.attach.addCustom') }}
          </button>
        </div>

        <template
          v-if="tape ? customFacets.kromkaEnlar.length > 0 : customFacets.olchamlar.length > 0"
        >
          <span class="text-xs font-bold text-ink-muted">
            {{ $t('inventory.attach.customGroup') }}
          </span>
          <div class="flex flex-wrap items-center gap-2">
            <template v-if="tape">
              <button
                v-for="value in customFacets.kromkaEnlar"
                :key="`own-w-${value}`"
                type="button"
                class="inline-flex min-h-10 items-center rounded-full border border-dashed px-4 text-sm font-extrabold transition-colors"
                :class="
                  pickedTapeWidths.includes(value)
                    ? 'border-accent bg-accent-soft text-accent'
                    : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
                "
                :aria-pressed="pickedTapeWidths.includes(value)"
                @click="toggleTapeWidth(value)"
              >
                {{ value }} mm
              </button>
            </template>
            <template v-else>
              <button
                v-for="size in customFacets.olchamlar"
                :key="`own-s-${sizeKey(size)}`"
                type="button"
                class="inline-flex min-h-10 items-center rounded-full border border-dashed px-4 text-sm font-extrabold transition-colors"
                :class="
                  pickedSizeKeys.includes(sizeKey(size))
                    ? 'border-accent bg-accent-soft text-accent'
                    : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
                "
                :aria-pressed="pickedSizeKeys.includes(sizeKey(size))"
                @click="toggleSize(sizeKey(size))"
              >
                {{ size.uzunlik_mm }}×{{ size.eni_mm }}
              </button>
            </template>
          </div>
        </template>

        <p v-if="!hasAnySize" class="text-xs text-ink-muted">
          {{ $t('inventory.attach.noStandardFormats') }}
        </p>

        <div
          v-if="customOpen === 'size'"
          class="flex flex-wrap items-end gap-2 rounded-md border border-hairline bg-sunk px-3 py-2"
        >
          <label class="grid min-w-0 flex-1 basis-32 gap-1">
            <span class="text-xs font-bold text-ink-muted">
              {{ $t('inventory.attach.customLengthLabel') }}
            </span>
            <input v-model="customDraft.length" class="mp-input" inputmode="numeric" />
          </label>
          <label class="grid min-w-0 flex-1 basis-32 gap-1">
            <span class="text-xs font-bold text-ink-muted">
              {{ $t('inventory.attach.customWidthLabel') }}
            </span>
            <input v-model="customDraft.width" class="mp-input" inputmode="numeric" />
          </label>
          <button type="button" class="mp-button mp-button-outline" @click="addCustomSize">
            {{ $t('inventory.action.add') }}
          </button>
          <small v-if="customError" class="mp-field-error basis-full">{{ customError }}</small>
        </div>

        <div
          v-if="customOpen === 'tape'"
          class="flex flex-wrap items-end gap-2 rounded-md border border-hairline bg-sunk px-3 py-2"
        >
          <label class="grid min-w-0 flex-1 basis-40 gap-1">
            <span class="text-xs font-bold text-ink-muted">
              {{ $t('inventory.attach.customTapeWidthLabel') }}
            </span>
            <input v-model="customDraft.tape" class="mp-input" inputmode="numeric" />
          </label>
          <button type="button" class="mp-button mp-button-outline" @click="addCustomTapeWidth">
            {{ $t('inventory.action.add') }}
          </button>
          <small v-if="customError" class="mp-field-error basis-full">{{ customError }}</small>
        </div>
      </fieldset>

      <div v-if="combinations.length === 0" class="st-empty !py-6">
        <p>{{ $t('inventory.attach.selectFormats') }}</p>
      </div>

      <template v-else>
        <div class="grid gap-2 rounded-md border border-hairline bg-sunk px-3 py-3">
          <div class="flex flex-wrap items-end gap-2">
            <span class="self-center text-sm font-bold text-ink">
              {{ $t('inventory.attach.bulkAll') }}
            </span>
            <label class="grid min-w-0 flex-1 basis-40 gap-1">
              <span class="text-xs font-bold text-ink-muted">
                {{ $t('inventory.attach.priceLabel') }}
              </span>
              <input v-model="bulkFill.price" class="mp-input" inputmode="numeric" />
            </label>
            <label class="grid min-w-0 flex-1 basis-32 gap-1">
              <span class="text-xs font-bold text-ink-muted">{{ lowStockThresholdColumn() }}</span>
              <input v-model="bulkFill.threshold" class="mp-input" inputmode="decimal" />
            </label>
            <button
              type="button"
              class="mp-button mp-button-outline"
              :disabled="!bulkFill.price.trim() && !bulkFill.threshold.trim()"
              @click="applyBulkFill"
            >
              {{ $t('inventory.attach.apply') }}
            </button>
          </div>
          <small class="text-ink-muted">{{ $t('inventory.attach.bulkHint') }}</small>
        </div>

        <div class="table-wrap">
          <table class="tbl tbl-fluid">
            <thead>
              <tr>
                <th class="w-full">{{ $t('inventory.attach.columnFormat') }}</th>
                <th class="nowrap right">{{ $t('inventory.attach.columnPrice') }}</th>
                <th class="nowrap right">{{ lowStockThresholdColumn() }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in combinations" :key="row.key">
                <td>
                  <div class="grid min-w-0 gap-0.5">
                    <span class="break-words font-bold text-ink">{{ row.label }}</span>
                    <!-- Already carried: shown, not hidden, so the cross product
                         the operator picked stays legible. -->
                    <small v-if="row.carried" class="text-ink-muted">
                      {{ $t('inventory.attach.alreadyCarried') }}
                    </small>
                  </div>
                </td>
                <td class="nowrap right">
                  <input
                    class="mp-input w-28 text-right"
                    inputmode="numeric"
                    :disabled="row.carried"
                    :value="row.carried ? '' : priceOf(row.key)"
                    :aria-label="$t('inventory.attach.priceAria', { name: row.label })"
                    :aria-invalid="priceErrorKeys.has(row.key) || undefined"
                    :class="priceErrorKeys.has(row.key) ? '!border-danger' : ''"
                    @input="setPrice(row.key, ($event.target as HTMLInputElement).value)"
                  />
                  <small class="block text-ink-muted">{{ priceUnit() }}</small>
                </td>
                <td class="nowrap right">
                  <input
                    class="mp-input w-20 text-right"
                    inputmode="decimal"
                    :disabled="row.carried"
                    :value="row.carried ? '' : thresholdOf(row.key)"
                    :aria-label="$t('inventory.attach.thresholdAria', { name: row.label })"
                    :aria-invalid="thresholdErrorKeys.has(row.key) || undefined"
                    :class="thresholdErrorKeys.has(row.key) ? '!border-danger' : ''"
                    @input="setThreshold(row.key, ($event.target as HTMLInputElement).value)"
                  />
                  <small class="block text-ink-muted">{{ thresholdUnit(tur) }}</small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p class="text-xs text-ink-muted">{{ $t('inventory.attach.priceOptional') }}</p>
        <p class="text-xs text-ink-muted">
          {{ lowStockThresholdLabel() }} — {{ lowStockThresholdHint() }}
        </p>
      </template>

      <p v-if="saveError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
        {{ saveError }}<template v-if="saveTraceId"> · trace_id: {{ saveTraceId }}</template>
      </p>

      <div class="flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
        <button
          type="button"
          class="mp-button mp-button-primary"
          :disabled="saving || pendingCombos.length === 0"
          @click="submit"
        >
          {{
            saving
              ? $t('inventory.attach.saving')
              : $t('inventory.attach.submit', { n: pendingCombos.length }, pendingCombos.length)
          }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="step = 1">
          {{ $t('inventory.attach.back') }}
        </button>
      </div>
    </div>
  </AppModal>
</template>
