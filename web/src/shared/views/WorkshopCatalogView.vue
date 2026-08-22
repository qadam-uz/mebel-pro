<script setup lang="ts">
/**
 * "Material katalogi" — what this branch carries, grouped by decor.
 *
 * The catalog reshape split identity (a platform decor) from format (a branch
 * row), so a flat list repeated the same decor name once per thickness. The table
 * groups instead: one photo + identity line per decor, its formats as indented
 * rows beneath. A format with `price_unset` carries a "Narx yo'q" pill — it is
 * hidden from the client-facing catalog until it is priced, and this is the only
 * screen where that gap is fixable.
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { traceLine, traceSuffix } from '@/shared/app/errorTrace'
import { sanitizeMoneyInput, sanitizeQuantityInput } from '@/shared/app/inputSanitizers'
import { DECOR_TYPES, decorTypeLabel, formatMm, isTape } from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import type { DropdownOption } from '@/shared/app/roleConfig'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import {
  thresholdUnit,
  lowStockThresholdColumn,
  lowStockThresholdHint,
  lowStockThresholdLabel,
} from '@/shared/app/lowStockThreshold'
import AppModal from '@/shared/components/AppModal.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import BranchMaterialAttachSheet from '@/shared/components/BranchMaterialAttachSheet.vue'
import FilterStatus from '@/shared/components/FilterStatus.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useOnboardingContinuation } from '@/shared/composables/useOnboardingContinuation'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatStockQuantity,
  formatTiyin,
  parseDisplayQuantity,
  parseSomToTiyin,
} from '@/shared/formatters'
import type { Decor, DecorType, MaterialStatus } from '@/shared/stores/admin'
import {
  useWorkshopStore,
  type BranchMaterial,
  type BranchMaterialFilters,
} from '@/shared/stores/workshop'

const permissions = useWorkshopPermissions()
const workshop = useWorkshopStore()
const toast = useToast()
const route = useRoute()
const { t } = useI18n()
const { notifyProgress } = useOnboardingContinuation()
const statusFilter = ref<'all' | MaterialStatus>('all')
const turFilter = ref<'all' | DecorType>('all')
const search = ref('')

// Same defect as Ombor (QAD-182): with a search on, the branch reported it held
// no materials at all — and offered an add button that would not have helped.
const catalogFiltered = computed(
  () => search.value.trim().length > 0 || turFilter.value !== 'all' || statusFilter.value !== 'all',
)

// The bar-level reset appears from the second active filter on: with one, it
// would sit next to that filter's own clear and do the same thing.
const activeCatalogFilterCount = computed(
  () =>
    (search.value.trim() ? 1 : 0) +
    (turFilter.value === 'all' ? 0 : 1) +
    (statusFilter.value === 'all' ? 0 : 1),
)

function resetCatalogFilters() {
  search.value = ''
  turFilter.value = 'all'
  statusFilter.value = 'all'
}
const rowActionId = ref<string | null>(null)
const rowActionError = ref<string | null>(null)
const rowActionTraceId = ref<string | null>(null)
const materialSaving = ref(false)
const materialError = ref<string | null>(null)
const editingBranchMaterialId = ref<string | null>(null)
const materialModalOpen = ref(false)
const attachSheetOpen = ref(false)
const collapsedDecorIds = ref<Set<string>>(new Set())
let searchTimer: number | undefined
const materialForm = reactive({
  // Deliberately empty, not '0': a pre-filled 0 satisfies `required` and lets a
  // hurried owner publish a 0 so'm material to the client-facing catalog.
  priceTiyin: '',
  minStock: '',
})
const priceFieldError = ref<string | null>(null)
const minStockFieldError = ref<string | null>(null)
const priceTiyinParsed = computed(() => parseSomToTiyin(materialForm.priceTiyin))

const canUseCatalog = computed(() => permissions.can(p.manageCatalog))
const accessibleBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, [p.manageCatalog]),
)
// Branch is driven by the topbar context picker (AppShell); the page follows it
// and falls back to the first accessible branch until context is set.
const selectedBranchId = computed(() => {
  const context = workshop.selectedBranchContext
  if (context && accessibleBranches.value.some((branch) => branch.id === context)) return context
  return accessibleBranches.value[0]?.id ?? ''
})
// The Qoldiq column is stock, and `manage_catalog` alone does not grant it.
const canReadStock = computed(() =>
  permissions.canOnBranch(p.manageInventory, selectedBranchId.value),
)
// Computed, not a plain array: a `const` built at setup would keep the labels of
// whatever locale was active when the page mounted.
const statusOptions = computed<DropdownOption[]>(() => [
  { value: 'all', label: t('catalog.filter.statusAll') },
  { value: 'active', label: t('catalog.status.active'), dot: 'success' },
  { value: 'inactive', label: t('catalog.status.inactive'), dot: 'muted' },
])
// All seven wire values, including `dsp` — it shares the `LDSP` label but is a
// distinct enum member, and omitting it would leave those decors unfilterable.
const turOptions = computed<DropdownOption[]>(() => [
  { value: 'all', label: t('catalog.filter.turAll') },
  ...DECOR_TYPES.map((value) => ({ value, label: decorTypeLabel(value) })),
])
const editingBranchMaterial = computed(
  () => workshop.branchMaterials.find((row) => row.id === editingBranchMaterialId.value) ?? null,
)
// The threshold's own copy lives in `lowStockThreshold.ts` so the attach sheet,
// this form and the table can never name it differently.
const thresholdLabel = computed(() => lowStockThresholdLabel())
const thresholdColumn = computed(() => lowStockThresholdColumn())
const thresholdHint = computed(() => lowStockThresholdHint())
const materialThresholdUnit = computed(() => {
  const row = editingBranchMaterial.value
  return row ? thresholdUnit(row.decor_format.type) : t('catalog.unit.piece')
})
const materialPriceUnit = computed(() => {
  const row = editingBranchMaterial.value
  return row ? priceUnit(row.decor_format.type) : ''
})

interface DecorGroup {
  decor: Decor
  rows: BranchMaterial[]
}

// Grouped in server order, first appearance wins: the list is paginated, so the
// grouping must never reorder rows or a "load more" would shuffle the table.
const decorGroups = computed<DecorGroup[]>(() => {
  const groups = new Map<string, DecorGroup>()
  for (const row of workshop.branchMaterials) {
    const group = groups.get(row.decor_format.decor_id)
    if (group) group.rows.push(row)
    else groups.set(row.decor_format.decor_id, { decor: row.decor, rows: [row] })
  }
  return [...groups.values()]
})

// On-hand comes from the branch's stock list, keyed by branch material. A stock
// row can be missing (nothing ever arrived), which reads as "—", not as 0.
const onHandByMaterialId = computed(
  () =>
    new Map(
      workshop.stockItems.map((item) => [
        item.branch_material_id,
        { onHand: item.on_hand, unit: item.display_unit, low: item.is_low_stock },
      ]),
    ),
)

function routeSearchValue() {
  const value = route.query.search
  return typeof value === 'string' ? value : ''
}

function applyRouteSearch() {
  const value = routeSearchValue()
  if (value !== search.value) search.value = value
}

/** `2800×2070×18 mm` for a panel, `0.4×19 mm` for a tape. */
function formatLabel(row: BranchMaterial) {
  const format = row.decor_format
  const thickness = formatMm(format.thickness_mm)
  if (isTape(format.type)) {
    return format.tape_width_mm !== null
      ? t('catalog.meta.tapeFormat', { thickness, width: format.tape_width_mm })
      : `${thickness} mm`
  }
  return format.length_mm !== null && format.width_mm !== null
    ? t('catalog.meta.panelFormat', {
        length: format.length_mm,
        width: format.width_mm,
        thickness,
      })
    : `${thickness} mm`
}

