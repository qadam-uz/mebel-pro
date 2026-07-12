<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { sanitizeMoneyInput, sanitizeQuantityInput } from '@/shared/app/inputSanitizers'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import type { DropdownOption } from '@/shared/app/roleConfig'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import AppModal from '@/shared/components/AppModal.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import {
  formatStockQuantity,
  formatTiyin,
  parseDisplayQuantity,
  parseSomToTiyin,
} from '@/shared/formatters'
import type { MaterialKind, MaterialStatus } from '@/shared/stores/admin'
import { useWorkshopStore, type BranchMaterial } from '@/shared/stores/workshop'

const permissions = useWorkshopPermissions()
const workshop = useWorkshopStore()
const toast = useToast()
const route = useRoute()
const statusFilter = ref<'all' | MaterialStatus>('all')
const kindFilter = ref<'all' | MaterialKind>('all')
const manufacturerFilter = ref('all')
const search = ref('')
const rowActionId = ref<string | null>(null)
const rowActionError = ref<string | null>(null)
const rowActionTraceId = ref<string | null>(null)
const materialSaving = ref(false)
const materialError = ref<string | null>(null)
const materialFieldError = ref<string | null>(null)
const editingBranchMaterialId = ref<string | null>(null)
const materialModalOpen = ref(false)
let searchTimer: number | undefined
const materialForm = reactive({
  materialId: null as string | null,
  // Deliberately empty, not '0': a pre-filled 0 satisfies `required` and lets a
  // hurried owner publish a 0 so'm material to the client-facing catalog.
  priceTiyin: '',
  minStock: '0',
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
  { value: 'panel', label: 'Panel' },
  { value: 'edge', label: 'Krom' },
]
const manufacturerOptions = computed<DropdownOption[]>(() => {
  const byId = new Map<string, string>()
  for (const row of workshop.branchMaterials) {
    byId.set(row.material.manufacturer_id, row.material.manufacturer_name)
  }
  return [
    { value: 'all', label: 'Barcha ishlab chiqaruvchilar' },
    ...[...byId.entries()]
      .sort((left, right) => left[1].localeCompare(right[1]))
      .map(([value, label]) => ({ value, label })),
  ]
})
const availableCatalogOptions = computed(() =>
  workshop.catalogOptions
    .filter((option) => !option.already_selected)
    .map((option) => ({
      value: option.material.id,
      label: option.material.name,
      meta: `${option.material.manufacturer_name} · ${option.material.kind}`,
    })),
)
const editingBranchMaterial = computed(
  () => workshop.branchMaterials.find((row) => row.id === editingBranchMaterialId.value) ?? null,
)
const selectedCatalogMaterial = computed(
  () =>
    workshop.catalogOptions.find((option) => option.material.id === materialForm.materialId)
      ?.material ?? null,
)
const materialMinStockUnit = computed(() => {
  const material = selectedCatalogMaterial.value ?? editingBranchMaterial.value?.material
  return material?.kind === 'edge' ? 'm' : 'panel'
})
const materialPriceUnit = computed(() => {
  const material = selectedCatalogMaterial.value ?? editingBranchMaterial.value?.material
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
  if (material.kind === 'edge') return `krom · ${material.thickness_mm} mm · ${material.color}`
  return `${material.type?.toUpperCase() ?? 'panel'} · ${material.thickness_mm} mm · ${material.color} · ${material.panel_length_mm}x${material.panel_width_mm}`
}

function priceUnit(kind: MaterialKind) {
  return kind === 'edge' ? '/ metr' : '/ panel'
}

// Split "2.5 m" / "12 panel" so the unit can sit on its own muted line and the
// digits stay aligned on the column's right edge.
function minStockParts(row: BranchMaterial) {
  const text = formatStockQuantity(row.min_stock, row.material.kind === 'edge' ? 'm' : 'panel')
  const splitAt = text.lastIndexOf(' ')
  return { value: text.slice(0, splitAt), unit: text.slice(splitAt + 1) }
}

async function refreshCatalog() {
  if (!selectedBranchId.value) return
  rowActionError.value = null
  rowActionTraceId.value = null
  const filters = {
    status: statusFilter.value === 'all' ? null : statusFilter.value,
    kind: kindFilter.value === 'all' ? null : kindFilter.value,
    manufacturer_id: manufacturerFilter.value === 'all' ? null : manufacturerFilter.value,
    search: search.value,
  }
  await Promise.all([
    workshop.loadBranchMaterials(selectedBranchId.value, filters).catch(() => undefined),
    workshop.loadCatalogOptions(selectedBranchId.value, filters).catch(() => undefined),
  ])
}

async function saveBranchMaterial() {
  if (!selectedBranchId.value) return
  materialSaving.value = true
  materialError.value = null
  materialFieldError.value = null
  priceFieldError.value = null
  minStockFieldError.value = null
  try {
    if (!editingBranchMaterialId.value && !materialForm.materialId) {
      materialFieldError.value = 'Material tanlang'
      return
    }
    const material = selectedCatalogMaterial.value ?? editingBranchMaterial.value?.material
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
      minStockFieldError.value = "Min zaxirani to'g'ri kiriting"
      return
    }
    const payload = { price_tiyin: priceTiyin, min_stock: minStock }
    const wasEditing = Boolean(editingBranchMaterialId.value)
    if (editingBranchMaterialId.value) {
      await workshop.updateBranchMaterial(
        selectedBranchId.value,
        editingBranchMaterialId.value,
        payload,
      )
    } else {
      await workshop.addBranchMaterial(selectedBranchId.value, {
        material_id: materialForm.materialId,
        ...payload,
      })
    }
    resetMaterialForm()
    materialModalOpen.value = false
    await refreshCatalog()
    toast.success(wasEditing ? 'Material sozlamasi saqlandi.' : "Material filialga qo'shildi.")
  } catch {
    materialError.value = 'branch_material_save_failed'
  } finally {
    materialSaving.value = false
  }
}

function openCreateMaterial() {
  resetMaterialForm()
  materialError.value = null
  materialModalOpen.value = true
}

function editBranchMaterial(row: BranchMaterial) {
  editingBranchMaterialId.value = row.id
  materialForm.materialId = row.material_id
  materialForm.priceTiyin = String(row.price_tiyin / 100)
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
  materialForm.materialId = null
  materialForm.priceTiyin = ''
  materialForm.minStock = '0'
  materialFieldError.value = null
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

watch([selectedBranchId, statusFilter, kindFilter, manufacturerFilter], () => {
  void refreshCatalog()
})

watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void refreshCatalog(), 250)
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
// a draft priced for one branch must not silently save into another.
watch(selectedBranchId, () => {
  materialModalOpen.value = false
  resetMaterialForm()
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
      <p>Ustaxona egasiga murojaat qiling.</p>
    </div>

    <div v-else-if="accessibleBranches.length === 0" class="st-empty">
      <h3>Filial biriktirilmagan</h3>
      <p>Filial biriktirilgach, katalog shu yerda ko'rinadi.</p>
    </div>

    <template v-else>
      <div class="mp-filters">
        <label class="mp-filter-input">
          <span>Qidirish</span>
          <input v-model="search" placeholder="Material qidirish..." />
        </label>
        <ProjectDropdown v-model="kindFilter" label="Tur" :options="kindOptions" top-label />
        <ProjectDropdown
          v-model="manufacturerFilter"
          label="Ishlab chiqaruvchi"
          :options="manufacturerOptions"
          top-label
        />
        <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" top-label />
        <button type="button" class="mp-button mp-button-primary" @click="openCreateMaterial">
          + Material qo'shish
        </button>
      </div>

      <div v-if="rowActionError" class="banner danger mb-4">
        <div class="grow">
          {{ rowActionError }} · trace_id: {{ rowActionTraceId ?? 'unavailable' }}
        </div>
      </div>

      <AppModal
        :open="materialModalOpen"
        :title="editingBranchMaterialId ? 'Materialni tahrirlash' : `Material qo'shish`"
        @close="closeMaterialModal"
      >
        <form class="grid gap-3" @submit.prevent="saveBranchMaterial">
          <!-- Editing: availableCatalogOptions filters out already-selected materials,
               so the combobox has no option (and no label) for the edited row — show
               the name in a plain disabled field instead (finance-modal precedent). -->
          <label v-if="editingBranchMaterialId" class="field">
            <span>Material</span>
            <input class="mp-input" :value="editingBranchMaterial?.material.name ?? ''" disabled />
          </label>
          <SearchCombobox
            v-else
            v-model="materialForm.materialId"
            label="Material"
            :options="availableCatalogOptions"
            :error="materialFieldError"
          />
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
            <span>Min zaxira ({{ materialMinStockUnit }})</span>
            <input v-model="materialForm.minStock" class="mp-input" inputmode="decimal" required />
            <small v-if="minStockFieldError" class="mp-field-error">
              {{ minStockFieldError }}
            </small>
          </label>
          <p
            v-if="materialError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            Filial materiali saqlanmadi.
          </p>
          <div class="flex items-center gap-2">
            <button class="mp-button mp-button-primary" type="submit" :disabled="materialSaving">
              {{
                materialSaving ? 'Saqlanmoqda' : editingBranchMaterialId ? 'Saqlash' : "Qo'shish"
              }}
            </button>
            <button type="button" class="mp-button mp-button-outline" @click="closeMaterialModal">
              Bekor
            </button>
          </div>
        </form>
      </AppModal>

      <section v-if="workshop.catalogLoading" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="workshop.catalogError" class="st-error">
        <h3>Ma'lumotni yuklab bo'lmadi</h3>
        <p>trace_id: {{ workshop.catalogTraceId ?? 'unavailable' }}</p>
      </section>

      <section v-else class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <!-- Let the descriptive name column absorb the table's slack so the
                     narrow type/price/stock/status columns hug their content on the
                     right instead of drifting apart across the full width. -->
                <th class="w-full">Material</th>
                <th>Tur</th>
                <th class="right">Narx</th>
                <th class="right">Min zaxira</th>
                <th>Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in workshop.branchMaterials" :key="row.id">
                <td>
                  <div class="flex min-w-0 items-center gap-3">
                    <span class="sw" :class="materialSwatchClass(row.material)"></span>
                    <span class="min-w-0">
                      <span class="nm">{{ row.material.name }}</span>
                      <small class="block truncate text-ink-muted">{{ materialMeta(row) }}</small>
                    </span>
                  </div>
                </td>
                <td>
                  <span :class="row.material.kind === 'edge' ? 'pill p-eb' : 'pill p-cut'">
                    <span class="pd"></span
                    >{{ row.material.kind === 'edge' ? 'Krom (metr)' : 'Panel' }}
                  </span>
                </td>
                <td class="amt">
                  {{ formatTiyin(row.price_tiyin) }}
                  <small class="block font-normal text-ink-muted">
                    {{ priceUnit(row.material.kind) }}
                  </small>
                </td>
                <td class="amt muted">
                  {{ minStockParts(row).value }}
                  <small class="block font-normal">{{ minStockParts(row).unit }}</small>
                </td>
                <td>
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
                    <span
                      class="text-xs font-bold"
                      :class="row.status === 'active' ? 'text-ink' : 'text-ink-muted'"
                    >
                      {{ row.status === 'active' ? 'Faol' : 'Faol emas' }}
                    </span>
                  </button>
                </td>
                <td class="right">
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                    @click="editBranchMaterial(row)"
                  >
                    Tahrirlash
                  </button>
                </td>
              </tr>
              <tr v-if="workshop.branchMaterials.length === 0">
                <td colspan="6">
                  <div class="st-empty !border-0 !py-8">
                    <h3>Bu filialga material qo'shilmagan</h3>
                    <p>Platforma katalogidan material qo'shing.</p>
                    <button
                      type="button"
                      class="mp-button mp-button-primary mt-3"
                      @click="openCreateMaterial"
                    >
                      + Material qo'shish
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>
