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
 * Step 2 carries the other half of that: the o'lchamlar the selection shares
 * become **quick-pick chips** («LDSP · 2800×2070×18 mm (30)»), so thirty boards
 * in one size is one tick rather than thirty, and «Hammasi (N)» ticks the lot.
 *
 * **Step 1 shows the o'lchamlar too.** A decor row opens to the platform's
 * formats for it, each marked carried or not — the question "do I stock this
 * decor" is answered by the sizes behind it, and answering it used to cost a
 * round trip into step 2 and back. The rows are a preview, not a second place to
 * tick: what is carried is read there, what to add is chosen (and priced) one
 * step on, so there is never a tick in two places meaning two different things.
 *
 * The one-decor case is shorter still: a single decor with a single addable
 * format arrives in step 2 already ticked — there is nothing to choose, only
 * a price to type if the operator has one. The pre-tick is deliberately NOT
 * extended to multi-decor selections: a wrongly attached row can only be
 * deactivated, never deleted, so a batch is something the operator confirms
 * row by row (or chip by chip), not something the sheet guesses.
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
import {
  DECOR_TYPES,
  decorTypeLabel,
  finishedSidesNote,
  formatDimensionsLabel,
  isTape,
} from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import AppIcon from '@/shared/components/AppIcon.vue'
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

// Step 1's open decor rows, and the per-row state of their preview fetch. Kept
// per decor rather than as one flag: several rows can be open at once, and one
// that failed must be retryable without closing the others.
const expanded = ref<Set<string>>(new Set())
const previewLoading = ref<Set<string>>(new Set())
const previewFailed = ref<Set<string>>(new Set())

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
    filterComplete.value &&
    filterIds.value.length > 0 &&
    filterIds.value.every((id) => selected.value.has(id)),
)

/**
 * A decor with nothing left to add is **not tickable** — its checkbox is gone,
 * not merely unchecked.
 *
 * Ticking one used to be allowed and led somewhere useless: step two full of
 * disabled rows, «0 ta o'lchamni qo'shish» refusing to save, and no explanation
 * on either screen. The row itself stays — it is how the operator confirms the
 * decor IS carried, and its o'lchamlar still open — but the one thing it cannot
 * do any more is enter a batch it can contribute nothing to.
 */
function canAttach(option: BranchCatalogOption) {
  return option.carried_format_count < option.available_format_count
}

/** Loaded rows that still have something to add — what select-all may collect. */
const attachableOptions = computed(() => options.value.filter(canAttach))

