<script setup lang="ts">
/**
 * "+ Material" — attach MANY dekorlar to this branch, each in one or more o'lchamlar.
 *
 * Two steps, because the catalog reshape split identity from o'lcham: step 1 picks
 * the *dekorlar* (a platform fact — manufacturer, tur, kod, nomi, photo), step 2
 * picks the *o'lchamlar* (a branch fact — qalinlik × o'lcham, or qalinlik × lenta
 * eni). A dekor the branch already carries is never hidden: carrying 18 mm does
 * not stop you adding 16 mm, so it stays in the list with its carried count.
 *
 * Step 1 is multi-select, and that is the point. 87% of carried dekorlar exist in
 * exactly one o'lcham, so the multiplication that matters is MANY DEKORLAR × ONE
 * O'LCHAM: a branch registering its supplier list ticks thirty boards and one
 * sheet size. "Filtrdagi hammasi (N)" therefore covers the whole filter, paging
 * past the loaded page server-side rather than lying about the page it can see.
 *
 * Because a selection can span turlar, the chip axes are **per tur**: one block
 * per distinct tur in the selection, each with its own qalinlik / o'lcham chips,
 * its own "Nostandart · faqat sizda" group and its own "+ qo'shish". A board and
 * its matching kromka have different axes and still belong in one save.
 *
 * The standard chip sets are hard-coded in the web app (`standardFormats.ts`) and
 * anything else the branch types in with "+ qo'shish" — it simply becomes that
 * branch's row, with no approval step. Price and threshold are optional and
 * default to 0: a branch routinely registers its whole o'lcham list before it
 * knows prices.
 */
import { computed, reactive, ref, watch } from 'vue'
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
import type { Dekor, DekorType } from '@/shared/stores/admin'
import {
  useWorkshopStore,
  type BranchCatalogOption,
  type BranchMaterialAttachItem,
  type BranchMaterialFormatInput,
} from '@/shared/stores/workshop'

const props = defineProps<{ open: boolean; branchId: string }>()
const emit = defineEmits<{
  close: []
  // Both halves travel: a duplicate o'lcham is *skipped* server-side, never an
  // error, so the caller has to be able to say "3 added, 1 already there".
  attached: [result: { created: number; skipped: number }]
}>()

// Server-side page size for the dekor picker. "Filtrdagi hammasi" pages past it
// using the endpoint's `total`, so this bounds the DOM, not the selection.
const PAGE_LIMIT = 100

const { t } = useI18n()
const workshop = useWorkshopStore()

const EMPTY_SET: StandardFormatSet = { qalinliklar: [], olchamlar: [], kromkaEnlar: [] }

/**
 * The chip state of ONE tur. Keyed by tur rather than held globally because a
 * selection spanning ldsp + kromka needs two independent sets of axes.
 *
 * `custom*` are the "+ qo'shish" additions, live only until the sheet closes —
 * once submitted they become branch rows and `nonStandardFacets` picks them up.
 */
interface TurPicks {
  readonly qalinliklar: readonly string[]
  readonly sizeKeys: readonly string[]
  readonly tapeWidths: readonly number[]
  readonly customQalinliklar: readonly string[]
  readonly customSizes: readonly StandardPanelSize[]
  readonly customTapeWidths: readonly number[]
}

// Shared default so `picks()` allocates nothing per render — safe to share
// precisely because `TurPicks` is readonly: every write path replaces the object
// rather than mutating it.
const EMPTY_PICKS: TurPicks = {
  qalinliklar: [],
  sizeKeys: [],
  tapeWidths: [],
  customQalinliklar: [],
  customSizes: [],
  customTapeWidths: [],
}

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

// Dekor ids matching the current filter. Until "Filtrdagi hammasi" pages through
// the rest, only the loaded page is known — `filterComplete` says which it is, so
// the master checkbox never claims to cover rows nobody has fetched.
const filterIds = ref<string[]>([])
const filterComplete = ref(false)

