<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { apiTraceId, ApiError } from '@/shared/api/client'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { sanitizeMoneyInput, sanitizeQuantityInput } from '@/shared/app/inputSanitizers'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import AppModal from '@/shared/components/AppModal.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import FormSelect from '@/shared/components/FormSelect.vue'
import { parseDisplayQuantity, parseSomToTiyin } from '@/shared/formatters'
import type { Material, MaterialKind } from '@/shared/stores/admin'
import {
  defaultLowStockThreshold,
  thresholdUnit,
  lowStockThresholdColumn,
  lowStockThresholdHint,
  lowStockThresholdLabel,
} from '@/shared/app/lowStockThreshold'
import { useWorkshopStore, type BranchMaterialBulkItem } from '@/shared/stores/workshop'

const props = defineProps<{ open: boolean; branchId: string }>()
const emit = defineEmits<{ close: []; attached: [count: number] }>()

// Server-side page size for the picker. "Filtrdagi hammasi" pages past it using
// the endpoint's `total`, so this bounds the DOM, not the selection.
const PAGE_LIMIT = 100

const { t } = useI18n()
const workshop = useWorkshopStore()

const step = ref<1 | 2>(1)
const search = ref('')
const manufacturerFilter = ref<string | null>('all')
const kindFilter = ref<string | null>('all')
const thicknessFilter = ref<string | null>('all')
const options = ref<Material[]>([])
const total = ref(0)
const loading = ref(false)
const loadError = ref(false)
const selectAllPending = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveTraceId = ref<string | null>(null)
const bulkFill = reactive({ price: '', threshold: '' })

interface SelectedRow {
  material: Material
  price: string
  threshold: string
  priceError: boolean
  thresholdError: boolean
}

// Ids matching the current filter. Until "Filtrdagi hammasi" pages through the
// rest, only the loaded page is known — `filterComplete` says which it is, so the
// master checkbox never claims to cover rows nobody has fetched.
const filterIds = ref<string[]>([])
const filterComplete = ref(false)

// Keyed by material id so the selection survives filter changes, paging, and
// the step-1 ⇄ step-2 round trip.
const selected = ref(new Map<string, SelectedRow>())
const selectedRows = computed(() => [...selected.value.values()])
const selectedCount = computed(() => selected.value.size)

// `FormSelect`, not `ProjectDropdown`: the latter teleports its panel at z-50 and
// would render behind the modal layer (z-80) — see web/DESIGN.md → Shapes.
const manufacturerOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: t('inventory.attach.manufacturerAll') },
  ...workshop.catalogFilters.manufacturers.map((row) => ({ value: row.id, label: row.name })),
])
const kindOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: t('inventory.attach.kindAll') },
  { value: 'panel', label: t('inventory.attach.kindPanel') },
  { value: 'edge', label: t('inventory.attach.kindEdge') },
])
const thicknessOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: t('inventory.attach.thicknessAll') },
  ...workshop.catalogFilters.thicknesses.map((value) => ({
    value,
    label: t('inventory.attach.thicknessOption', { value }),
  })),
])

// The master checkbox reflects the filter, not the page: it is checked once every
// material matching the current filter sits in the selection. With more matches
// than one page holds, that is only knowable after the select-all pass has paged
// through them — before that the box stays unchecked rather than lying.
const filterFullySelected = computed(
  () =>
    total.value > 0 &&
    filterComplete.value &&
    filterIds.value.every((id) => selected.value.has(id)),
)
const mixedKinds = computed(() => {
  const kinds = new Set(selectedRows.value.map((row) => row.material.kind))
  return kinds.size > 1
})

// Kind and dimensions only — the generated material name already carries the
// manufacturer, decor and colour, and repeating them here cost three extra
// wrapped lines per row on a phone.
function optionMeta(material: Material) {
  if (material.kind === 'edge') {
    return t('inventory.attach.metaEdge', {
      thickness: material.thickness_mm,
      width: material.edge_width_mm,
    })
  }
  const type = material.type ? material.type.toUpperCase() : t('inventory.attach.panelTypeFallback')
  return t('inventory.attach.metaPanel', {
    type,
    length: material.panel_length_mm,
    width: material.panel_width_mm,
    thickness: material.thickness_mm,
  })
}

function priceUnit(kind: MaterialKind) {
  return kind === 'edge'
    ? t('inventory.attach.priceUnitMetre')
    : t('inventory.attach.priceUnitSheet')
}