function priceUnit(type: DecorType) {
  return isTape(type) ? t('catalog.unit.perMetre') : t('catalog.unit.perPanel')
}

// Split "2.5 m" / "12 dona" so the unit can sit on its own muted line and the
// digits stay aligned on the column's right edge.
function thresholdParts(row: BranchMaterial) {
  const text = formatStockQuantity(row.min_stock, thresholdUnit(row.decor_format.type))
  const splitAt = text.lastIndexOf(' ')
  return { value: text.slice(0, splitAt), unit: text.slice(splitAt + 1) }
}

function onHandText(row: BranchMaterial) {
  const stock = onHandByMaterialId.value.get(row.id)
  return stock ? formatStockQuantity(stock.onHand, stock.unit) : '—'
}

function isLowStock(row: BranchMaterial) {
  return onHandByMaterialId.value.get(row.id)?.low ?? false
}

function swatchSource(decor: Decor) {
  return { id: decor.id, name: decor.name, code: decor.code }
}

function isCollapsed(decorId: string) {
  return collapsedDecorIds.value.has(decorId)
}

function toggleDecor(decorId: string) {
  const next = new Set(collapsedDecorIds.value)
  if (next.has(decorId)) next.delete(decorId)
  else next.add(decorId)
  collapsedDecorIds.value = next
}

