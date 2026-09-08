<script setup lang="ts">
/**
 * "+ Material" — have this branch carry catalog formats, **one decor at a time**.
 *
 * Two screens, because the platform owns the product and the branch owns only
 * the decision to sell it: step 1 picks the *decor* (a pattern — manufacturer,
 * code, name, photo), step 2 picks which of that decor's **o'lchamlar** the
 * branch carries and what it charges for each. A decor already carried is never
 * hidden: carrying 18 mm does not stop you adding 16 mm, so it stays in the list
 * with its carried count.
 *
 * **One decor, not a batch** (owner review, 2026-09-08). The sheet used to be a
 * multi-select: tick thirty decors, then tick the sheet size they share. It
 * registered a price list in one pass and cost everything else — a selection to
 * keep track of, a master checkbox that had to page the server to be honest, a
 * quick-pick chip row, a price table with a decor column, and two places where a
 * tick meant two different things. The owner chose the smaller shape: a row is a
 * **door**, it opens the o'lchamlar of that decor, and «+ Material» is the way
 * to the next one. Everything the batch needed is gone rather than disabled.
 *
 * **The branch can enter what the library lacks** (2026-09-07). The platform
 * catalog is a pre-filled list, not an authority: «+ Yangi dekor» opens the
 * create form for a decor nobody has entered, and «+ Boshqa o'lcham» adds one
 * size to a decor that already exists. Both are visible to this workshop only.
 * The sheet itself stays a router — `pick → create → price` — and the form is
 * `BranchDecorCreateForm`, so this file does not grow a third job.
 *
 * **A size that already exists is merged in silence** (owner item 2): the
 * operator types a shape the catalog already holds and gets the row that holds
 * it, ticked. No warning, no toast, nothing to read — a duplicate is the app's
 * problem, not theirs. The one thing they are told is the one thing they can
 * act on: the shape is already ON THE SHELF, so there is nothing to add.
 *
 * Price is optional and defaults to 0: a branch routinely registers its whole
 * list before it knows prices. The low-stock threshold that used to sit beside
 * it is retired (2026-09-08) — a negative balance is the only shelf fact the
 * app watches, and it needs no number behind it.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { apiTraceId, ApiError } from '@/shared/api/client'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { sanitizeMoneyInput } from '@/shared/app/inputSanitizers'
import {
  DECOR_TYPES,
  decorTypeLabel,
  finishedSidesNote,
  formatDimensionsLabel,
  isTape,
} from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { formatDraftKey, type FormatDraft } from '@/shared/app/standardFormats'
import AppIcon from '@/shared/components/AppIcon.vue'
import AppModal from '@/shared/components/AppModal.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import BranchDecorCreateForm from '@/shared/components/BranchDecorCreateForm.vue'
import BranchDecorFormatPicker from '@/shared/components/BranchDecorFormatPicker.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import FormSelect from '@/shared/components/FormSelect.vue'
import { parseSomToTiyin } from '@/shared/formatters'
import type { Decor, DecorFormat, DecorType } from '@/shared/stores/admin'
import {
  useWorkshopStore,
  type BranchCatalogFormatOption,
  type BranchCatalogOption,
  type BranchMaterialAttachItem,
} from '@/shared/stores/workshop'

const props = defineProps<{ open: boolean; branchId: string }>()
const emit = defineEmits<{
  close: []
  // The decor travels with the counts: the toast names what was added, and a
  // duplicate is *skipped* server-side rather than refused, so the caller has to
  // be able to say "3 added, 1 already there".
  attached: [result: { created: number; skipped: number; decorLabel: string }]
}>()

/** Server-side page size for the decor picker; «Yana» pages past it. */
const PAGE_LIMIT = 100

/** How long «Sizda bor» stays beside a row the branch already carries. */
const CARRIED_NOTE_MS = 3000

const { t } = useI18n()
const workshop = useWorkshopStore()