// Keyed by dekor id so the selection survives filter changes, paging, and the
// step-1 ⇄ step-2 round trip. Insertion order is the order rows are rendered in.
const selected = ref(new Map<string, Dekor>())
const selectedDekorlar = computed(() => [...selected.value.values()])
const selectedCount = computed(() => selected.value.size)

// Chip picks per tur. Deselecting a dekor deliberately leaves its tur's picks in
// place: re-ticking a card of that tur brings them straight back, and a tur no
// longer in the selection is neither rendered nor read.
const picksByTur = ref<Record<string, TurPicks>>({})

const customOpen = ref<{ tur: DekorType; kind: 'thickness' | 'size' | 'tape' } | null>(null)
const customDraft = reactive({ thickness: '', length: '', width: '', tape: '' })
const customError = ref<string | null>(null)

// Price / threshold text per ROW key (dekor id + o'lcham key — two dekorlar can
// produce the same o'lcham). Read with a default rather than pre-seeded: the
// cross product changes on every chip click, and a synced map would either mutate
// during render or lose what the operator already typed.
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

// The master checkbox reflects the filter, not the page: it is checked once every
// dekor matching the current filter sits in the selection. With more matches than
// one page holds, that is only knowable after the select-all pass has paged
// through them — before that the box stays unchecked rather than lying.
const filterFullySelected = computed(
  () =>
    total.value > 0 &&
    filterComplete.value &&
    filterIds.value.every((id) => selected.value.has(id)),
)

// Order of first appearance in the selection, not `DEKOR_TYPES` order: a dekor
// carrying a tur outside the current enum must still get a block rather than
// silently losing its rows.
const selectedTurlar = computed<DekorType[]>(() => [
  ...new Set(selectedDekorlar.value.map((dekor) => dekor.tur)),
])

const dekorCountByTur = computed<Record<string, number>>(() => {
  const counts: Record<string, number> = {}
  for (const dekor of selectedDekorlar.value) counts[dekor.tur] = (counts[dekor.tur] ?? 0) + 1
  return counts
})

const standardByTur = computed<Record<string, StandardFormatSet>>(() => {
  const out: Record<string, StandardFormatSet> = {}
  for (const value of selectedTurlar.value) out[value] = standardFormatSet(value)
  return out
})

/**
 * Per tur: the branch's own non-standard facets plus anything added in this
 * session.
 *
 * Scoped by `tur` across every dekor the branch carries — NOT by the selected
 * dekorlar. One block now serves many dekorlar at once, and the operator is
 * typically adding dekorlar the branch does not carry yet; scoping to those would
 * empty the group exactly when its chips are most useful, forcing "+ qo'shish"
 * for an o'lcham the branch demonstrably uses.
 *
 * Derived from `workshop.branchMaterials`, the rows the catalog page has loaded.
 * That list is paged and filtered, so an o'lcham beyond it can slip through as
 * "not carried" — which is exactly why the response's `skipped` is surfaced as a
 * notice rather than an error.
 */
const customFacetsByTur = computed<Record<string, StandardFormatSet>>(() => {
  const out: Record<string, StandardFormatSet> = {}
  for (const value of selectedTurlar.value) {
    const branch = nonStandardFacets(value, workshop.branchMaterials)
    const own = picks(value)
    const qalinliklar = [...new Set([...branch.qalinliklar, ...own.customQalinliklar])].sort(
      (left, right) => Number(left) - Number(right),
    )
    const sizes = new Map<string, StandardPanelSize>()
    for (const size of [...branch.olchamlar, ...own.customSizes]) sizes.set(sizeKey(size), size)
    const kromkaEnlar = [...new Set([...branch.kromkaEnlar, ...own.customTapeWidths])].sort(
      (left, right) => left - right,
    )
    out[value] = {
      qalinliklar,
      olchamlar: isTape(value) ? [] : [...sizes.values()],
      kromkaEnlar,
    }
  }
  return out
})

const allSizesByTur = computed<Record<string, StandardPanelSize[]>>(() => {
  const out: Record<string, StandardPanelSize[]> = {}
  for (const value of selectedTurlar.value) {
    out[value] = [...standard(value).olchamlar, ...customFacets(value).olchamlar]
  }
  return out
})