function tableFilters(offset = 0): BranchMaterialFilters {
  return {
    status: statusFilter.value === 'all' ? null : statusFilter.value,
    type: turFilter.value === 'all' ? null : turFilter.value,
    search: search.value,
    offset,
  }
}

async function loadBranchTable(offset = 0) {
  if (!selectedBranchId.value) return
  rowActionError.value = null
  rowActionTraceId.value = null
  await workshop
    .loadBranchMaterials(selectedBranchId.value, tableFilters(offset))
    .catch(() => undefined)
}

// Full refresh (mount, branch switch, after save): reset the table to page one.
// Stock rides along so the Qoldiq column has numbers; the attach sheet loads its
// own decor options when it opens.
function refreshCatalog() {
  if (!selectedBranchId.value) return Promise.resolve()
  return Promise.all([
    loadBranchTable(0),
    // Stock is a *separate* entitlement: `manage_catalog` lets you read the
    // catalog but not the branch's stock, so asking anyway is a guaranteed 403
    // on page load. The Qoldiq column falls back to "—", which is the truth for
    // someone who may not see stock.
    canReadStock.value
      ? workshop.loadStock(selectedBranchId.value).catch(() => undefined)
      : Promise.resolve(),
  ])
}

function loadMoreBranchMaterials() {
  void loadBranchTable(workshop.branchMaterials.length)
}

async function saveBranchMaterial() {
  if (!selectedBranchId.value || !editingBranchMaterialId.value) return
  materialSaving.value = true
  materialError.value = null
  priceFieldError.value = null
  minStockFieldError.value = null
  try {
    const row = editingBranchMaterial.value
    const minStock = parseDisplayQuantity(
      materialForm.minStock,
      row && isTape(row.decor_format.type) ? 'm' : 'pcs',
    )
    // The price field is entered in so'm; the backend stores tiyin (1 so'm = 100
    // tiyin). null covers both unparseable input and 0 — a 0 so'm material must
    // never reach the client catalog by accident.
    const priceTiyin = priceTiyinParsed.value
    if (priceTiyin === null) {
      priceFieldError.value = t('catalog.form.priceInvalid')
      return
    }
    if (!Number.isFinite(minStock) || minStock < 0) {
      minStockFieldError.value = t('catalog.form.thresholdInvalid')
      return
    }
    await workshop.updateBranchMaterial(selectedBranchId.value, editingBranchMaterialId.value, {
      price_tiyin: priceTiyin,
      min_stock: minStock,
    })
    resetMaterialForm()
    materialModalOpen.value = false
    await refreshCatalog()
    toast.success(t('catalog.toast.settingsSaved'))
  } catch {
    materialError.value = 'branch_material_save_failed'
  } finally {
    materialSaving.value = false
  }
}