/** `pick → create → price`. The sheet only routes; the form is its own file. */
type Step = 'pick' | 'create' | 'price'
const step = ref<Step>('pick')
const search = ref('')
const manufacturerFilter = ref<string | null>('all')
const turFilter = ref<string | null>('all')
const options = ref<BranchCatalogOption[]>([])
const total = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const loadError = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveTraceId = ref<string | null>(null)

/** The one decor step 2 is about. `null` only while step 1 is open. */
const picked = ref<Decor | null>(null)

// Step two's data: this branch's answer for each ACTIVE format of the picked
// decor. Cached per decor so a step-2 → back → step-2 round trip does not
// refetch what was on screen a second ago.
const formatsByDecor = ref<Record<string, BranchCatalogFormatOption[]>>({})
const formatsLoading = ref(false)
const formatsError = ref(false)

/** Format ids the operator ticked. A carried row can never enter this set. */
const checked = ref<Set<string>>(new Set())

// Price text per FORMAT id. Read with a default rather than pre-seeded: a
// synced map would either mutate during render or lose what the operator
// already typed.
const priceByKey = ref<Record<string, string>>({})
const priceErrorKeys = ref<Set<string>>(new Set())

// The «+ Boshqa o'lcham» composer, and the row that is answering it with
// «Sizda bor» — the one outcome the operator has to act on.
const composerOpen = ref(false)
const composerBusy = ref(false)
const composerError = ref<string | null>(null)
const carriedNoteKey = ref<string | null>(null)
let carriedNoteTimer: number | undefined

// The create step: what step 1 had typed, and a failed manufacturer read.
const createSeedName = ref('')
const createError = ref<string | null>(null)
const createFormRef = ref<InstanceType<typeof BranchDecorCreateForm> | null>(null)
const createSaving = computed(() => createFormRef.value?.saving ?? false)

// The modal frame, so a step change starts the new screen at its own top rather
// than at the offset the previous one was scrolled to.
const modalRef = ref<InstanceType<typeof AppModal> | null>(null)

// Price inputs by format id — the row just ticked takes the caret, since typing
// the number is the only thing left to do on it.
const priceInputs = new Map<string, HTMLInputElement>()

// `FormSelect`, not `ProjectDropdown`: the latter teleports its panel at z-50 and
// would render behind the modal layer (z-80) — see web/DESIGN.md → Shapes.
const manufacturerOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: t('inventory.attach.manufacturerAll') },
  ...workshop.catalogFilters.manufacturers.map((row) => ({ value: row.id, label: row.name })),
])
// Every `type` is offered, including `dsp` — the workshop calls it by its own
// word, and dropping it would leave those decors unreachable by filter.
const turOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: t('inventory.attach.turAll') },
  ...DECOR_TYPES.map((value) => ({ value, label: decorTypeLabel(value) })),
])

const stepTitle = computed(() => {
  if (step.value === 'create') return t('inventory.attach.createTitle')
  return step.value === 'pick'
    ? t('inventory.attach.stepPickTitle')
    : t('inventory.attach.stepPriceTitle')
})

/** The list found nothing — the one state that carries its own create action. */
const showEmptyState = computed(
  () => !loading.value && !loadError.value && options.value.length === 0,
)

interface FormatRow {
  /** Row identity — the platform format's own id. */
  key: string
  type: DecorType
  format: BranchCatalogFormatOption['decor_format']
  label: string
  carried: boolean
}

/**
 * The picked decor's o'lchamlar: boards first and kromka last, thinnest first
 * inside each substrate.
 *
 * A decor's tape is the accessory to its board — Egger H1145 is a sheet you buy
 * and an edge you buy *for* it — so the board rows are what the eye should land
 * on, and the sizes read as a ladder rather than in whatever order the platform
 * happened to enter them.
 */
