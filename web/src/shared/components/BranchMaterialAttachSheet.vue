<script setup lang="ts">
/**
 * "+ Material" — have this branch carry platform formats.
 *
 * Two steps, because the platform owns the product and the branch owns only the
 * decision to sell it: step 1 picks the *decors* (a pattern — manufacturer,
 * code, name, photo), step 2 picks which of that decor's **formats** the branch
 * carries. A decor already carried is never hidden: carrying 18 mm does not stop
 * you adding 16 mm, so it stays in the list with its carried count.
 *
 * Step 1 is multi-select, and that is the point. Most carried decors exist in
 * exactly one format, so the multiplication that matters is MANY DECORS × ONE
 * FORMAT: a branch registering its supplier list ticks thirty boards and one
 * sheet size. "Filtrdagi hammasi (N)" therefore covers the whole filter, paging
 * past the loaded page server-side rather than lying about the page it can see.
 *
 * **The branch cannot invent a format.** The old "Nostandart · faqat sizda"
 * group and its "+ qo'shish" are gone with the reshape: a format is the
 * manufacturer's fact, entered once by the platform so the same physical product
 * carries one id in every workshop. A branch that needs a size nobody has
 * entered is told so on screen (`inventory.attach.missingFormat`) and asks —
 * that wait is the accepted cost of the curated list, so it is made visible
 * rather than hidden behind a control that would silently fork the catalog.
 *
 * Price and threshold are optional and default to 0: a branch routinely
 * registers its whole list before it knows prices.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { apiTraceId, ApiError } from '@/shared/api/client'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { sanitizeMoneyInput, sanitizeQuantityInput } from '@/shared/app/inputSanitizers'
import {
  defaultLowStockThreshold,
  thresholdUnit,
  lowStockThresholdColumn,
  lowStockThresholdHint,
  lowStockThresholdLabel,
} from '@/shared/app/lowStockThreshold'
import { DECOR_TYPES, decorTypeLabel, isTape } from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import AppModal from '@/shared/components/AppModal.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import FormSelect from '@/shared/components/FormSelect.vue'
import { parseDisplayQuantity, parseSomToTiyin } from '@/shared/formatters'
import type { Decor, DecorType } from '@/shared/stores/admin'
import {
  useWorkshopStore,
  type BranchCatalogFormatOption,
  type BranchCatalogOption,
  type BranchMaterialAttachItem,
} from '@/shared/stores/workshop'

const props = defineProps<{ open: boolean; branchId: string }>()
const emit = defineEmits<{
  close: []
  // Both halves travel: a duplicate o'lcham is *skipped* server-side, never an
  // error, so the caller has to be able to say "3 added, 1 already there".
  attached: [result: { created: number; skipped: number }]
}>()

// Server-side page size for the decor picker. "Filtrdagi hammasi" pages past it
// using the endpoint's `total`, so this bounds the DOM, not the selection.
const PAGE_LIMIT = 100

const { t } = useI18n()
const workshop = useWorkshopStore()

const step = ref<1 | 2>(1)
const search = ref('')
const manufacturerFilter = ref<string | null>('all')
const turFilter = ref<string | null>('all')
const options = ref<BranchCatalogOption[]>([])
const total = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const loadError = ref(false)
const selectAllPending = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveTraceId = ref<string | null>(null)

// Decor ids matching the current filter. Until "Filtrdagi hammasi" pages through
// the rest, only the loaded page is known — `filterComplete` says which it is, so
// the master checkbox never claims to cover rows nobody has fetched.
const filterIds = ref<string[]>([])
const filterComplete = ref(false)

// Keyed by decor id so the selection survives filter changes, paging, and the
// step-1 ⇄ step-2 round trip. Insertion order is the order rows are rendered in.
const selected = ref(new Map<string, Decor>())
const selectedDecors = computed(() => [...selected.value.values()])
const selectedCount = computed(() => selected.value.size)

// Step two's data: this branch's answer for each selected decor's ACTIVE
// formats. Fetched on entering step 2 rather than with the decor list — a
// hundred decors' formats is a payload nobody reads, and the selection is
// usually a handful.
const formatsByDecor = ref<Record<string, BranchCatalogFormatOption[]>>({})
const formatsLoading = ref(false)
const formatsError = ref(false)

// Format ids the operator has ticked. Carried ones are rendered disabled and can
// never enter this set.
const checked = ref<Set<string>>(new Set())

// Price / threshold text per FORMAT id. Read with a default rather than
// pre-seeded: a synced map would either mutate during render or lose what the
// operator already typed.
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
// Every `type` is offered, including `dsp` — it is a distinct wire value even
// though it shares the `LDSP` label, and dropping it would leave those decors
// unreachable by filter.
const turOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: t('inventory.attach.turAll') },
  ...DECOR_TYPES.map((value) => ({ value, label: decorTypeLabel(value) })),
])

// The master checkbox reflects the filter, not the page: it is checked once every
// decor matching the current filter sits in the selection. With more matches than
// one page holds, that is only knowable after the select-all pass has paged
// through them — before that the box stays unchecked rather than lying.
const filterFullySelected = computed(
  () =>
    total.value > 0 &&
    filterComplete.value &&
    filterIds.value.every((id) => selected.value.has(id)),
)

interface FormatRow {
  /** Row identity — the platform format's own id. */
  key: string
  decor: Decor
  type: DecorType
  format: BranchCatalogFormatOption['decor_format']
  label: string
  carried: boolean
}