function picks(tur: DekorType): TurPicks {
  return picksByTur.value[tur] ?? EMPTY_PICKS
}

function setPicks(tur: DekorType, patch: Partial<TurPicks>) {
  picksByTur.value = { ...picksByTur.value, [tur]: { ...picks(tur), ...patch } }
}

function standard(tur: DekorType): StandardFormatSet {
  return standardByTur.value[tur] ?? EMPTY_SET
}

function customFacets(tur: DekorType): StandardFormatSet {
  return customFacetsByTur.value[tur] ?? EMPTY_SET
}

function allSizes(tur: DekorType): StandardPanelSize[] {
  return allSizesByTur.value[tur] ?? []
}

function hasAnyThickness(tur: DekorType) {
  return standard(tur).qalinliklar.length + customFacets(tur).qalinliklar.length > 0
}

function hasAnySize(tur: DekorType) {
  return isTape(tur)
    ? standard(tur).kromkaEnlar.length + customFacets(tur).kromkaEnlar.length > 0
    : allSizes(tur).length > 0
}

const carriedByDekor = computed(() => {
  const map = new Map<string, Set<string>>()
  for (const dekor of selectedDekorlar.value) {
    map.set(dekor.id, carriedFormatKeys(workshop.branchMaterials, dekor.id))
  }
  return map
})

interface FormatRow {
  /** Row identity — dekor id + o'lcham key. Two dekorlar share o'lcham keys. */
  key: string
  dekor: Dekor
  tur: DekorType
  qalinlik: string
  size: StandardPanelSize | null
  kromkaEni: number | null
  label: string
  carried: boolean
}

const rows = computed<FormatRow[]>(() => {
  const out: FormatRow[] = []
  for (const dekor of selectedDekorlar.value) {
    const turValue = dekor.tur
    const picked = picks(turValue)
    if (picked.qalinliklar.length === 0) continue
    const carried = carriedByDekor.value.get(dekor.id) ?? new Set<string>()
    for (const qalinlik of picked.qalinliklar) {
      if (isTape(turValue)) {
        for (const width of picked.tapeWidths) {
          const key = formatKey({ qalinlik_mm: qalinlik, kromka_eni_mm: width })
          out.push({
            key: `${dekor.id}|${key}`,
            dekor,
            tur: turValue,
            qalinlik,
            size: null,
            kromkaEni: width,
            label: t('catalog.meta.tapeFormat', { thickness: qalinlik, width }),
            carried: carried.has(key),
          })
        }
        continue
      }
      for (const sizeKeyValue of picked.sizeKeys) {
        const size = sizeByKey(turValue, sizeKeyValue)
        if (!size) continue
        const key = formatKey({
          qalinlik_mm: qalinlik,
          uzunlik_mm: size.uzunlik_mm,
          eni_mm: size.eni_mm,
        })
        out.push({
          key: `${dekor.id}|${key}`,
          dekor,
          tur: turValue,
          qalinlik,
          size,
          kromkaEni: null,
          label: t('catalog.meta.panelFormat', {
            length: size.uzunlik_mm,
            width: size.eni_mm,
            thickness: qalinlik,
          }),
          carried: carried.has(key),
        })
      }
    }
  }
  return out
})

const pendingRows = computed(() => rows.value.filter((row) => !row.carried))

// One block per dekor so the table reads as "this dekor, these o'lchamlar"
// instead of a flat list whose labels repeat across dekorlar.
const groupedRows = computed(() => {
  const groups: { dekor: Dekor; rows: FormatRow[] }[] = []
  const at = new Map<string, number>()
  for (const row of rows.value) {
    const index = at.get(row.dekor.id)
    if (index === undefined) {
      at.set(row.dekor.id, groups.length)
      groups.push({ dekor: row.dekor, rows: [row] })
    } else {
      groups[index].rows.push(row)
    }
  }
  return groups
})

function sizeKey(size: StandardPanelSize) {
  return `${size.uzunlik_mm}x${size.eni_mm}`
}