function openAttachSheet() {
  attachSheetOpen.value = true
}

// The attach call is not all-or-nothing: a format the branch already carries
// comes back under `skipped`. That is a notice, never an error.
async function onMaterialsAttached(result: { created: number; skipped: number }) {
  attachSheetOpen.value = false
  await refreshCatalog()
  if (result.skipped > 0) {
    toast.warn(t('inventory.attach.resultSkipped', { n: result.skipped }))
  }
  if (result.created === 0) return
  if (!(await notifyProgress())) {
    toast.success(t('catalog.toast.attached', { n: result.created }, result.created))
  }
}

function editBranchMaterial(row: BranchMaterial) {
  editingBranchMaterialId.value = row.id
  // An unpriced format opens with an empty field, not "0" — the operator is here
  // to set a price, and a prefilled 0 is the value we are asking them to replace.
  materialForm.priceTiyin = row.price_unset ? '' : String(row.price_tiyin / 100)
  // Existing rows keep whatever threshold they were saved with — the per-type
  // defaults apply to new attachments only (no backfill, QAD-159).
  materialForm.minStock = isTape(row.decor_format.type)
    ? String(row.min_stock / 1000)
    : String(row.min_stock)
  materialError.value = null
  materialModalOpen.value = true
}

function closeMaterialModal() {
  materialModalOpen.value = false
  resetMaterialForm()
}

function resetMaterialForm() {
  editingBranchMaterialId.value = null
  materialForm.priceTiyin = ''
  materialForm.minStock = ''
  priceFieldError.value = null
  minStockFieldError.value = null
}

async function toggleVisibility(row: BranchMaterial) {
  if (!selectedBranchId.value) return
  rowActionId.value = row.id
  rowActionError.value = null
  rowActionTraceId.value = null
  try {
    await workshop.setBranchMaterialStatus(
      selectedBranchId.value,
      row.id,
      row.status === 'active' ? 'inactive' : 'active',
    )
    toast.success(t('catalog.toast.statusChanged'))
  } catch (caught) {
    rowActionError.value = t('catalog.error.statusChangeFailed')
    rowActionTraceId.value = apiTraceId(caught)
  } finally {
    rowActionId.value = null
  }
}

// Table filters reload just the table (offset 0); the picker is independent.
watch([statusFilter, turFilter], () => {
  void loadBranchTable(0)
})

watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void loadBranchTable(0), SEARCH_DEBOUNCE_MS)
})

// Type-time sanitization (PhoneInput precedent) — invalid characters never stick.
watch(
  () => materialForm.priceTiyin,
  (value) => {
    const clean = sanitizeMoneyInput(value)
    if (clean !== value) materialForm.priceTiyin = clean
  },
)
watch(
  () => materialForm.minStock,
  (value) => {
    const clean = sanitizeQuantityInput(value)
    if (clean !== value) materialForm.minStock = clean
  },
)

// Reset (and close) the add/edit dialog whenever the topbar switches the branch —
// a draft priced for one branch must not silently save into another — and reload
// the table + picker for the new branch.
watch(selectedBranchId, () => {
  materialModalOpen.value = false
  attachSheetOpen.value = false
  collapsedDecorIds.value = new Set()
  resetMaterialForm()
  void refreshCatalog()
})

watch(
  () => route.query.search,
  () => {
    applyRouteSearch()
  },
)

onMounted(async () => {
  applyRouteSearch()
  await workshop.loadBranchContext().catch(() => undefined)
  window.clearTimeout(searchTimer)
  await refreshCatalog()
})