/** One block per selected decor, its active formats under it. */
const groupedRows = computed<{ decor: Decor; rows: FormatRow[] }[]>(() =>
  selectedDecors.value.map((decor) => ({
    decor,
    rows: (formatsByDecor.value[decor.id] ?? []).map((option) => ({
      key: option.decor_format.id,
      decor,
      type: option.decor_format.type,
      format: option.decor_format,
      // The server composes the label from the same formatter the PDF and the
      // order history use, so step two reads exactly like the Zaxira row it
      // will become.
      label: option.decor_format.label,
      carried: option.carried,
    })),
  })),
)

const rows = computed<FormatRow[]>(() => groupedRows.value.flatMap((group) => group.rows))

/** The pricing table: only what the operator actually ticked. */
const pricedGroups = computed(() =>
  groupedRows.value
    .map((group) => ({
      decor: group.decor,
      rows: group.rows.filter((row) => !row.carried && checked.value.has(row.key)),
    }))
    .filter((group) => group.rows.length > 0),
)

/** Ticked, and not already on the shelf. */
const pendingRows = computed(() =>
  rows.value.filter((row) => !row.carried && checked.value.has(row.key)),
)

/** Every selected decor came back with nothing the branch could add. */
const noFormatsAtAll = computed(
  () => !formatsLoading.value && rows.value.length === 0 && selectedCount.value > 0,
)

function isChecked(key: string) {
  return checked.value.has(key)
}

function toggleFormat(row: FormatRow) {
  if (row.carried) return
  const next = new Set(checked.value)
  if (next.has(row.key)) next.delete(row.key)
  else next.add(row.key)
  checked.value = next
}

async function loadFormats() {
  formatsLoading.value = true
  formatsError.value = false
  try {
    const pairs = await Promise.all(
      selectedDecors.value.map(
        async (decor) =>
          [decor.id, await workshop.fetchCatalogFormats(props.branchId, decor.id)] as const,
      ),
    )
    formatsByDecor.value = Object.fromEntries(pairs)
  } catch {
    formatsError.value = true
    formatsByDecor.value = {}
  } finally {
    formatsLoading.value = false
  }
}

function swatchSource(decor: Decor) {
  return { id: decor.id, name: decor.name, code: decor.code }
}