function sizeByKey(tur: DekorType, key: string) {
  return allSizes(tur).find((size) => sizeKey(size) === key) ?? null
}

function swatchSource(dekor: Dekor) {
  return { id: dekor.id, nomi: dekor.nomi, kod: dekor.kod }
}

// Follows the ROW's tur, not one global flag: a batch can hold both a board
// priced per list and a kromka priced per metre.
function priceUnit(tur: DekorType) {
  return isTape(tur) ? t('inventory.attach.priceUnitMetre') : t('inventory.attach.priceUnitSheet')
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

function toggleQalinlik(tur: DekorType, value: string) {
  setPicks(tur, { qalinliklar: toggle(picks(tur).qalinliklar, value) })
}

function toggleSize(tur: DekorType, value: string) {
  setPicks(tur, { sizeKeys: toggle(picks(tur).sizeKeys, value) })
}

function toggleTapeWidth(tur: DekorType, value: number) {
  setPicks(tur, { tapeWidths: toggle(picks(tur).tapeWidths, value) })
}

function isCustomOpen(tur: DekorType, kind: 'thickness' | 'size' | 'tape') {
  return customOpen.value?.tur === tur && customOpen.value.kind === kind
}

function openCustom(tur: DekorType, kind: 'thickness' | 'size' | 'tape') {
  customOpen.value = isCustomOpen(tur, kind) ? null : { tur, kind }
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

function addCustomThickness(tur: DekorType) {
  const raw = customDraft.thickness.trim().replace(',', '.')
  const parsed = Number(raw)
  if (!raw || !Number.isFinite(parsed) || parsed <= 0) {
    customError.value = t('inventory.attach.customInvalid')
    return
  }
  const value = normalizeQalinlik(raw)
  const known = new Set([
    ...standard(tur).qalinliklar.map(normalizeQalinlik),
    ...customFacets(tur).qalinliklar,
  ])
  if (known.has(value)) {
    customError.value = t('inventory.attach.customDuplicate')
    // Still select it — the operator asked for this qalinlik and it exists.
    if (!picks(tur).qalinliklar.includes(value)) toggleQalinlik(tur, value)
    return
  }
  setPicks(tur, {
    customQalinliklar: [...picks(tur).customQalinliklar, value],
    qalinliklar: toggle(picks(tur).qalinliklar, value),
  })
  customOpen.value = null
}

function addCustomSize(tur: DekorType) {
  const length = positiveInt(customDraft.length)
  const width = positiveInt(customDraft.width)
  if (length === null || width === null) {
    customError.value = t('inventory.attach.customInvalid')
    return
  }
  // Longer side first, so 1830×2750 and 2750×1830 are one chip, not two.
  const size = normalizePanelSize(length, width)
  const key = sizeKey(size)
  if (allSizes(tur).some((known) => sizeKey(known) === key)) {
    customError.value = t('inventory.attach.customDuplicate')
    if (!picks(tur).sizeKeys.includes(key)) toggleSize(tur, key)
    return
  }
  setPicks(tur, {
    customSizes: [...picks(tur).customSizes, size],
    sizeKeys: toggle(picks(tur).sizeKeys, key),
  })
  customOpen.value = null
}

function addCustomTapeWidth(tur: DekorType) {
  const value = positiveInt(customDraft.tape)
  if (value === null) {
    customError.value = t('inventory.attach.customInvalid')
    return
  }
  const known = new Set([...standard(tur).kromkaEnlar, ...customFacets(tur).kromkaEnlar])
  if (known.has(value)) {
    customError.value = t('inventory.attach.customDuplicate')
    if (!picks(tur).tapeWidths.includes(value)) toggleTapeWidth(tur, value)
    return
  }
  setPicks(tur, {
    customTapeWidths: [...picks(tur).customTapeWidths, value],
    tapeWidths: toggle(picks(tur).tapeWidths, value),
  })
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
    filterIds.value = page.items.map((option) => option.dekor.id)
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
    filterIds.value = options.value.map((option) => option.dekor.id)
    filterComplete.value = options.value.length >= page.total
  } catch {
    loadError.value = true
  } finally {
    loadingMore.value = false
  }
}

function toggleDekor(dekor: Dekor) {
  const next = new Map(selected.value)
  if (next.has(dekor.id)) next.delete(dekor.id)
  else next.set(dekor.id, dekor)
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
    const collected: Dekor[] = options.value.map((option) => option.dekor)
    while (collected.length < total.value) {
      const page = await workshop.fetchCatalogOptions(props.branchId, filters(collected.length))
      if (page.items.length === 0) break
      collected.push(...page.items.map((option) => option.dekor))
    }
    const next = new Map(selected.value)
    for (const dekor of collected) if (!next.has(dekor.id)) next.set(dekor.id, dekor)
    selected.value = next
    filterIds.value = collected.map((dekor) => dekor.id)
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

function resetPicks() {
  picksByTur.value = {}
  customOpen.value = null
  customError.value = null
  priceByKey.value = {}
  thresholdByKey.value = {}
  priceErrorKeys.value = new Set()
  thresholdErrorKeys.value = new Set()
  saveError.value = null
  saveTraceId.value = null
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

function parseThreshold(text: string, tur: DekorType): number | null {
  const trimmed = text.trim()
  if (!trimmed) return 0
  const parsed = parseDisplayQuantity(trimmed, isTape(tur) ? 'm' : 'pcs')
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
  // Grouped by dekor — the wire shape is one item per dekor, its o'lchamlar under it.
  const byDekor = new Map<string, BranchMaterialFormatInput[]>()
  for (const row of pendingRows.value) {
    const price = parsePrice(priceOf(row.key))
    const threshold = parseThreshold(thresholdOf(row.key), row.tur)
    if (price === null) badPrices.add(row.key)
    if (threshold === null) badThresholds.add(row.key)
    if (price === null || threshold === null) continue
    const formats = byDekor.get(row.dekor.id) ?? []
    formats.push({
      qalinlik_mm: row.qalinlik,
      ...(row.size ? { uzunlik_mm: row.size.uzunlik_mm, eni_mm: row.size.eni_mm } : {}),
      ...(row.kromkaEni !== null ? { kromka_eni_mm: row.kromkaEni } : {}),
      price_tiyin: price,
      min_stock: threshold,
    })
    byDekor.set(row.dekor.id, formats)
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
  const items: BranchMaterialAttachItem[] = [...byDekor].map(([dekorId, formats]) => ({
    dekor_id: dekorId,
    formats,
  }))
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
  resetPicks()
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
    <!-- Step 1 — pick the dekorlar. Photo-first: an operator recognises a decor by
         its surface long before its code. Multi-select, because the job is many
         dekorlar in one o'lcham. -->
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
          <li v-for="option in options" :key="option.dekor.id" class="min-w-0">
            <label
              class="flex w-full min-w-0 cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-left transition-colors"
              :class="
                selected.has(option.dekor.id)
                  ? 'border-accent-tint bg-accent-soft'
                  : 'border-hairline bg-elevated hover:border-accent'
              "
            >
              <input
                type="checkbox"
                class="size-4 shrink-0 accent-accent"
                :checked="selected.has(option.dekor.id)"
                @change="toggleDekor(option.dekor)"
              />
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
          @click="step = 2"
        >
          {{ $t('inventory.attach.continue') }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="emit('close')">
          {{ $t('inventory.action.cancel') }}
        </button>
      </div>
    </div>

    <!-- Step 2 — pick the o'lchamlar, then price them (both optional). One chip
         block per tur in the selection; a board and its kromka have different axes. -->
    <div v-else class="grid gap-3">
      <p class="text-sm font-bold text-ink-muted">
        {{ $t('inventory.attach.selectedCount', { n: selectedCount }, selectedCount) }}
      </p>

      <div
        v-for="turValue in selectedTurlar"
        :key="`block-${turValue}`"
        class="grid gap-3 rounded-md border border-hairline px-3 py-3"
      >
        <div class="flex flex-wrap items-baseline gap-2">
          <span class="text-sm font-extrabold text-ink">{{ dekorTurLabel(turValue) }}</span>
          <small class="text-ink-muted">
            {{
              $t(
                'inventory.attach.turDekorCount',
                { n: dekorCountByTur[turValue] ?? 0 },
                dekorCountByTur[turValue] ?? 0,
              )
            }}
          </small>
        </div>

        <fieldset class="grid gap-2">
          <legend class="text-sm font-bold text-ink">
            {{ $t('inventory.attach.standardThickness') }}
          </legend>
          <div class="flex flex-wrap items-center gap-2">
            <button
              v-for="value in standard(turValue).qalinliklar"
              :key="`std-q-${turValue}-${value}`"
              type="button"
              class="inline-flex min-h-10 items-center rounded-full border px-4 text-sm font-extrabold transition-colors"
              :class="
                picks(turValue).qalinliklar.includes(value)
                  ? 'border-accent-tint bg-accent-soft text-accent-strong'
                  : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
              "
              :aria-pressed="picks(turValue).qalinliklar.includes(value)"
              @click="toggleQalinlik(turValue, value)"
            >
              {{ value }} mm
            </button>
            <button
              type="button"
              class="inline-flex min-h-10 items-center rounded-full border border-dashed border-hairline-strong px-4 text-sm font-extrabold text-ink-soft transition-colors hover:border-accent hover:text-ink"
              :aria-expanded="isCustomOpen(turValue, 'thickness')"
              @click="openCustom(turValue, 'thickness')"
            >
              {{ $t('inventory.attach.addCustom') }}
            </button>
          </div>

          <!-- "Nostandart · faqat sizda": this branch's own qalinliklar for this
               tur, kept visually apart so a standard set never silently grows. -->
          <template v-if="customFacets(turValue).qalinliklar.length > 0">
            <span class="text-xs font-bold text-ink-muted">
              {{ $t('inventory.attach.customGroup') }}
            </span>
            <div class="flex flex-wrap items-center gap-2">
              <button
                v-for="value in customFacets(turValue).qalinliklar"
                :key="`own-q-${turValue}-${value}`"
                type="button"
                class="inline-flex min-h-10 items-center rounded-full border border-dashed px-4 text-sm font-extrabold transition-colors"
                :class="
                  picks(turValue).qalinliklar.includes(value)
                    ? 'border-accent-tint bg-accent-soft text-accent-strong'
                    : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
                "
                :aria-pressed="picks(turValue).qalinliklar.includes(value)"
                @click="toggleQalinlik(turValue, value)"
              >
                {{ value }} mm
              </button>
            </div>
          </template>

          <p v-if="!hasAnyThickness(turValue)" class="text-xs text-ink-muted">
            {{ $t('inventory.attach.noStandardFormats') }}
          </p>

          <div
            v-if="isCustomOpen(turValue, 'thickness')"
            class="flex flex-wrap items-end gap-2 rounded-md border border-hairline bg-sunk px-3 py-2"
          >
            <label class="grid min-w-0 flex-1 basis-40 gap-1">
              <span class="text-xs font-bold text-ink-muted">
                {{ $t('inventory.attach.customThicknessLabel') }}
              </span>
              <input v-model="customDraft.thickness" class="mp-input" inputmode="decimal" />
            </label>
            <button
              type="button"
              class="mp-button mp-button-outline"
              @click="addCustomThickness(turValue)"
            >
              {{ $t('inventory.action.add') }}
            </button>
            <small v-if="customError" class="mp-field-error basis-full">{{ customError }}</small>
          </div>
        </fieldset>

        <fieldset class="grid gap-2">
          <legend class="text-sm font-bold text-ink">
            {{
              isTape(turValue)
                ? $t('inventory.attach.standardTapeWidth')
                : $t('inventory.attach.standardSize')
            }}
          </legend>
          <div class="flex flex-wrap items-center gap-2">
            <template v-if="isTape(turValue)">
              <button
                v-for="value in standard(turValue).kromkaEnlar"
                :key="`std-w-${turValue}-${value}`"
                type="button"
                class="inline-flex min-h-10 items-center rounded-full border px-4 text-sm font-extrabold transition-colors"
                :class="
                  picks(turValue).tapeWidths.includes(value)
                    ? 'border-accent-tint bg-accent-soft text-accent-strong'
                    : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
                "
                :aria-pressed="picks(turValue).tapeWidths.includes(value)"
                @click="toggleTapeWidth(turValue, value)"
              >
                {{ value }} mm
              </button>
            </template>
            <template v-else>
              <button
                v-for="size in standard(turValue).olchamlar"
                :key="`std-s-${turValue}-${sizeKey(size)}`"
                type="button"
                class="inline-flex min-h-10 items-center rounded-full border px-4 text-sm font-extrabold transition-colors"
                :class="
                  picks(turValue).sizeKeys.includes(sizeKey(size))
                    ? 'border-accent-tint bg-accent-soft text-accent-strong'
                    : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
                "
                :aria-pressed="picks(turValue).sizeKeys.includes(sizeKey(size))"
                @click="toggleSize(turValue, sizeKey(size))"
              >
                {{ size.uzunlik_mm }}×{{ size.eni_mm }}
              </button>
            </template>
            <button
              type="button"
              class="inline-flex min-h-10 items-center rounded-full border border-dashed border-hairline-strong px-4 text-sm font-extrabold text-ink-soft transition-colors hover:border-accent hover:text-ink"
              :aria-expanded="isCustomOpen(turValue, isTape(turValue) ? 'tape' : 'size')"
              @click="openCustom(turValue, isTape(turValue) ? 'tape' : 'size')"
            >
              {{ $t('inventory.attach.addCustom') }}
            </button>
          </div>

          <template
            v-if="
              isTape(turValue)
                ? customFacets(turValue).kromkaEnlar.length > 0
                : customFacets(turValue).olchamlar.length > 0
            "
          >
            <span class="text-xs font-bold text-ink-muted">
              {{ $t('inventory.attach.customGroup') }}
            </span>
            <div class="flex flex-wrap items-center gap-2">
              <template v-if="isTape(turValue)">
                <button
                  v-for="value in customFacets(turValue).kromkaEnlar"
                  :key="`own-w-${turValue}-${value}`"
                  type="button"
                  class="inline-flex min-h-10 items-center rounded-full border border-dashed px-4 text-sm font-extrabold transition-colors"
                  :class="
                    picks(turValue).tapeWidths.includes(value)
                      ? 'border-accent-tint bg-accent-soft text-accent-strong'
                      : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
                  "
                  :aria-pressed="picks(turValue).tapeWidths.includes(value)"
                  @click="toggleTapeWidth(turValue, value)"
                >
                  {{ value }} mm
                </button>
              </template>
              <template v-else>
                <button
                  v-for="size in customFacets(turValue).olchamlar"
                  :key="`own-s-${turValue}-${sizeKey(size)}`"
                  type="button"
                  class="inline-flex min-h-10 items-center rounded-full border border-dashed px-4 text-sm font-extrabold transition-colors"
                  :class="
                    picks(turValue).sizeKeys.includes(sizeKey(size))
                      ? 'border-accent-tint bg-accent-soft text-accent-strong'
                      : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent'
                  "
                  :aria-pressed="picks(turValue).sizeKeys.includes(sizeKey(size))"
                  @click="toggleSize(turValue, sizeKey(size))"
                >
                  {{ size.uzunlik_mm }}×{{ size.eni_mm }}
                </button>
              </template>
            </div>
          </template>

          <p v-if="!hasAnySize(turValue)" class="text-xs text-ink-muted">
            {{ $t('inventory.attach.noStandardFormats') }}
          </p>

          <div
            v-if="isCustomOpen(turValue, 'size')"
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
            <button
              type="button"
              class="mp-button mp-button-outline"
              @click="addCustomSize(turValue)"
            >
              {{ $t('inventory.action.add') }}
            </button>
            <small v-if="customError" class="mp-field-error basis-full">{{ customError }}</small>
          </div>

          <div
            v-if="isCustomOpen(turValue, 'tape')"
            class="flex flex-wrap items-end gap-2 rounded-md border border-hairline bg-sunk px-3 py-2"
          >
            <label class="grid min-w-0 flex-1 basis-40 gap-1">
              <span class="text-xs font-bold text-ink-muted">
                {{ $t('inventory.attach.customTapeWidthLabel') }}
              </span>
              <input v-model="customDraft.tape" class="mp-input" inputmode="numeric" />
            </label>
            <button
              type="button"
              class="mp-button mp-button-outline"
              @click="addCustomTapeWidth(turValue)"
            >
              {{ $t('inventory.action.add') }}
            </button>
            <small v-if="customError" class="mp-field-error basis-full">{{ customError }}</small>
          </div>
        </fieldset>
      </div>

      <div v-if="rows.length === 0" class="st-empty !py-6">
        <p>{{ $t('inventory.attach.selectFormats') }}</p>
      </div>

      <template v-else>
        <div class="table-wrap">
          <table class="tbl tbl-fluid">
            <thead>
              <tr>
                <!-- The dekor name is the longest string in the table and `auto`
                     layout would otherwise starve it down to one word per line
                     while the o'lcham column keeps slack it has no use for. -->
                <th class="min-w-[190px]">{{ $t('inventory.attach.columnDekor') }}</th>
                <th class="w-full">{{ $t('inventory.attach.columnFormat') }}</th>
                <th class="nowrap right">{{ $t('inventory.attach.columnPrice') }}</th>
                <th class="nowrap right">{{ lowStockThresholdColumn() }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="group in groupedRows" :key="group.dekor.id">
                <tr v-for="(row, index) in group.rows" :key="row.key">
                  <!-- One identity cell per dekor, spanning its o'lchamlar: with
                       many dekorlar the o'lcham label alone is ambiguous, and
                       repeating the name on every row buries the o'lchamlar. -->
                  <td v-if="index === 0" :rowspan="group.rows.length" class="align-top">
                    <div class="flex min-w-0 items-center gap-2">
                      <AuthFileImage
                        v-if="group.dekor.image_file_id"
                        :file-id="group.dekor.image_file_id"
                        :alt="group.dekor.label"
                        class="size-[28px] shrink-0 rounded-md object-cover"
                      />
                      <span
                        v-else
                        class="sw shrink-0"
                        :class="materialSwatchClass(swatchSource(group.dekor))"
                      />
                      <div class="grid min-w-0 gap-0.5">
                        <span class="break-words font-bold text-ink">{{ group.dekor.label }}</span>
                        <small class="break-words text-ink-muted">
                          {{ group.dekor.manufacturer_name }} · {{ dekorTurLabel(group.dekor.tur) }}
                        </small>
                      </div>
                    </div>
                  </td>
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
                      :aria-label="
                        $t('inventory.attach.priceAria', {
                          name: `${group.dekor.label} · ${row.label}`,
                        })
                      "
                      :aria-invalid="priceErrorKeys.has(row.key) || undefined"
                      :class="priceErrorKeys.has(row.key) ? '!border-danger' : ''"
                      @input="setPrice(row.key, ($event.target as HTMLInputElement).value)"
                    />
                    <small class="block text-ink-muted">{{ priceUnit(row.tur) }}</small>
                  </td>
                  <td class="nowrap right">
                    <input
                      class="mp-input w-20 text-right"
                      inputmode="decimal"
                      :disabled="row.carried"
                      :value="row.carried ? '' : thresholdOf(row.key)"
                      :aria-label="
                        $t('inventory.attach.thresholdAria', {
                          name: `${group.dekor.label} · ${row.label}`,
                        })
                      "
                      :aria-invalid="thresholdErrorKeys.has(row.key) || undefined"
                      :class="thresholdErrorKeys.has(row.key) ? '!border-danger' : ''"
                      @input="setThreshold(row.key, ($event.target as HTMLInputElement).value)"
                    />
                    <small class="block text-ink-muted">{{ thresholdUnit(row.tur) }}</small>
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