function filters(offset = 0) {
  return {
    search: search.value,
    kind: kindFilter.value === 'all' ? null : (kindFilter.value as MaterialKind),
    manufacturer_id: manufacturerFilter.value === 'all' ? null : manufacturerFilter.value,
    thickness_mm: thicknessFilter.value === 'all' ? null : thicknessFilter.value,
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
    options.value = page.items.map((option) => option.material)
    total.value = page.total
    filterIds.value = options.value.map((material) => material.id)
    filterComplete.value = options.value.length >= page.total
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

function newRow(material: Material): SelectedRow {
  return {
    material,
    price: '',
    threshold: String(defaultLowStockThreshold(material.kind)),
    priceError: false,
    thresholdError: false,
  }
}

function toggleMaterial(material: Material) {
  const next = new Map(selected.value)
  if (next.has(material.id)) next.delete(material.id)
  else next.set(material.id, newRow(material))
  selected.value = next
}

// "Filtrdagi hammasi" must select every match, not just the loaded page — page
// through the rest server-side before adding them all in one go.
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
    const collected: Material[] = [...options.value]
    while (collected.length < total.value) {
      const page = await workshop.fetchCatalogOptions(props.branchId, filters(collected.length))
      if (page.items.length === 0) break
      collected.push(...page.items.map((option) => option.material))
    }
    const next = new Map(selected.value)
    for (const material of collected) {
      if (!next.has(material.id)) next.set(material.id, newRow(material))
    }
    selected.value = next
    filterIds.value = collected.map((material) => material.id)
    filterComplete.value = true
  } catch {
    loadError.value = true
  } finally {
    selectAllPending.value = false
  }
}

function removeSelected(materialId: string) {
  const next = new Map(selected.value)
  next.delete(materialId)
  selected.value = next
  if (next.size === 0) step.value = 1
}

function applyBulkFill() {
  const next = new Map(selected.value)
  for (const [id, row] of next) {
    next.set(id, {
      ...row,
      price: bulkFill.price.trim() ? bulkFill.price : row.price,
      threshold: bulkFill.threshold.trim() ? bulkFill.threshold : row.threshold,
      priceError: false,
      thresholdError: false,
    })
  }
  selected.value = next
}

function apiMessage(error: unknown): string | null {
  if (!(error instanceof ApiError) || typeof error.body !== 'object' || error.body === null) {
    return null
  }
  const message = (error.body as { message?: unknown }).message
  return typeof message === 'string' && message.trim() ? message : null
}

function rowPriceTiyin(row: SelectedRow) {
  return parseSomToTiyin(row.price)
}

function rowThreshold(row: SelectedRow) {
  const parsed = parseDisplayQuantity(row.threshold, row.material.kind === 'edge' ? 'm' : 'pcs')
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
}

async function submit() {
  saveError.value = null
  saveTraceId.value = null
  const items: BranchMaterialBulkItem[] = []
  let missingPrice = false
  let badThreshold = false
  const next = new Map(selected.value)
  for (const [id, row] of next) {
    const price = rowPriceTiyin(row)
    const threshold = rowThreshold(row)
    next.set(id, { ...row, priceError: price === null, thresholdError: threshold === null })
    if (price === null) missingPrice = true
    if (threshold === null) badThreshold = true
    if (price === null || threshold === null) continue
    items.push({ material_id: id, price_tiyin: price, min_stock: threshold })
  }
  selected.value = next
  if (missingPrice || badThreshold) {
    // Name the field that actually failed — over 40 rows, "something is wrong"
    // leaves the user hunting.
    saveError.value = missingPrice
      ? t('inventory.attach.priceRequired')
      : t('inventory.attach.thresholdInvalid')
    return
  }
  saving.value = true
  try {
    const result = await workshop.addBranchMaterialsBulk(props.branchId, items)
    emit('attached', result.created.length)
  } catch (caught) {
    // The bulk endpoint rejects the whole batch naming the offending material —
    // surface that message verbatim rather than a generic failure.
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
  kindFilter.value = 'all'
  thicknessFilter.value = 'all'
  selected.value = new Map()
  bulkFill.price = ''
  bulkFill.threshold = ''
  saveError.value = null
  saveTraceId.value = null
  loadError.value = false
  filterIds.value = []
  filterComplete.value = false
}

let searchTimer: number | undefined
watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void loadOptions(), SEARCH_DEBOUNCE_MS)
})
watch([manufacturerFilter, kindFilter, thicknessFilter], () => void loadOptions())

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

function sanitizeRowPrice(row: SelectedRow) {
  const clean = sanitizeMoneyInput(row.price)
  if (clean !== row.price) row.price = clean
  row.priceError = false
}