// Follows the ROW's type, not one global flag: a batch can hold both a board
// priced per list and a kromka priced per metre.
function priceUnit(type: DecorType) {
  return isTape(type) ? t('inventory.attach.priceUnitMetre') : t('inventory.attach.priceUnitSheet')
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

function filters(offset = 0) {
  return {
    search: search.value,
    // On this surface `type` means "has at least one ACTIVE format of this
    // substrate" — a decor itself no longer has one.
    type: turFilter.value === 'all' ? null : (turFilter.value as DecorType),
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
    filterIds.value = page.items.map((option) => option.decor.id)
    filterComplete.value = page.items.length >= page.total
  } catch {
    loadError.value = true
    options.value = []
    total.value = 0
    filterIds.value = []
    filterComplete.value = false
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
    filterIds.value = options.value.map((option) => option.decor.id)
    filterComplete.value = options.value.length >= page.total
  } catch {
    loadError.value = true
  } finally {
    loadingMore.value = false
  }
}

function toggleDecor(decor: Decor) {
  const next = new Map(selected.value)
  if (next.has(decor.id)) next.delete(decor.id)
  else next.set(decor.id, decor)
  selected.value = next
}

/**
 * "Filtrdagi hammasi" must select every match, not just the loaded page — page
 * through the rest server-side before adding them all in one go.
 */
async function toggleSelectAllInFilter() {
  if (filterFullySelected.value) {
    const next = new Map(selected.value)
    // Unchecking removes exactly what checking added — the filter's whole set,
    // not just the page still on screen.
    for (const id of filterIds.value) next.delete(id)
    selected.value = next
    return
  }
  selectAllPending.value = true
  try {
    const collected: Decor[] = options.value.map((option) => option.decor)
    while (collected.length < total.value) {
      const page = await workshop.fetchCatalogOptions(props.branchId, filters(collected.length))
      if (page.items.length === 0) break
      collected.push(...page.items.map((option) => option.decor))
    }
    const next = new Map(selected.value)
    for (const decor of collected) if (!next.has(decor.id)) next.set(decor.id, decor)
    selected.value = next
    filterIds.value = collected.map((decor) => decor.id)
    filterComplete.value = true
  } catch {
    loadError.value = true
  } finally {
    selectAllPending.value = false
  }
}

function clearSelection() {
  selected.value = new Map()
}

function resetStepTwo() {
  formatsByDecor.value = {}
  formatsError.value = false
  checked.value = new Set()
  priceByKey.value = {}
  thresholdByKey.value = {}
  priceErrorKeys.value = new Set()
  thresholdErrorKeys.value = new Set()
  saveError.value = null
  saveTraceId.value = null
}

/** Step 1 → step 2. The formats are fetched here, for the selection only. */
async function goToFormats() {
  resetStepTwo()
  step.value = 2
  await loadFormats()
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

function parseThreshold(text: string, type: DecorType): number | null {
  const trimmed = text.trim()
  if (!trimmed) return 0
  const parsed = parseDisplayQuantity(trimmed, isTape(type) ? 'm' : 'pcs')
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
}

async function submit() {
  saveError.value = null
  saveTraceId.value = null
  if (pendingRows.value.length === 0) {
    saveError.value = t('inventory.attach.selectFormats')
    return
  }
  const badPrices = new Set<string>()
  const badThresholds = new Set<string>()
  const items: BranchMaterialAttachItem[] = []
  for (const row of pendingRows.value) {
    const price = parsePrice(priceOf(row.key))
    const threshold = parseThreshold(thresholdOf(row.key), row.type)
    if (price === null) badPrices.add(row.key)
    if (threshold === null) badThresholds.add(row.key)
    if (price === null || threshold === null) continue
    items.push({ decor_format_id: row.key, price_tiyin: price, min_stock: threshold })
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
    const result = await workshop.attachBranchMaterials(props.branchId, { items })
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
  selected.value = new Map()
  filterIds.value = []
  filterComplete.value = false
  selectAllPending.value = false
  loadError.value = false
  resetStepTwo()
}

let searchTimer: number | undefined
watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void loadOptions(), SEARCH_DEBOUNCE_MS)
})
watch([manufacturerFilter, turFilter], () => void loadOptions())

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
    <!-- Step 1 — pick the decors. Photo-first: an operator recognises a decor by
         its surface long before its code. Multi-select, because the job is many
         decors in one o'lcham. -->
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

      <div
        class="flex flex-wrap items-center justify-between gap-3 rounded-md border border-hairline bg-sunk px-3 py-2"
      >
        <label
          class="flex min-h-11 min-w-0 cursor-pointer items-center gap-2 text-sm font-bold text-ink"
        >
          <input
            type="checkbox"
            class="size-4 shrink-0 accent-accent"
            :checked="filterFullySelected"
            :disabled="total === 0 || selectAllPending"
            @change="toggleSelectAllInFilter"
          />
          <span class="min-w-0">
            {{
              selectAllPending
                ? $t('inventory.attach.selectAllPending')
                : $t('inventory.attach.selectAllInFilter', { count: total })
            }}
          </span>
        </label>
        <div class="flex flex-wrap items-center gap-3">
          <span class="text-sm font-bold text-ink-muted" aria-live="polite">
            {{ $t('inventory.attach.selectedCount', { n: selectedCount }, selectedCount) }}
          </span>
          <button
            v-if="selectedCount > 0"
            type="button"
            class="mp-button mp-button-outline"
            @click="clearSelection"
          >
            {{ $t('inventory.attach.clearSelection') }}
          </button>
        </div>
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
          <li v-for="option in options" :key="option.decor.id" class="min-w-0">
            <label
              class="flex w-full min-w-0 cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-left transition-colors"
              :class="
                selected.has(option.decor.id)
                  ? 'border-accent-tint bg-accent-soft'
                  : 'border-hairline bg-elevated hover:border-accent'
              "
            >
              <input
                type="checkbox"
                class="size-4 shrink-0 accent-accent"
                :checked="selected.has(option.decor.id)"
                @change="toggleDecor(option.decor)"
              />
              <AuthFileImage
                v-if="option.decor.image_file_id"
                :file-id="option.decor.image_file_id"
                :alt="option.decor.label"
                class="size-[34px] shrink-0 rounded-md object-cover"
              />
              <span v-else class="sw" :class="materialSwatchClass(swatchSource(option.decor))" />
              <span class="grid min-w-0 flex-1 gap-0.5">
                <span class="break-words text-sm font-bold text-ink">{{ option.decor.label }}</span>
                <small class="break-words text-ink-muted">
                  {{ option.decor.manufacturer_name }}
                </small>
              </span>
              <!-- Carried decors stay in the list: carrying 18 mm does not stop
                   you adding 16 mm. The count says how many are already in. -->
              <span v-if="option.carried_format_count > 0" class="mp-chip shrink-0">
                {{ $t('inventory.attach.carriedCount', { n: option.carried_format_count }) }}
              </span>
            </label>
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
          :disabled="selectedCount === 0"
          @click="goToFormats"
        >
          {{ $t('inventory.attach.continue') }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="emit('close')">
          {{ $t('inventory.action.cancel') }}
        </button>
      </div>
    </div>

    <!-- Step 2 — pick the o'lchamlar, then price them (both optional). One chip
         block per type in the selection; a board and its kromka have different axes. -->
    <div v-else class="grid gap-3">
      <p class="text-sm font-bold text-ink-muted">
        {{ $t('inventory.attach.selectedCount', { n: selectedCount }, selectedCount) }}
      </p>

      <p v-if="formatsLoading" class="text-sm text-ink-muted">
        {{ $t('inventory.attach.loading') }}
      </p>
      <div v-else-if="formatsError" class="st-empty !py-6">
        <p>{{ $t('inventory.attach.loadFailed') }}</p>
        <button type="button" class="mp-button mp-button-outline" @click="loadFormats">
          {{ $t('inventory.action.retry') }}
        </button>
      </div>

      <template v-else>
        <!-- One block per selected decor, listing the formats the PLATFORM has
             entered for it. Carried ones stay in the list, disabled: hiding them
             would leave the branch wondering whether the size exists at all,
             which is the exact question this step is here to answer. -->
        <div
          v-for="group in groupedRows"
          :key="`formats-${group.decor.id}`"
          class="grid gap-2 rounded-md border border-hairline px-3 py-3"
        >
          <div class="flex min-w-0 items-center gap-2">
            <AuthFileImage
              v-if="group.decor.image_file_id"
              :file-id="group.decor.image_file_id"
              :alt="group.decor.label"
              class="size-[28px] shrink-0 rounded-md object-cover"
            />
            <span
              v-else
              class="sw shrink-0"
              :class="materialSwatchClass(swatchSource(group.decor))"
            />
            <span class="min-w-0 break-words text-sm font-extrabold text-ink">
              {{ group.decor.label }}
            </span>
          </div>

          <p v-if="group.rows.length === 0" class="text-xs text-ink-muted">
            {{ $t('inventory.attach.noFormats') }}
          </p>

          <label
            v-for="row in group.rows"
            :key="row.key"
            class="flex min-w-0 cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-sunk"
            :class="row.carried ? 'cursor-default opacity-60' : ''"
          >
            <input
              type="checkbox"
              class="mp-checkbox shrink-0"
              :checked="isChecked(row.key)"
              :disabled="row.carried"
              @change="toggleFormat(row)"
            />
            <span class="min-w-0 flex-1 break-words text-sm text-ink">{{ row.label }}</span>
            <span v-if="row.carried" class="mp-chip shrink-0">
              {{ $t('inventory.attach.carried') }}
            </span>
          </label>
        </div>

        <!-- The promised visibility of the wait: a branch cannot add a format
             itself any more, so the screen has to say who can. -->
        <p class="text-xs text-ink-muted">{{ $t('inventory.attach.missingFormat') }}</p>
        <p v-if="noFormatsAtAll" class="text-xs text-ink-muted">
          {{ $t('inventory.attach.noFormats') }}
        </p>
      </template>

      <template v-if="pendingRows.length > 0">
        <div class="table-wrap">
          <table class="tbl tbl-fluid">
            <thead>
              <tr>
                <!-- The decor name is the longest string in the table and `auto`
                     layout would otherwise starve it down to one word per line
                     while the o'lcham column keeps slack it has no use for. -->
                <th class="min-w-[190px]">{{ $t('inventory.attach.columnDekor') }}</th>
                <th class="w-full">{{ $t('inventory.attach.columnFormat') }}</th>
                <th class="nowrap right">{{ $t('inventory.attach.columnPrice') }}</th>
                <th class="nowrap right">{{ lowStockThresholdColumn() }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="group in pricedGroups" :key="group.decor.id">
                <tr v-for="(row, index) in group.rows" :key="row.key">
                  <!-- One identity cell per decor, spanning its o'lchamlar: with
                       many decors the o'lcham label alone is ambiguous, and
                       repeating the name on every row buries the o'lchamlar. -->
                  <td v-if="index === 0" :rowspan="group.rows.length" class="align-top">
                    <div class="flex min-w-0 items-center gap-2">
                      <AuthFileImage
                        v-if="group.decor.image_file_id"
                        :file-id="group.decor.image_file_id"
                        :alt="group.decor.label"
                        class="size-[28px] shrink-0 rounded-md object-cover"
                      />
                      <span
                        v-else
                        class="sw shrink-0"
                        :class="materialSwatchClass(swatchSource(group.decor))"
                      />
                      <div class="grid min-w-0 gap-0.5">
                        <span class="break-words font-bold text-ink">{{ group.decor.label }}</span>
                        <small class="break-words text-ink-muted">
                          {{ group.decor.manufacturer_name }}
                        </small>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="grid min-w-0 gap-0.5">
                      <span class="break-words font-bold text-ink">{{ row.label }}</span>
                    </div>
                  </td>
                  <td class="nowrap right">
                    <input
                      class="mp-input w-28 text-right"
                      inputmode="numeric"
                      :value="priceOf(row.key)"
                      :aria-label="
                        $t('inventory.attach.priceAria', {
                          name: `${group.decor.label} · ${row.label}`,
                        })
                      "
                      :aria-invalid="priceErrorKeys.has(row.key) || undefined"
                      :class="priceErrorKeys.has(row.key) ? '!border-danger' : ''"
                      @input="setPrice(row.key, ($event.target as HTMLInputElement).value)"
                    />
                    <small class="block text-ink-muted">{{ priceUnit(row.type) }}</small>
                  </td>
                  <td class="nowrap right">
                    <input
                      class="mp-input w-20 text-right"
                      inputmode="decimal"
                      :value="thresholdOf(row.key)"
                      :aria-label="
                        $t('inventory.attach.thresholdAria', {
                          name: `${group.decor.label} · ${row.label}`,
                        })
                      "
                      :aria-invalid="thresholdErrorKeys.has(row.key) || undefined"
                      :class="thresholdErrorKeys.has(row.key) ? '!border-danger' : ''"
                      @input="setThreshold(row.key, ($event.target as HTMLInputElement).value)"
                    />
                    <small class="block text-ink-muted">{{ thresholdUnit(row.type) }}</small>
                  </td>
                </tr>
              </template>
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
          :disabled="saving || pendingRows.length === 0"
          @click="submit"
        >
          {{
            saving
              ? $t('inventory.attach.saving')
              : $t('inventory.attach.submit', { n: pendingRows.length }, pendingRows.length)
          }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="step = 1">
          {{ $t('inventory.attach.back') }}
        </button>
      </div>
    </div>
  </AppModal>
</template>