onBeforeUnmount(() => {
  window.clearTimeout(searchTimer)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>{{ $t('catalog.page.title') }}</h1>
      </div>
    </div>

    <div v-if="!canUseCatalog" class="st-empty">
      <h3>{{ $t('catalog.page.noAccessTitle') }}</h3>
      <p>{{ $t('catalog.page.noAccessBody') }}</p>
    </div>

    <div v-else-if="accessibleBranches.length === 0" class="st-empty">
      <h3>{{ $t('catalog.page.noBranchTitle') }}</h3>
      <p>{{ $t('catalog.page.noBranchBody') }}</p>
    </div>

    <template v-else>
      <div class="mp-filters">
        <label class="mp-filter-input">
          <span>{{ $t('catalog.filter.searchLabel') }}</span>
          <input v-model="search" :placeholder="$t('catalog.filter.searchPlaceholder')" />
        </label>
        <ProjectDropdown
          v-model="turFilter"
          :label="$t('catalog.filter.turLabel')"
          :options="turOptions"
          top-label
        />
        <ProjectDropdown
          v-model="statusFilter"
          :label="$t('catalog.filter.statusLabel')"
          :options="statusOptions"
          top-label
        />
        <button
          type="button"
          class="mp-button mp-button-primary"
          data-onboard="catalog-add"
          @click="openAttachSheet"
        >
          {{ $t('catalog.action.attach') }}
        </button>
      </div>

      <FilterStatus
        :active="catalogFiltered"
        :loading="workshop.loading"
        :count="workshop.branchMaterials.length"
        noun="material"
        :on-reset="activeCatalogFilterCount > 1 ? resetCatalogFilters : null"
      />

      <div v-if="rowActionError" class="banner danger mb-4">
        <div class="grow">{{ rowActionError }}{{ traceSuffix(rowActionTraceId) }}</div>
      </div>

      <BranchMaterialAttachSheet
        :open="attachSheetOpen"
        :branch-id="selectedBranchId"
        @close="attachSheetOpen = false"
        @attached="onMaterialsAttached"
      />

      <AppModal
        :open="materialModalOpen"
        :title="$t('catalog.form.title')"
        @close="closeMaterialModal"
      >
        <form class="grid gap-3" @submit.prevent="saveBranchMaterial">
          <!-- The format itself is fixed once attached — show the server label in a
               plain disabled field (finance-modal precedent); price and threshold
               are the only editable values. -->
          <label class="field">
            <span>{{ $t('catalog.form.material') }}</span>
            <input class="mp-input" :value="editingBranchMaterial?.label ?? ''" disabled />
          </label>
          <label class="field">
            <span>{{ $t('catalog.form.price') }}</span>
            <input
              v-model="materialForm.priceTiyin"
              class="mp-input"
              inputmode="numeric"
              required
            />
            <small v-if="priceTiyinParsed !== null" class="text-ink-muted">
              = {{ formatTiyin(priceTiyinParsed) }} {{ materialPriceUnit }}
            </small>
            <small v-else-if="priceFieldError" class="mp-field-error">
              {{ priceFieldError }}
            </small>
            <small v-else-if="editingBranchMaterial?.price_unset" class="text-warning">
              {{ $t('catalog.price.unsetHint') }}
            </small>
          </label>
          <label class="field">
            <span>{{ thresholdLabel }} ({{ materialThresholdUnit }})</span>
            <input v-model="materialForm.minStock" class="mp-input" inputmode="decimal" required />
            <small v-if="minStockFieldError" class="mp-field-error">
              {{ minStockFieldError }}
            </small>
            <small v-else class="text-ink-muted">{{ thresholdHint }}</small>
          </label>
          <p
            v-if="materialError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            {{ $t('catalog.form.saveFailed') }}
          </p>
          <div class="flex items-center gap-2">
            <button class="mp-button mp-button-primary" type="submit" :disabled="materialSaving">
              {{ materialSaving ? $t('catalog.action.saving') : $t('catalog.action.save') }}
            </button>
            <button type="button" class="mp-button mp-button-outline" @click="closeMaterialModal">
              {{ $t('catalog.action.cancel') }}
            </button>
          </div>
        </form>
      </AppModal>

      <section
        v-if="workshop.catalogLoading && workshop.branchMaterials.length === 0"
        class="card p-5"
        aria-live="polite"
      >
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="workshop.catalogError" class="st-error">
        <h3>{{ $t('catalog.page.loadErrorTitle') }}</h3>
        <p>{{ traceLine(workshop.catalogTraceId) }}</p>
      </section>

      <section v-else class="card">
        <!-- QAD-159: `tbl-fluid` drops the shared 680px floor for this table only —
             long Russian decor names used to force the whole page sideways. The
             decor line wraps instead, and the columns that repeat what the group
             header already says (Tur) or matter least on a phone fall away as
             width runs out. -->
        <div class="table-wrap">
          <table class="tbl tbl-fluid">
            <thead>
              <tr>
                <!-- Let the format column absorb the table's slack so the narrow
                     price/threshold/stock columns hug their content on the right. -->
                <th class="w-full">{{ $t('catalog.table.format') }}</th>
                <th class="nowrap hidden lg:table-cell">{{ $t('catalog.table.tur') }}</th>
                <th class="nowrap right hidden sm:table-cell">{{ $t('catalog.table.price') }}</th>
                <th class="nowrap right hidden sm:table-cell">{{ thresholdColumn }}</th>
                <th class="nowrap right hidden md:table-cell">
                  {{ $t('catalog.table.onHand') }}
                </th>
                <th class="nowrap">{{ $t('catalog.table.status') }}</th>
              </tr>
            </thead>
            <tbody v-for="group in decorGroups" :key="group.decor.id">
              <!-- Group header: the decor's identity once, then its formats. -->
              <tr class="bg-sunk">
                <td colspan="6">
                  <button
                    type="button"
                    class="flex w-full min-w-0 items-center gap-3 rounded-md text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    :aria-expanded="!isCollapsed(group.decor.id)"
                    :aria-label="$t('catalog.table.expandDekor', { name: group.decor.label })"
                    @click="toggleDecor(group.decor.id)"
                  >
                    <AuthFileImage
                      v-if="group.decor.image_file_id"
                      :file-id="group.decor.image_file_id"
                      :alt="group.decor.label"
                      class="size-[34px] shrink-0 rounded-md object-cover"
                    />
                    <span
                      v-else
                      class="sw"
                      :class="materialSwatchClass(swatchSource(group.decor))"
                    ></span>
                    <span class="grid min-w-0 flex-1 gap-0.5">
                      <span class="nm break-words">{{ group.decor.label }}</span>
                      <small class="block break-words text-ink-muted">
                        {{ group.decor.manufacturer_name }} ·
                        {{ $t('catalog.meta.formatCount', { n: group.rows.length }) }}
                      </small>
                    </span>
                  </button>
                </td>
              </tr>
              <template v-if="!isCollapsed(group.decor.id)">
                <tr v-for="row in group.rows" :key="row.id" class="row-clickable">
                  <td>
                    <div class="grid min-w-0 gap-0.5 pl-[46px]">
                      <!-- The format is the edit control, stretched over the row
                           (QAD-184) — the row no longer ends in a button column. -->
                      <button
                        type="button"
                        class="nm row-open row-open-text break-words"
                        :aria-label="$t('catalog.table.editRow', { name: row.label })"
                        @click="editBranchMaterial(row)"
                      >
                        {{ formatLabel(row) }}
                      </button>
                      <small v-if="row.price_unset" class="block">
                        <span class="pill p-warn">
                          <span class="pd"></span>{{ $t('catalog.price.unset') }}
                        </span>
                      </small>
                      <!-- Below `sm` the Narx and Chegara columns are gone — a phone
                           cannot hold six columns plus a wrapping decor name without
                           scrolling sideways. The numbers move here instead of being
                           dropped. -->
                      <small class="block text-ink-muted sm:hidden">
                        {{ formatTiyin(row.price_tiyin) }} {{ priceUnit(row.decor_format.type) }} ·
                        {{ thresholdColumn }}: {{ thresholdParts(row).value }}
                        {{ thresholdParts(row).unit }}
                      </small>
                      <small class="block text-ink-muted md:hidden">
                        {{ $t('catalog.table.onHand') }}: {{ onHandText(row) }}
                      </small>
                    </div>
                  </td>
                  <td class="nowrap hidden lg:table-cell">
                    <span :class="isTape(row.decor_format.type) ? 'pill p-eb' : 'pill p-cut'">
                      <span class="pd"></span>{{ decorTypeLabel(row.decor_format.type) }}
                    </span>
                  </td>
                  <td class="amt nowrap hidden sm:table-cell">
                    {{ formatTiyin(row.price_tiyin) }}
                    <small class="block font-normal text-ink-muted">
                      {{ priceUnit(row.decor_format.type) }}
                    </small>
                  </td>
                  <td class="amt muted nowrap hidden sm:table-cell">
                    {{ thresholdParts(row).value }}
                    <small class="block font-normal">{{ thresholdParts(row).unit }}</small>
                  </td>
                  <td
                    class="amt nowrap hidden md:table-cell"
                    :class="isLowStock(row) ? 'text-warning' : 'muted'"
                  >
                    {{ onHandText(row) }}
                  </td>
                  <!-- `row-above` lifts the switch over the row's stretched click
                       layer, so toggling Faol never opens the edit modal. -->
                  <td class="nowrap row-above">
                    <button
                      type="button"
                      role="switch"
                      :aria-checked="row.status === 'active'"
                      :aria-label="$t('catalog.table.statusToggle', { name: row.label })"
                      :aria-busy="rowActionId === row.id || undefined"
                      :disabled="rowActionId === row.id"
                      class="inline-flex items-center gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50"
                      @click="toggleVisibility(row)"
                    >
                      <span
                        class="relative h-5 w-9 shrink-0 rounded-full transition-colors"
                        :class="row.status === 'active' ? 'bg-accent' : 'bg-hairline-strong'"
                        aria-hidden="true"
                      >
                        <span
                          class="absolute left-0.5 top-0.5 size-4 rounded-full bg-white shadow transition-transform"
                          :class="row.status === 'active' ? 'translate-x-4' : 'translate-x-0'"
                        ></span>
                      </span>
                      <!-- The switch carries its own accessible name, so below `sm`
                           the visible label can go rather than wrap one letter per line. -->
                      <span
                        class="hidden text-xs font-bold sm:inline"
                        :class="row.status === 'active' ? 'text-ink' : 'text-ink-muted'"
                      >
                        {{
                          row.status === 'active'
                            ? $t('catalog.status.active')
                            : $t('catalog.status.inactive')
                        }}
                      </span>
                    </button>
                  </td>
                </tr>
              </template>
            </tbody>
            <tbody v-if="decorGroups.length === 0">
              <tr>
                <td colspan="6">
                  <div class="st-empty !border-0 !py-8">
                    <template v-if="catalogFiltered">
                      <h3>{{ $t('catalog.empty.filteredTitle') }}</h3>
                      <p>{{ $t('catalog.empty.filteredBody') }}</p>
                    </template>
                    <template v-else>
                      <h3>{{ $t('catalog.empty.title') }}</h3>
                      <p>{{ $t('catalog.empty.body') }}</p>
                      <!-- Only on first run: with a filter on, this button is a
                           second copy of the one in the bar above (QAD-182). -->
                      <button
                        type="button"
                        class="mp-button mp-button-primary mt-3"
                        @click="openAttachSheet"
                      >
                        {{ $t('catalog.action.attach') }}
                      </button>
                    </template>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div v-if="workshop.branchMaterialsHasMore" class="mt-4 flex justify-center">
        <button
          type="button"
          class="mp-button mp-button-outline"
          :disabled="workshop.catalogLoading"
          @click="loadMoreBranchMaterials"
        >
          {{
            workshop.catalogLoading
              ? $t('catalog.action.loadingMore')
              : $t('catalog.action.loadMore')
          }}
        </button>
      </div>
    </template>
  </section>
</template>