const rows = computed<FormatRow[]>(() =>
  (formatsByDecor.value[picked.value?.id ?? ''] ?? [])
    .map((option) => ({
      key: option.decor_format.id,
      type: option.decor_format.type,
      format: option.decor_format,
      // Identity-free: the decor is the header right above these rows, and
      // repeating it on every line buries the one thing that differs.
      label: shortFormatLabel(option.decor_format),
      carried: option.carried,
    }))
    .sort((a, b) => rowOrder(a) - rowOrder(b) || thickness(a) - thickness(b)),
)

function rowOrder(row: FormatRow) {
  return isTape(row.type) ? DECOR_TYPES.length : DECOR_TYPES.indexOf(row.type)
}

function thickness(row: FormatRow) {
  const value = Number(row.format.thickness_mm)
  return Number.isFinite(value) ? value : 0
}

/** Ticked, and not already on the shelf — what «Qo'shish» will post. */
const pendingRows = computed(() =>
  rows.value.filter((row) => !row.carried && checked.value.has(row.key)),
)

/** The decor came back with no active format at all. */
const noFormats = computed(
  () => !formatsLoading.value && !formatsError.value && rows.value.length === 0,
)

/**
 * What the composer's type row opens on — the decor's first o'lcham.
 *
 * It seeds the row, it does not pin it: the type is a property of the format, so
 * a board decor must still be able to take a kromka (Egger H1145 is one decor
 * with both). This only spares the common case — another size of what the decor
 * already has — one press.
 */
const composerType = computed<DecorType>(() => rows.value[0]?.type ?? 'ldsp')

function isChecked(key: string) {
  return checked.value.has(key)
}

/** Tick a row and give it the caret; unticking leaves the typed price alone. */
function toggleFormat(row: FormatRow) {
  if (row.carried) return
  const next = new Set(checked.value)
  if (next.has(row.key)) {
    next.delete(row.key)
    checked.value = next
    return
  }
  next.add(row.key)
  checked.value = next
  void focusPrice(row.key)
}

async function focusPrice(key: string) {
  await nextTick()
  priceInputs.get(key)?.focus()
}

function setPriceInput(key: string, el: unknown) {
  if (el instanceof HTMLInputElement) priceInputs.set(key, el)
  else priceInputs.delete(key)
}

/** `LDSP · 2800×2070×18 mm`, `Kromka · 0.8×22 mm` — the o'lcham alone. */
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
 * The count on a door: `3 o'lcham` when none is carried, `2/3 o'lcham bor`
 * while some are, `Hammasi bor` when nothing is left to add. Text, not a
 * control — the whole row is the control now.
 */
function formatCountText(option: BranchCatalogOption) {
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
  const decor = picked.value
  if (!decor) return
  formatsError.value = false
  // Cached from an earlier visit to this decor: `carried` cannot change while
  // the sheet is open, so a back-and-forth costs no round trip.
  if (!formatsByDecor.value[decor.id]) {
    formatsLoading.value = true
    try {
      const fetched = await workshop.fetchCatalogFormats(props.branchId, decor.id)
      formatsByDecor.value = { ...formatsByDecor.value, [decor.id]: fetched }
    } catch {
      formatsError.value = true
      return
    } finally {
      formatsLoading.value = false
    }
  }
  // Exactly one o'lcham to add means there is nothing to choose — only a price
  // to type, if the operator has one.
  const addable = rows.value.filter((row) => !row.carried)
  if (addable.length === 1) {
    checked.value = new Set([addable[0].key])
    void focusPrice(addable[0].key)
  }
}

function swatchSource(decor: Decor) {
  return { id: decor.id, name: decor.name, code: decor.code }
}

// Follows the ROW's type, not one global flag: a decor is priced per list for
// its board and per metre for its kromka.
function priceUnit(type: DecorType) {
  return isTape(type) ? t('inventory.attach.priceUnitMetre') : t('inventory.attach.priceUnitSheet')
}

function priceOf(key: string) {
  return priceByKey.value[key] ?? ''
}