function sanitizeRowThreshold(row: SelectedRow) {
  const clean = sanitizeQuantityInput(row.threshold)
  if (clean !== row.threshold) row.threshold = clean
  row.thresholdError = false
}
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
    <div v-if="step === 1" class="grid gap-3">
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label class="field">
          <span>{{ $t('inventory.attach.searchLabel') }}</span>
          <input
            v-model="search"
            class="mp-input"
            :placeholder="$t('inventory.attach.searchPlaceholder')"
          />
        </label>
        <FormSelect
          v-model="manufacturerFilter"
          :label="$t('inventory.attach.manufacturerLabel')"
          :options="manufacturerOptions"
        />
        <FormSelect
          v-model="kindFilter"
          :label="$t('inventory.attach.kindLabel')"
          :options="kindOptions"
        />
        <FormSelect
          v-model="thicknessFilter"
          :label="$t('inventory.attach.thicknessLabel')"
          :options="thicknessOptions"
        />
      </div>

      <div
        class="flex flex-wrap items-center justify-between gap-3 rounded-md border border-hairline bg-sunk px-3 py-2"
      >
        <label class="flex min-w-0 items-center gap-2 text-sm font-bold text-ink">
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
        <span class="text-sm font-bold text-ink-muted">{{
          $t('inventory.attach.selectedCount', { n: selectedCount }, selectedCount)
        }}</span>
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
      <ul v-else class="grid max-h-[42dvh] gap-1 overflow-y-auto overflow-x-hidden">
        <li v-for="material in options" :key="material.id" class="min-w-0">
          <label
            class="flex min-w-0 cursor-pointer items-start gap-3 rounded-md px-2 py-2 hover:bg-accent-soft"
          >
            <input
              type="checkbox"
              class="mt-0.5 size-4 shrink-0 accent-accent"
              :checked="selected.has(material.id)"
              @change="toggleMaterial(material)"
            />
            <span class="sw mt-0.5 shrink-0" :class="materialSwatchClass(material)"></span>
            <span class="grid min-w-0 gap-0.5">
              <span class="break-words text-sm font-bold text-ink">{{ material.name }}</span>
              <small class="break-words text-ink-muted">{{ optionMeta(material) }}</small>
            </span>
          </label>
        </li>
      </ul>

      <div class="flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
        <button
          type="button"
          class="mp-button mp-button-primary"
          :disabled="selectedCount === 0"
          @click="step = 2"
        >
          {{ $t('inventory.attach.continue', { count: selectedCount }) }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="emit('close')">
          {{ $t('inventory.action.cancel') }}
        </button>
      </div>
    </div>

    <div v-else class="grid gap-3">
      <div class="grid gap-2 rounded-md border border-hairline bg-sunk px-3 py-3">
        <div class="flex flex-wrap items-end gap-2">
          <span class="self-center text-sm font-bold text-ink">{{
            $t('inventory.attach.bulkAll')
          }}</span>
          <label class="grid min-w-0 flex-1 basis-40 gap-1">
            <span class="text-xs font-bold text-ink-muted">{{
              $t('inventory.attach.priceLabel')
            }}</span>
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
        <small class="text-ink-muted">
          {{ $t('inventory.attach.bulkHint') }}
          <template v-if="mixedKinds">
            {{ $t('inventory.attach.mixedKindsHint') }}
          </template>
        </small>
      </div>

      <div class="table-wrap">
        <table class="tbl tbl-fluid">
          <thead>
            <tr>
              <th class="w-full">{{ $t('inventory.attach.columnMaterial') }}</th>
              <th class="nowrap right">{{ $t('inventory.attach.priceLabel') }}</th>
              <th class="nowrap right">{{ lowStockThresholdColumn() }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in selectedRows" :key="row.material.id">
              <td>
                <div class="grid min-w-0 gap-0.5">
                  <span class="break-words font-bold text-ink">{{ row.material.name }}</span>
                  <small class="break-words text-ink-muted">{{ optionMeta(row.material) }}</small>
                </div>
              </td>
              <td class="nowrap right">
                <input
                  v-model="row.price"
                  class="mp-input w-28 text-right"
                  inputmode="numeric"
                  :aria-label="$t('inventory.attach.priceAria', { name: row.material.name })"
                  :aria-invalid="row.priceError || undefined"
                  :class="row.priceError ? '!border-danger' : ''"
                  @input="sanitizeRowPrice(row)"
                />
                <small class="block text-ink-muted">{{ priceUnit(row.material.kind) }}</small>
              </td>
              <td class="nowrap right">
                <input
                  v-model="row.threshold"
                  class="mp-input w-20 text-right"
                  inputmode="decimal"
                  :aria-label="$t('inventory.attach.thresholdAria', { name: row.material.name })"
                  :aria-invalid="row.thresholdError || undefined"
                  :class="row.thresholdError ? '!border-danger' : ''"
                  @input="sanitizeRowThreshold(row)"
                />
                <small class="block text-ink-muted">{{ thresholdUnit(row.material.kind) }}</small>
              </td>
              <td class="nowrap right">
                <button
                  type="button"
                  class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  :aria-label="$t('inventory.attach.removeAria', { name: row.material.name })"
                  @click="removeSelected(row.material.id)"
                >
                  {{ $t('inventory.attach.remove') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="text-xs text-ink-muted">
        {{ lowStockThresholdLabel() }} — {{ lowStockThresholdHint() }}
      </p>

      <p v-if="saveError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
        {{ saveError }}<template v-if="saveTraceId"> · trace_id: {{ saveTraceId }}</template>
      </p>

      <div class="flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
        <button
          type="button"
          class="mp-button mp-button-primary"
          :disabled="saving || selectedCount === 0"
          @click="submit"
        >
          {{
            saving
              ? $t('inventory.attach.saving')
              : $t('inventory.attach.submit', { n: selectedCount }, selectedCount)
          }}
        </button>
        <button type="button" class="mp-button mp-button-outline" @click="step = 1">
          {{ $t('inventory.attach.back') }}
        </button>
      </div>
    </div>
  </AppModal>
</template>
