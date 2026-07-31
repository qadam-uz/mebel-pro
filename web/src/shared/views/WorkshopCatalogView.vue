<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { traceLine, traceSuffix } from '@/shared/app/errorTrace'
import { sanitizeMoneyInput, sanitizeQuantityInput } from '@/shared/app/inputSanitizers'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import type { DropdownOption } from '@/shared/app/roleConfig'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import {
  thresholdUnit,
  LOW_STOCK_THRESHOLD_COLUMN,
  LOW_STOCK_THRESHOLD_HINT,
  LOW_STOCK_THRESHOLD_LABEL,
} from '@/shared/app/lowStockThreshold'
import AppModal from '@/shared/components/AppModal.vue'
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
import type { MaterialKind, MaterialStatus } from '@/shared/stores/admin'
import {
  useWorkshopStore,
  type BranchMaterial,
  type BranchMaterialFilters,
} from '@/shared/stores/workshop'

const permissions = useWorkshopPermissions()
const workshop = useWorkshopStore()
const toast = useToast()
const route = useRoute()
const { notifyProgress } = useOnboardingContinuation()
const statusFilter = ref<'all' | MaterialStatus>('all')
const kindFilter = ref<'all' | MaterialKind>('all')
const search = ref('')

// Same defect as Ombor (QAD-182): with a search on, the branch reported it held
// no materials at all — and offered an add button that would not have helped.
const catalogFiltered = computed(
  () =>
    search.value.trim().length > 0 || kindFilter.value !== 'all' || statusFilter.value !== 'all',
)

// The bar-level reset appears from the second active filter on: with one, it
// would sit next to that filter's own clear and do the same thing.
const activeCatalogFilterCount = computed(
  () =>
    (search.value.trim() ? 1 : 0) +
    (kindFilter.value === 'all' ? 0 : 1) +
    (statusFilter.value === 'all' ? 0 : 1),
)