function setPrice(key: string, value: string) {
  priceByKey.value = { ...priceByKey.value, [key]: sanitizeMoneyInput(value) }
  if (priceErrorKeys.value.has(key)) {
    const next = new Set(priceErrorKeys.value)
    next.delete(key)
    priceErrorKeys.value = next
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

function resetStepTwo() {
  formatsError.value = false
  checked.value = new Set()
  priceByKey.value = {}
  priceErrorKeys.value = new Set()
  closeComposer()
  clearCarriedNote()
  saveError.value = null
  saveTraceId.value = null
}

/** A door opens: step 1 → step 2 for that decor, its o'lchamlar fetched here. */
async function openDecor(decor: Decor) {
  resetStepTwo()
  picked.value = decor
  step.value = 'price'
  scrollToTop()
  await loadFormats()
}

/** Back to the list, which kept its search, filters and paging. */
function backToPick() {
  step.value = 'pick'
  scrollToTop()
}

function scrollToTop() {
  void nextTick(() => modalRef.value?.scrollToTop())
}

// ---- «+ Yangi dekor» ------------------------------------------------------

/**
 * Step 1 → the create form, carrying whatever was typed in the search box.
 *
 * The typed query is almost always the decor's name — that is what the operator
 * looked for and did not find — so it seeds Nomi rather than being thrown away
 * with the step.
 */
function openCreateForm() {
  createSeedName.value = search.value.trim()
  createError.value = null
  step.value = 'create'
  scrollToTop()
  void workshop.loadBranchManufacturers(props.branchId).catch(() => {
    createError.value = t('inventory.attach.manufacturersFailed')
  })
}

/**
 * A created decor goes straight to pricing with every one of its brand-new
 * o'lchamlar ticked: the operator just typed them, so there is nothing left to
 * choose — only a price to put against each.
 */
async function onDecorCreated(result: { decor: Decor; formats: DecorFormat[] }) {
  resetStepTwo()
  picked.value = result.decor
  formatsByDecor.value = {
    ...formatsByDecor.value,
    [result.decor.id]: result.formats.map((decor_format) => ({ decor_format, carried: false })),
  }
  checked.value = new Set(result.formats.map((row) => row.id))
  step.value = 'price'
  scrollToTop()
  const first = rows.value.find((row) => checked.value.has(row.key))
  if (first) await focusPrice(first.key)
}

// ---- «+ Boshqa o'lcham» ---------------------------------------------------

function toggleComposer() {
  composerError.value = null
  composerOpen.value = !composerOpen.value
}

function closeComposer() {
  composerOpen.value = false
  composerBusy.value = false
  composerError.value = null
}

/** «Sizda bor» beside a row, for as long as it takes to read it. */
function showCarriedNote(key: string) {
  clearCarriedNote()
  carriedNoteKey.value = key
  carriedNoteTimer = window.setTimeout(() => {
    carriedNoteKey.value = null
  }, CARRIED_NOTE_MS)
}

function clearCarriedNote() {
  window.clearTimeout(carriedNoteTimer)
  carriedNoteTimer = undefined
  carriedNoteKey.value = null
}

onBeforeUnmount(clearCarriedNote)

/** The format id a 409 `decor_format_exists` names — the twin already on file. */
function existingFormatId(error: unknown): string | null {
  if (!(error instanceof ApiError) || typeof error.body !== 'object' || error.body === null) {
    return null
  }
  const details = (error.body as { details?: unknown }).details
  if (typeof details !== 'object' || details === null) return null
  const id = (details as { decor_format_id?: unknown }).decor_format_id
  return typeof id === 'string' ? id : null
}

/** A stored format read as the draft shape, so the two compare by one key. */
function toDraft(format: DecorFormat): FormatDraft {
  return {
    type: format.type,
    thickness_mm: format.thickness_mm,
    length_mm: format.length_mm,
    width_mm: format.width_mm,
    tape_width_mm: format.tape_width_mm,
    finished_sides: format.finished_sides,
  }
}

/** Take the row into the selection and give it the caret — the silent outcome. */
function absorbRow(row: FormatRow) {
  checked.value = new Set([...checked.value, row.key])
  closeComposer()
  void focusPrice(row.key)
}

/**
 * Add one o'lcham to the picked decor — library or own — and **merge in
 * silence** when it turns out to exist (owner item 2).
 *
 * Three outcomes, and only the last one says anything:
 *
 * - the shape is a row already on screen, or a row the server names in a 409 →
 *   tick it. Nothing is created, nothing is announced: the operator asked for a
 *   size and got the size, which is the whole of what they wanted to know.
 * - the shape is new → `201`, the row appears ticked with an empty price.
 * - the shape is already CARRIED by this branch → there is nothing to add, and
 *   that is the one fact they cannot see for themselves, so the row says
 *   «Sizda bor» for a moment and the composer keeps what was typed.
 */
async function addDecorFormat(draft: FormatDraft) {
  const decor = picked.value
  if (!decor) return
  clearCarriedNote()
  const key = formatDraftKey(draft)

  // Client-side first: the sheet already knows every active o'lcham of this
  // decor, so the common twin costs no round trip at all.
  const local = rows.value.find((row) => formatDraftKey(toDraft(row.format)) === key)
  if (local) {
    if (local.carried) showCarriedNote(local.key)
    else absorbRow(local)
    return
  }

  composerBusy.value = true
  composerError.value = null
  try {
    const created = await workshop.createBranchDecorFormat(props.branchId, decor.id, draft)
    appendFormat(decor.id, { decor_format: created, carried: false })
    absorbRow({
      key: created.id,
      type: created.type,
      format: created,
      label: shortFormatLabel(created),
      carried: false,
    })
  } catch (caught) {
    await absorbTwin(decor.id, caught, key)
  } finally {
    composerBusy.value = false
  }
}

/**
 * The 409 half of the silent merge: find the row the server refused to
 * duplicate and tick it.
 *
 * The twin can be one the sheet never listed — a format the branch cannot
 * attach, a library row that went inactive after this list was fetched — so a
 * miss is answered by re-reading the decor's formats before giving up. If it is
 * still nowhere, the sheet has nothing to tick and says so: silence would leave
 * a pressed button with no effect anywhere on the screen.
 */
async function absorbTwin(decorId: string, caught: unknown, draftKey: string) {
  const twinId = existingFormatId(caught)
  if (twinId === null) {
    composerError.value = t('inventory.attach.formatCreateFailed')
    return
  }
  let row = rows.value.find((candidate) => candidate.key === twinId)
  if (!row) {
    try {
      const fetched = await workshop.fetchCatalogFormats(props.branchId, decorId)
      formatsByDecor.value = { ...formatsByDecor.value, [decorId]: fetched }
    } catch {
      composerError.value = t('inventory.attach.formatCreateFailed')
      return
    }
    row =
      rows.value.find((candidate) => candidate.key === twinId) ??
      rows.value.find((candidate) => formatDraftKey(toDraft(candidate.format)) === draftKey)
  }
  if (!row) {
    composerError.value = t('inventory.attach.formatCreateFailed')
    return
  }
  if (row.carried) showCarriedNote(row.key)
  else absorbRow(row)
}

function appendFormat(decorId: string, option: BranchCatalogFormatOption) {
  formatsByDecor.value = {
    ...formatsByDecor.value,
    [decorId]: [...(formatsByDecor.value[decorId] ?? []), option],
  }
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

async function submit() {
  saveError.value = null
  saveTraceId.value = null
  const decor = picked.value
  if (!decor || pendingRows.value.length === 0) {
    saveError.value = t('inventory.attach.selectFormats')
    return
  }
  const badPrices = new Set<string>()
  const items: BranchMaterialAttachItem[] = []
  for (const row of pendingRows.value) {
    const price = parsePrice(priceOf(row.key))
    if (price === null) {
      badPrices.add(row.key)
      continue
    }
    items.push({ decor_format_id: row.key, price_tiyin: price })
  }
  priceErrorKeys.value = badPrices
  if (badPrices.size > 0) {
    saveError.value = t('catalog.form.priceInvalid')
    return
  }
  saving.value = true
  try {
    const result = await workshop.attachBranchMaterials(props.branchId, { items })
    // The sheet is done: the caller closes it and reloads the table, and
    // «+ Material» is the way to the next decor.
    emit('attached', {
      created: result.created.length,
      skipped: result.skipped.length,
      decorLabel: decor.label,
    })
  } catch (caught) {
    saveError.value = apiMessage(caught) ?? t('inventory.attach.saveFailed')
    saveTraceId.value = apiTraceId(caught)
  } finally {
    saving.value = false
  }
}

function reset() {
  step.value = 'pick'
  createSeedName.value = ''
  createError.value = null
  search.value = ''
  manufacturerFilter.value = 'all'
  turFilter.value = 'all'
  loadError.value = false
  picked.value = null
  // A reopened sheet may be pointed at another branch, where `carried` differs.
  formatsByDecor.value = {}
  priceInputs.clear()
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
    ref="modalRef"
    :open="open"
    :title="stepTitle"
    max-width="max-w-4xl"
    @close="emit('close')"
  >
    <!-- The filters never scroll away: they are how the list on the other side
         of them is changed (owner item 3, §3.1). -->
    <template v-if="step === 'pick'" #head>
      <!-- One row of three from `sm` up, rather than `sm:grid-cols-2
           lg:grid-cols-3`: `--breakpoint-lg` is redefined in `main.css`, which
           re-registers the variant AFTER `sm` in Tailwind v4's cascade order,
           so the two-column rule wins at every width and the pair silently
           never reaches three. The fixed head is the one place that costs a
           whole row of modal height, so it states the layout once. -->
      <div class="grid gap-3 sm:grid-cols-3">
        <label class="field !mb-0">
          <span>{{ $t('inventory.attach.searchLabel') }}</span>
          <input
            v-model="search"
            class="mp-input"
            :placeholder="$t('inventory.attach.searchPlaceholder')"
          />
        </label>
        <FormSelect
          v-model="turFilter"
          class="!mb-0"
          :label="$t('inventory.attach.turLabel')"
          :options="turOptions"
        />
        <FormSelect
          v-model="manufacturerFilter"
          class="!mb-0"
          :label="$t('inventory.attach.manufacturerLabel')"
          :options="manufacturerOptions"
        />
      </div>
    </template>

    <!-- Step 2's identity bar: which decor these o'lchamlar belong to, and the
         way back to the list. Fixed, like the filters it replaces. -->
    <template v-else-if="step === 'price' && picked" #head>
      <div class="flex min-w-0 items-center gap-3">
        <button
          type="button"
          class="mp-row-icon shrink-0"
          :aria-label="$t('inventory.attach.back')"
          @click="backToPick"
        >
          <AppIcon name="chevron-left" />
        </button>
        <AuthFileImage
          v-if="picked.image_file_id"
          :file-id="picked.image_file_id"
          :alt="picked.label"
          class="size-[34px] shrink-0 rounded-md object-cover"
        />
        <span v-else class="sw shrink-0" :class="materialSwatchClass(swatchSource(picked))" />
        <span class="grid min-w-0 gap-0.5">
          <span class="flex min-w-0 flex-wrap items-center gap-1.5">
            <span class="break-words text-sm font-extrabold text-ink">{{ picked.label }}</span>
            <span v-if="picked.own" class="mp-chip shrink-0">
              {{ $t('inventory.attach.ownBadge') }}
            </span>
          </span>
          <small class="break-words text-ink-muted">{{ picked.manufacturer_name }}</small>
        </span>
      </div>
    </template>

    <!-- Step 1 — pick ONE decor. Photo-first: an operator recognises a decor by
         its surface long before its code. Every row is a door. -->
    <div v-if="step === 'pick'" class="grid gap-3">
      <div v-if="loading" class="grid gap-3 p-2" aria-live="polite">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
      <div v-else-if="loadError" class="st-error">
        <h3>{{ $t('inventory.attach.loadErrorTitle') }}</h3>
        <p>{{ $t('inventory.attach.loadErrorBody') }}</p>
      </div>
      <!-- The empty state carries the create action itself, and the footer's
           copy of it is hidden while it shows: one control, not two, on the one
           screen where the whole point is that nothing was found (QAD-182). -->
      <div v-else-if="showEmptyState" class="st-empty !py-8">
        <div class="client-empty-icon"><AppIcon name="layers" /></div>
        <h3>{{ $t('inventory.attach.emptyTitle') }}</h3>
        <p>{{ $t('inventory.attach.emptyBody') }}</p>
        <button type="button" class="mp-button mp-button-primary mt-3" @click="openCreateForm">
          {{ $t('inventory.attach.newDecor') }}
        </button>
      </div>
      <template v-else>
        <ul class="grid gap-2 sm:grid-cols-2">
          <li v-for="option in options" :key="option.decor.id" class="min-w-0">
            <!-- One control per row, filling it: the row IS the choice, so
                 there is nothing beside it that could take the press and mean
                 something else. -->
            <button
              type="button"
              class="flex w-full min-w-0 cursor-pointer items-center gap-3 rounded-md border border-hairline bg-elevated px-3 py-2 text-left transition-colors hover:border-accent hover:bg-sunk"
              @click="openDecor(option.decor)"
            >
              <AuthFileImage
                v-if="option.decor.image_file_id"
                :file-id="option.decor.image_file_id"
                :alt="option.decor.label"
                class="size-[34px] shrink-0 rounded-md object-cover"
              />
              <span
                v-else
                class="sw shrink-0"
                :class="materialSwatchClass(swatchSource(option.decor))"
              />
              <span class="grid min-w-0 flex-1 gap-0.5">
                <span class="flex min-w-0 flex-wrap items-center gap-1.5">
                  <span class="break-words text-sm font-bold text-ink">
                    {{ option.decor.label }}
                  </span>
                  <!-- A row only this workshop can see. Quiet on purpose: it is
                       provenance, not a status. -->
                  <span v-if="option.decor.own" class="mp-chip shrink-0">
                    {{ $t('inventory.attach.ownBadge') }}
                  </span>
                </span>
                <small class="break-words text-ink-muted">
                  {{ option.decor.manufacturer_name }}
                </small>
              </span>
              <!-- Text, not a chip: it answers "how many sizes are behind this
                   door", and a chip here used to be a second control on a row
                   that now has exactly one. -->
              <span class="shrink-0 text-xs text-ink-muted">{{ formatCountText(option) }}</span>
              <AppIcon name="chevron-right" class="size-[15px] flex-none text-ink-muted" />
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
    </div>

    <!-- Step «create» — the workshop enters what the library lacks. Its own
         component: the sheet routes, it does not grow a form. -->
    <div v-else-if="step === 'create'" class="grid gap-3">
      <p
        v-if="createError"
        class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
      >
        {{ createError }}
      </p>
      <BranchDecorCreateForm
        ref="createFormRef"
        :branch-id="branchId"
        :initial-name="createSeedName"
        :actions="false"
        @created="onDecorCreated"
        @back="backToPick"
      />
    </div>

    <!-- Step 2 — one decor's o'lchamlar, each with the price this branch
         charges. Carried rows stay in the table, disabled: hiding them would
         leave the branch wondering whether the size exists at all, which is the
         exact question this step is here to answer. -->
    <div v-else class="grid gap-3">
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
        <p v-if="noFormats" class="text-sm text-ink-muted">
          {{ $t('inventory.attach.noFormats') }}
        </p>
        <div v-else class="table-wrap">
          <table class="tbl tbl-fluid">
            <thead>
              <tr>
                <th class="w-full">{{ $t('inventory.attach.columnFormat') }}</th>
                <th class="nowrap right">{{ $t('inventory.attach.columnPrice') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.key">
                <td>
                  <label
                    class="flex min-w-0 items-center gap-2"
                    :class="row.carried ? 'cursor-default' : 'cursor-pointer'"
                  >
                    <input
                      type="checkbox"
                      class="mp-checkbox shrink-0"
                      :checked="isChecked(row.key)"
                      :disabled="row.carried"
                      @change="toggleFormat(row)"
                    />
                    <span
                      class="min-w-0 break-words text-sm"
                      :class="row.carried ? 'text-ink-muted' : 'text-ink'"
                    >
                      {{ row.label }}
                    </span>
                  </label>
                </td>
                <td class="nowrap right">
                  <!-- A carried row has no price to type here: the o'lcham is
                       already on the shelf, and its price is edited in Materiallar. -->
                  <template v-if="row.carried">
                    <span
                      v-if="carriedNoteKey === row.key"
                      class="text-sm font-bold text-accent-deep"
                      aria-live="polite"
                    >
                      {{ $t('inventory.attach.carriedNow') }}
                    </span>
                    <span v-else class="text-sm text-ink-muted">
                      {{ $t('inventory.attach.carried') }}
                    </span>
                  </template>
                  <template v-else>
                    <input
                      :ref="(el) => setPriceInput(row.key, el)"
                      class="mp-input w-28 text-right"
                      inputmode="numeric"
                      :disabled="!isChecked(row.key)"
                      :value="priceOf(row.key)"
                      :aria-label="$t('inventory.attach.priceAria', { name: row.label })"
                      :aria-invalid="priceErrorKeys.has(row.key) || undefined"
                      :class="priceErrorKeys.has(row.key) ? '!border-danger' : ''"
                      @input="setPrice(row.key, ($event.target as HTMLInputElement).value)"
                    />
                    <small class="block text-ink-muted">{{ priceUnit(row.type) }}</small>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- The size the library does not have, added here rather than waited
             for. Works on a library decor and on an own one alike: the size is
             the workshop's fact either way. -->
        <div class="grid gap-2">
          <button
            type="button"
            class="justify-self-start text-xs font-bold text-accent-deep hover:underline"
            :aria-expanded="composerOpen"
            @click="toggleComposer"
          >
            {{ $t('inventory.attach.addOtherFormat') }}
          </button>
          <BranchDecorFormatPicker
            v-if="composerOpen"
            :initial-type="composerType"
            :busy="composerBusy"
            :error="composerError"
            @add="addDecorFormat"
          />
        </div>

        <p class="text-xs text-ink-muted">{{ $t('inventory.attach.priceOptional') }}</p>
      </template>

      <p v-if="saveError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
        {{ saveError }}<template v-if="saveTraceId"> · trace_id: {{ saveTraceId }}</template>
      </p>
    </div>

    <template #footer>
      <template v-if="step === 'pick'">
        <!-- Quiet, and beside «Bekor» rather than behind a search: the door has
             to be findable without first proving the library lacks the decor. It
             steps aside when the empty state offers the same action. -->
        <button
          v-if="!showEmptyState"
          type="button"
          class="mp-button mp-button-outline"
          @click="openCreateForm"
        >
          {{ $t('inventory.attach.newDecor') }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="emit('close')">
          {{ $t('inventory.action.cancel') }}
        </button>
      </template>
      <template v-else-if="step === 'create'">
        <button
          type="button"
          class="mp-button mp-button-primary"
          :disabled="createSaving"
          @click="createFormRef?.submit()"
        >
          {{ createSaving ? $t('inventory.attach.saving') : $t('inventory.attach.createSubmit') }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="backToPick">
          {{ $t('inventory.attach.back') }}
        </button>
      </template>
      <template v-else>
        <button
          type="button"
          class="mp-button mp-button-primary"
          :disabled="saving || pendingRows.length === 0"
          @click="submit"
        >
          {{
            saving
              ? $t('inventory.attach.saving')
              : $t('inventory.attach.submit', { n: pendingRows.length })
          }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="backToPick">
          {{ $t('inventory.attach.back') }}
        </button>
      </template>
    </template>
  </AppModal>
</template>