/** Everything in the filter is carried, and the filter is fully known. */
const nothingLeftToAdd = computed(
  () => options.value.length > 0 && filterComplete.value && attachableOptions.value.length === 0,
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

/** Everything the branch could still add from this selection. */
const addableRows = computed(() => rows.value.filter((row) => !row.carried))

interface QuickPick {
  /** The o'lcham identity — every format field except the decor. */
  key: string
  label: string
  rowKeys: string[]
  allChecked: boolean
}

/**
 * The o'lchamlar the selection has in common, one chip each, most shared first.
 * Thirty decors × one sheet size is the registering-a-price-list case, and it
 * is one chip here. Only shown once there is something to gather: a selection
 * with a single addable row has nothing a chip could say that the row doesn't.
 */
const quickPicks = computed<QuickPick[]>(() => {
  if (addableRows.value.length < 2) return []
  const groups = new Map<string, { label: string; rowKeys: string[] }>()
  for (const row of addableRows.value) {
    const f = row.format
    const key = [f.type, f.thickness_mm, f.length_mm, f.width_mm, f.tape_width_mm, f.finished_sides]
      .map((part) => String(part ?? ''))
      .join('|')
    let group = groups.get(key)
    if (!group) {
      const sides = finishedSidesNote(f.finished_sides)
      const label = [decorTypeLabel(f.type), formatDimensionsLabel(f), sides]
        .filter(Boolean)
        .join(' · ')
      group = { label, rowKeys: [] }
      groups.set(key, group)
    }
    group.rowKeys.push(row.key)
  }
  return [...groups.entries()]
    .map(([key, group]) => ({
      key,
      label: group.label,
      rowKeys: group.rowKeys,
      allChecked: group.rowKeys.every((rowKey) => checked.value.has(rowKey)),
    }))
    .sort((a, b) => b.rowKeys.length - a.rowKeys.length || a.label.localeCompare(b.label))
})

const allAddableChecked = computed(
  () =>
    addableRows.value.length > 0 && addableRows.value.every((row) => checked.value.has(row.key)),
)

/** A chip ticks every row of its o'lcham; a second press unticks exactly those. */
function toggleQuickPick(pick: QuickPick) {
  const next = new Set(checked.value)
  if (pick.allChecked) for (const key of pick.rowKeys) next.delete(key)
  else for (const key of pick.rowKeys) next.add(key)
  checked.value = next
}

function toggleAllAddable() {
  checked.value = allAddableChecked.value
    ? new Set()
    : new Set(addableRows.value.map((row) => row.key))
}

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

function withId(set: Set<string>, id: string, present: boolean) {
  const next = new Set(set)
  if (present) next.add(id)
  else next.delete(id)
  return next
}

/** One decor's active formats, fetched once and reused by both steps. */
async function ensureFormats(decorId: string) {
  if (formatsByDecor.value[decorId] || previewLoading.value.has(decorId)) return
  previewLoading.value = withId(previewLoading.value, decorId, true)
  previewFailed.value = withId(previewFailed.value, decorId, false)
  try {
    const rows = await workshop.fetchCatalogFormats(props.branchId, decorId)
    formatsByDecor.value = { ...formatsByDecor.value, [decorId]: rows }
  } catch {
    previewFailed.value = withId(previewFailed.value, decorId, true)
  } finally {
    previewLoading.value = withId(previewLoading.value, decorId, false)
  }
}

/** Open (or close) one decor's o'lcham list in step 1. */
function toggleFormatPreview(decor: Decor) {
  const open = !expanded.value.has(decor.id)
  expanded.value = withId(expanded.value, decor.id, open)
  if (open) void ensureFormats(decor.id)
}

/** The preview's rows: the o'lcham alone — the decor name is the heading above. */
function previewRows(decorId: string) {
  return (formatsByDecor.value[decorId] ?? []).map((option) => ({
    key: option.decor_format.id,
    label: shortFormatLabel(option.decor_format),
    carried: option.carried,
  }))
}

/** `LDSP · 2800×2070×18 mm · 2 tomonlama` — identity-free, for use under a decor. */
function shortFormatLabel(format: BranchCatalogFormatOption['decor_format']) {
  return [
    decorTypeLabel(format.type),
    formatDimensionsLabel(format),
    finishedSidesNote(format.finished_sides),
  ]
    .filter(Boolean)
    .join(' · ')
}

/**
 * The count chip, which is also the disclosure control: `3 o'lcham` when none is
 * carried, `2/3 o'lcham bor` while some are, `Hammasi bor` when nothing is left
 * to add. One control, because "how many are in?" and "which ones?" are the same
 * question asked at two depths.
 */
function formatCountChip(option: BranchCatalogOption) {
  if (option.carried_format_count === 0) {
    return t('catalog.meta.formatCount', { n: option.available_format_count })
  }
  return option.carried_format_count >= option.available_format_count
    ? t('inventory.attach.carriedAll')
    : t('inventory.attach.carriedCount', {
        n: option.carried_format_count,
        total: option.available_format_count,
      })
}

async function loadFormats() {
  formatsLoading.value = true
  formatsError.value = false
  try {
    // Only what step 1 has not already fetched: a previewed decor carries its
    // formats into step 2 rather than being asked for twice.
    const missing = selectedDecors.value.filter((decor) => !formatsByDecor.value[decor.id])
    const pairs = await Promise.all(
      missing.map(
        async (decor) =>
          [decor.id, await workshop.fetchCatalogFormats(props.branchId, decor.id)] as const,
      ),
    )
    if (pairs.length > 0) {
      formatsByDecor.value = { ...formatsByDecor.value, ...Object.fromEntries(pairs) }
    }
    // One decor, one addable o'lcham: nothing to choose, so it arrives ticked.
    // See the header for why this stops at one decor.
    if (selectedDecors.value.length === 1 && addableRows.value.length === 1) {
      checked.value = new Set([addableRows.value[0].key])
    }
  } catch {
    formatsError.value = true
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
    filterIds.value = page.items.filter(canAttach).map((option) => option.decor.id)
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
    filterIds.value = attachableOptions.value.map((option) => option.decor.id)
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
    // Paging is counted in ROWS (the offset the server pages by), while only the
    // attachable ones are collected — a filter of carried decors must still walk
    // to its end rather than looping on an offset that stops advancing.
    let seen = options.value.length
    const collected: Decor[] = attachableOptions.value.map((option) => option.decor)
    while (seen < total.value) {
      const page = await workshop.fetchCatalogOptions(props.branchId, filters(seen))
      if (page.items.length === 0) break
      seen += page.items.length
      collected.push(...page.items.filter(canAttach).map((option) => option.decor))
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
  // The fetched formats are NOT dropped: they are step 1's preview data too, and
  // a step-2 → back → step-2 round trip should not refetch what is on screen.
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
  // A reopened sheet may be pointed at another branch, where `carried` differs.
  formatsByDecor.value = {}
  expanded.value = new Set()
  previewLoading.value = new Set()
  previewFailed.value = new Set()
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
            :disabled="total === 0 || selectAllPending || nothingLeftToAdd"
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
            <div
              class="min-w-0 rounded-md border transition-colors"
              :class="
                selected.has(option.decor.id)
                  ? 'border-accent-tint bg-accent-soft'
                  : 'border-hairline bg-elevated'
              "
            >
              <div class="flex min-w-0 items-center gap-3 px-3 py-2">
                <!-- A `label` only while there is a control to label: a decor
                     with nothing left to add has no checkbox, and a pointer
                     cursor over a row that cannot be picked is a lie. -->
                <component
                  :is="canAttach(option) ? 'label' : 'div'"
                  class="flex min-w-0 flex-1 items-center gap-3 text-left"
                  :class="canAttach(option) ? 'cursor-pointer' : ''"
                >
                  <input
                    v-if="canAttach(option)"
                    type="checkbox"
                    class="size-4 shrink-0 accent-accent"
                    :checked="selected.has(option.decor.id)"
                    @change="toggleDecor(option.decor)"
                  />
                  <!-- Holds the checkbox's column so the photos stay in line. -->
                  <span v-else class="size-4 shrink-0" aria-hidden="true"></span>
                  <AuthFileImage
                    v-if="option.decor.image_file_id"
                    :file-id="option.decor.image_file_id"
                    :alt="option.decor.label"
                    class="size-[34px] shrink-0 rounded-md object-cover"
                  />
                  <span
                    v-else
                    class="sw"
                    :class="materialSwatchClass(swatchSource(option.decor))"
                  />
                  <span class="grid min-w-0 flex-1 gap-0.5">
                    <span class="break-words text-sm font-bold text-ink">
                      {{ option.decor.label }}
                    </span>
                    <small class="break-words text-ink-muted">
                      {{ option.decor.manufacturer_name }}
                    </small>
                  </span>
                </component>
                <!-- The count chip IS the disclosure: `3 o'lcham` when none is
                     carried, `2/3 o'lcham bor` while some are, `Hammasi bor`
                     when nothing is left to add — and it opens the list behind
                     the number. A carried decor is never hidden (carrying 18 mm
                     does not stop you adding 16 mm), so the number is the row's
                     answer to "why would I open this?" and the panel is the
                     answer to "which ones, then?". It sits OUTSIDE the label so
                     that opening the o'lchamlar does not tick the decor. -->
                <button
                  type="button"
                  class="mp-chip shrink-0 cursor-pointer hover:border-accent"
                  :aria-expanded="expanded.has(option.decor.id)"
                  :aria-label="
                    $t('inventory.attach.previewAria', {
                      name: option.decor.label,
                      summary: formatCountChip(option),
                    })
                  "
                  @click="toggleFormatPreview(option.decor)"
                >
                  {{ formatCountChip(option) }}
                  <AppIcon
                    name="chevron-down"
                    class="size-[15px] flex-none text-ink-muted transition-transform"
                    :class="expanded.has(option.decor.id) ? 'rotate-180' : ''"
                  />
                </button>
              </div>

              <!-- A preview, not a second place to tick: what the branch already
                   carries is READ here, what to add is chosen and priced one
                   step on. -->
              <div v-if="expanded.has(option.decor.id)" class="border-t border-hairline px-3 py-2">
                <p v-if="previewLoading.has(option.decor.id)" class="text-xs text-ink-muted">
                  {{ $t('inventory.attach.loading') }}
                </p>
                <div
                  v-else-if="previewFailed.has(option.decor.id)"
                  class="flex flex-wrap items-center gap-2"
                >
                  <span class="text-xs text-ink-muted">
                    {{ $t('inventory.attach.loadFailed') }}
                  </span>
                  <button
                    type="button"
                    class="mp-button mp-button-outline"
                    @click="ensureFormats(option.decor.id)"
                  >
                    {{ $t('inventory.action.retry') }}
                  </button>
                </div>
                <p
                  v-else-if="previewRows(option.decor.id).length === 0"
                  class="text-xs text-ink-muted"
                >
                  {{ $t('inventory.attach.noFormats') }}
                </p>
                <ul v-else class="grid gap-1">
                  <li
                    v-for="row in previewRows(option.decor.id)"
                    :key="row.key"
                    class="flex min-w-0 items-center justify-between gap-2 text-xs"
                    :class="row.carried ? 'text-ink-muted' : 'text-ink'"
                  >
                    <span class="min-w-0 break-words">{{ row.label }}</span>
                    <span v-if="row.carried" class="mp-chip shrink-0">
                      {{ $t('inventory.attach.carried') }}
                    </span>
                  </li>
                </ul>
              </div>
            </div>
          </li>
        </ul>
        <p v-if="nothingLeftToAdd" class="text-xs text-ink-muted">
          {{ $t('inventory.attach.nothingLeftToAdd') }}
        </p>
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
        <!-- Quick picks: the o'lchamlar the selection shares, one chip each. A
             price list is many decors in one size; this is where that becomes
             one press instead of one tick per decor. -->
        <div
          v-if="quickPicks.length > 0"
          class="flex flex-wrap items-center gap-2 rounded-md border border-hairline bg-sunk px-3 py-2"
        >
          <span class="text-sm font-bold text-ink">{{ $t('inventory.attach.quickPick') }}</span>
          <button
            v-for="pick in quickPicks"
            :key="pick.key"
            type="button"
            class="mp-chip cursor-pointer transition-colors"
            :class="
              pick.allChecked
                ? 'border-select-chip-line bg-select-chip text-ink'
                : 'hover:border-accent'
            "
            :aria-pressed="pick.allChecked"
            @click="toggleQuickPick(pick)"
          >
            {{ pick.label }} ({{ pick.rowKeys.length }})
          </button>
          <button
            type="button"
            class="mp-chip cursor-pointer transition-colors"
            :class="
              allAddableChecked
                ? 'border-select-chip-line bg-select-chip text-ink'
                : 'hover:border-accent'
            "
            :aria-pressed="allAddableChecked"
            @click="toggleAllAddable"
          >
            {{ $t('inventory.attach.quickPickAll', { n: addableRows.length }) }}
          </button>
        </div>

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