function resetCatalogFilters() {
  search.value = ''
  kindFilter.value = 'all'
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
const statusOptions: DropdownOption[] = [
  { value: 'all', label: 'Hammasi' },
  { value: 'active', label: 'Faol', dot: 'success' },
  { value: 'inactive', label: 'Faol emas', dot: 'muted' },
]
const kindOptions: DropdownOption[] = [
  { value: 'all', label: 'Barcha turlar' },
  { value: 'panel', label: 'List' },
  { value: 'edge', label: 'Kromka' },
]
const editingBranchMaterial = computed(
  () => workshop.branchMaterials.find((row) => row.id === editingBranchMaterialId.value) ?? null,
)
const materialThresholdUnit = computed(() => {
  const material = editingBranchMaterial.value?.material
  return material ? thresholdUnit(material.kind) : 'dona'
})
const materialPriceUnit = computed(() => {
  const material = editingBranchMaterial.value?.material
  return material ? priceUnit(material.kind) : ''
})
function routeSearchValue() {
  const value = route.query.search
  return typeof value === 'string' ? value : ''
}

function applyRouteSearch() {
  const value = routeSearchValue()
  if (value !== search.value) search.value = value
}

function materialMeta(row: (typeof workshop.branchMaterials)[number]) {
  const material = row.material
  if (material.kind === 'edge') return `kromka · ${material.thickness_mm} mm · ${material.color}`
  return `${material.type?.toUpperCase() ?? 'panel'} · ${material.thickness_mm} mm · ${material.color} · ${material.panel_length_mm}x${material.panel_width_mm}`
}

function priceUnit(kind: MaterialKind) {
  return kind === 'edge' ? '/ metr' : '/ list'
}

// Split "2.5 m" / "12 dona" so the unit can sit on its own muted line and the
// digits stay aligned on the column's right edge.
function thresholdParts(row: BranchMaterial) {
  const text = formatStockQuantity(row.min_stock, thresholdUnit(row.material.kind))
  const splitAt = text.lastIndexOf(' ')
  return { value: text.slice(0, splitAt), unit: text.slice(splitAt + 1) }
}

function tableFilters(offset = 0): BranchMaterialFilters {
  return {
    status: statusFilter.value === 'all' ? null : statusFilter.value,
    kind: kindFilter.value === 'all' ? null : kindFilter.value,
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
// The attach sheet loads its own options when it opens, against a catalog that
// now excludes everything this branch already carries.
function refreshCatalog() {
  return loadBranchTable(0)
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
    const material = editingBranchMaterial.value?.material
    const minStock = parseDisplayQuantity(
      materialForm.minStock,
      material?.kind === 'edge' ? 'm' : 'pcs',
    )
    // The price field is entered in so'm; the backend stores tiyin (1 so'm = 100
    // tiyin). null covers both unparseable input and 0 — a 0 so'm material must
    // never reach the client catalog by accident.
    const priceTiyin = priceTiyinParsed.value
    if (priceTiyin === null) {
      priceFieldError.value = "Narxni to'g'ri kiriting — masalan: 350 000"
      return
    }
    if (!Number.isFinite(minStock) || minStock < 0) {
      minStockFieldError.value = `${LOW_STOCK_THRESHOLD_LABEL}ni to'g'ri kiriting`
      return
    }
    await workshop.updateBranchMaterial(selectedBranchId.value, editingBranchMaterialId.value, {
      price_tiyin: priceTiyin,
      min_stock: minStock,
    })
    resetMaterialForm()
    materialModalOpen.value = false
    await refreshCatalog()
    toast.success('Material sozlamasi saqlandi.')
  } catch {
    materialError.value = 'branch_material_save_failed'
  } finally {
    materialSaving.value = false
  }
}

function openAttachSheet() {
  attachSheetOpen.value = true
}

async function onMaterialsAttached(count: number) {
  attachSheetOpen.value = false
  await refreshCatalog()
  if (!(await notifyProgress())) {
    toast.success(
      count === 1 ? "Material filialga qo'shildi." : `${count} ta material filialga qo'shildi.`,
    )
  }
}

function editBranchMaterial(row: BranchMaterial) {
  editingBranchMaterialId.value = row.id
  materialForm.priceTiyin = String(row.price_tiyin / 100)
  // Existing rows keep whatever threshold they were saved with — the new
  // per-kind defaults apply to new attachments only (no backfill, QAD-159).
  materialForm.minStock =
    row.material.kind === 'edge' ? String(row.min_stock / 1000) : String(row.min_stock)
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

async function toggleVisibility(row: (typeof workshop.branchMaterials)[number]) {
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
    toast.success("Material holati o'zgartirildi.")
  } catch (caught) {
    rowActionError.value = "Material holatini o'zgartirib bo'lmadi."
    rowActionTraceId.value = apiTraceId(caught)
  } finally {
    rowActionId.value = null
  }
}

// Table filters reload just the table (offset 0); the picker is independent.
watch([statusFilter, kindFilter], () => {
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
        <h1>Material katalogi</h1>
      </div>
    </div>

    <div v-if="!canUseCatalog" class="st-empty">
      <h3>Material katalogiga ruxsatingiz yo'q</h3>
      <p>Ustaxona rahbariga murojaat qiling.</p>
    </div>

    <div v-else-if="accessibleBranches.length === 0" class="st-empty">
      <h3>Filial biriktirilmagan</h3>
      <p>Filial biriktirilgach, katalog shu yerda ko'rinadi.</p>
    </div>

    <template v-else>
      <div class="mp-filters">
        <label class="mp-filter-input">
          <span>Qidirish</span>
          <input v-model="search" placeholder="Material nomi yoki dekor kodi" />
        </label>
        <ProjectDropdown v-model="kindFilter" label="Tur" :options="kindOptions" top-label />
        <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" top-label />
        <button
          type="button"
          class="mp-button mp-button-primary"
          data-onboard="catalog-add"
          @click="openAttachSheet"
        >
          + Material qo'shish
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

      <AppModal :open="materialModalOpen" title="Materialni tahrirlash" @close="closeMaterialModal">
        <form class="grid gap-3" @submit.prevent="saveBranchMaterial">
          <!-- The material itself is fixed once attached — show the name in a plain
               disabled field (finance-modal precedent); price and threshold are the
               only editable values. -->
          <label class="field">
            <span>Material</span>
            <input class="mp-input" :value="editingBranchMaterial?.material.name ?? ''" disabled />
          </label>
          <label class="field">
            <span>Narx (so'm)</span>
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
          </label>
          <label class="field">
            <span>{{ LOW_STOCK_THRESHOLD_LABEL }} ({{ materialThresholdUnit }})</span>
            <input v-model="materialForm.minStock" class="mp-input" inputmode="decimal" required />
            <small v-if="minStockFieldError" class="mp-field-error">
              {{ minStockFieldError }}
            </small>
            <small v-else class="text-ink-muted">{{ LOW_STOCK_THRESHOLD_HINT }}</small>
          </label>
          <p
            v-if="materialError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            Filial materiali saqlanmadi.
          </p>
          <div class="flex items-center gap-2">
            <button class="mp-button mp-button-primary" type="submit" :disabled="materialSaving">
              {{ materialSaving ? 'Saqlanmoqda' : 'Saqlash' }}
            </button>
            <button type="button" class="mp-button mp-button-outline" @click="closeMaterialModal">
              Bekor
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
        <h3>Ma'lumotni yuklab bo'lmadi</h3>
        <p>{{ traceLine(workshop.catalogTraceId) }}</p>
      </section>

      <section v-else class="card">
        <!-- QAD-159: `tbl-fluid` drops the shared 680px floor for this table only —
             long Russian decor names used to force the whole page sideways. The name
             wraps instead, and the columns that repeat what the name already says
             (Tur) or matter least on a phone (Chegara) fall away as width runs out. -->
        <div class="table-wrap">
          <table class="tbl tbl-fluid">
            <thead>
              <tr>
                <!-- Let the descriptive name column absorb the table's slack so the
                     narrow price/threshold/status columns hug their content on the
                     right instead of drifting apart across the full width. -->
                <th class="w-full">Material</th>
                <th class="nowrap hidden lg:table-cell">Tur</th>
                <th class="nowrap right hidden sm:table-cell">Narx</th>
                <th class="nowrap right hidden sm:table-cell">{{ LOW_STOCK_THRESHOLD_COLUMN }}</th>
                <th class="nowrap">Holat</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in workshop.branchMaterials" :key="row.id" class="row-clickable">
                <td>
                  <div class="flex min-w-0 items-start gap-3">
                    <span
                      class="sw mt-1 shrink-0"
                      :class="materialSwatchClass(row.material)"
                    ></span>
                    <span class="grid min-w-0 gap-0.5">
                      <!-- The name is the edit control, stretched over the row
                           (QAD-184) — the row no longer ends in a button column. -->
                      <button
                        type="button"
                        class="nm row-open row-open-text break-words"
                        :aria-label="`${row.material.name} — tahrirlash`"
                        @click="editBranchMaterial(row)"
                      >
                        {{ row.material.name }}
                      </button>
                      <small class="block break-words text-ink-muted">{{
                        materialMeta(row)
                      }}</small>
                      <!-- Below `sm` the Narx and Chegara columns are gone — a phone
                           cannot hold five columns plus a wrapping decor name without
                           scrolling sideways. The numbers move here instead of being
                           dropped. -->
                      <small class="block text-ink-muted sm:hidden">
                        {{ formatTiyin(row.price_tiyin) }} {{ priceUnit(row.material.kind) }} ·
                        {{ LOW_STOCK_THRESHOLD_COLUMN }}: {{ thresholdParts(row).value }}
                        {{ thresholdParts(row).unit }}
                      </small>
                    </span>
                  </div>
                </td>
                <td class="nowrap hidden lg:table-cell">
                  <span :class="row.material.kind === 'edge' ? 'pill p-eb' : 'pill p-cut'">
                    <span class="pd"></span
                    >{{ row.material.kind === 'edge' ? 'Kromka (metr)' : 'List' }}
                  </span>
                </td>
                <td class="amt nowrap hidden sm:table-cell">
                  {{ formatTiyin(row.price_tiyin) }}
                  <small class="block font-normal text-ink-muted">
                    {{ priceUnit(row.material.kind) }}
                  </small>
                </td>
                <td class="amt muted nowrap hidden sm:table-cell">
                  {{ thresholdParts(row).value }}
                  <small class="block font-normal">{{ thresholdParts(row).unit }}</small>
                </td>
                <!-- `row-above` lifts the switch over the row's stretched click
                     layer, so toggling Faol never opens the edit modal. -->
                <td class="nowrap row-above">
                  <button
                    type="button"
                    role="switch"
                    :aria-checked="row.status === 'active'"
                    :aria-label="`${row.material.name} holati`"
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
                      {{ row.status === 'active' ? 'Faol' : 'Faol emas' }}
                    </span>
                  </button>
                </td>
              </tr>
              <tr v-if="workshop.branchMaterials.length === 0">
                <td colspan="5">
                  <div class="st-empty !border-0 !py-8">
                    <template v-if="catalogFiltered">
                      <h3>Filtrga mos material topilmadi</h3>
                      <p>Filtrni o'zgartiring yoki tozalang.</p>
                    </template>
                    <template v-else>
                      <h3>Bu filialga material qo'shilmagan</h3>
                      <p>Platforma katalogidan material qo'shing.</p>
                      <!-- Only on first run: with a filter on, this button is a
                           second copy of the one in the bar above (QAD-182). -->
                      <button
                        type="button"
                        class="mp-button mp-button-primary mt-3"
                        @click="openAttachSheet"
                      >
                        + Material qo'shish
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
          {{ workshop.catalogLoading ? 'Yuklanmoqda' : "Ko'proq yuklash" }}
        </button>
      </div>
    </template>
  </section>
</template>
