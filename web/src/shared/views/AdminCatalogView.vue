<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import FilterDropdown from '@/shared/components/FilterDropdown.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import MultiSelectFilter from '@/shared/components/MultiSelectFilter.vue'
import { useAdminStore, type Material } from '@/shared/stores/admin'
import { useFilesStore } from '@/shared/stores/files'

const admin = useAdminStore()
const files = useFilesStore()
const manufacturerSaving = ref(false)
const materialSaving = ref(false)
const manufacturerSaveError = ref<string | null>(null)
const materialSaveError = ref<string | null>(null)
const editingManufacturerId = ref<string | null>(null)
const editingMaterialId = ref<string | null>(null)
const manufacturerSearch = ref('')
const manufacturerStatus = ref<string | null>(null)
const materialSearch = ref('')
const materialStatus = ref<string | null>(null)
const materialKinds = ref<string[]>([])

const manufacturerForm = reactive({
  name: '',
  country: '',
  note: '',
})
const materialForm = reactive({
  kind: 'panel',
  manufacturerId: '',
  type: 'dsp',
  name: '',
  thicknessMm: '18',
  color: '',
  decorCode: '',
  panelLengthMm: '2800',
  panelWidthMm: '2070',
  grainDirection: true,
  imageFileId: '',
})

const activeManufacturers = computed(() =>
  admin.manufacturers.filter((manufacturer) => manufacturer.status === 'active'),
)
const manufacturerOptions = computed(() =>
  activeManufacturers.value.map((manufacturer) => ({
    value: manufacturer.id,
    label: manufacturer.name,
    meta: manufacturer.country ?? 'active',
  })),
)
const filteredMaterials = computed(() => {
  if (materialKinds.value.length === 0) return admin.materials
  return admin.materials.filter((material) => materialKinds.value.includes(material.kind))
})
const hasManufacturerFilters = computed(
  () => manufacturerSearch.value.trim() !== '' || manufacturerStatus.value !== null,
)
const hasMaterialFilters = computed(
  () =>
    materialSearch.value.trim() !== '' ||
    materialStatus.value !== null ||
    materialKinds.value.length > 0,
)

const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]
const statusFilterOptions = [{ value: 'all', label: 'Any status' }, ...statusOptions]
const kindOptions = [
  { value: 'panel', label: 'Panel', meta: 'panel count' },
  { value: 'edge', label: 'Edge', meta: 'metres in UI' },
]
const panelTypeOptions = [
  { value: 'dsp', label: 'DSP' },
  { value: 'mdf', label: 'MDF' },
  { value: 'plywood', label: 'Plywood' },
  { value: 'natural_wood', label: 'Natural wood' },
  { value: 'other', label: 'Other' },
]

function selectedStatus(value: string | null) {
  return value === 'all' ? null : value
}

async function refreshManufacturers() {
  await admin.loadManufacturers({
    search: manufacturerSearch.value,
    status: selectedStatus(manufacturerStatus.value) as 'active' | 'inactive' | null,
  })
}

async function refreshMaterials() {
  await admin.loadMaterials({
    search: materialSearch.value,
    status: selectedStatus(materialStatus.value) as 'active' | 'inactive' | null,
  })
}

async function saveManufacturer() {
  manufacturerSaving.value = true
  manufacturerSaveError.value = null
  try {
    const payload = {
      name: manufacturerForm.name,
      country: manufacturerForm.country || null,
      note: manufacturerForm.note || null,
    }
    if (editingManufacturerId.value) {
      await admin.updateManufacturer(editingManufacturerId.value, payload)
    } else {
      await admin.createManufacturer(payload)
    }
    resetManufacturerForm()
  } catch {
    manufacturerSaveError.value = 'manufacturer_save_failed'
  } finally {
    manufacturerSaving.value = false
  }
}

async function saveMaterial() {
  materialSaving.value = true
  materialSaveError.value = null
  try {
    const isPanel = materialForm.kind === 'panel'
    const payload = {
      manufacturer_id: materialForm.manufacturerId,
      type: isPanel ? materialForm.type : null,
      name: materialForm.name,
      thickness_mm: materialForm.thicknessMm,
      color: materialForm.color,
      decor_code: materialForm.decorCode || null,
      panel_length_mm: isPanel ? Number(materialForm.panelLengthMm) : null,
      panel_width_mm: isPanel ? Number(materialForm.panelWidthMm) : null,
      grain_direction: isPanel ? materialForm.grainDirection : null,
      image_file_id: materialForm.imageFileId || null,
    }
    if (editingMaterialId.value) {
      await admin.updateMaterial(editingMaterialId.value, payload)
    } else {
      await admin.createMaterial({
        kind: materialForm.kind,
        ...payload,
      })
    }
    resetMaterialForm()
    await refreshMaterials()
  } catch {
    materialSaveError.value = 'material_save_failed'
  } finally {
    materialSaving.value = false
  }
}

async function onMaterialFile(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement) || !target.files?.[0]) return
  const uploaded = await files.upload(target.files[0])
  materialForm.imageFileId = uploaded.id
  target.value = ''
}

function editManufacturer(row: {
  id: string
  name: string
  country: string | null
  note: string | null
}) {
  editingManufacturerId.value = row.id
  manufacturerForm.name = row.name
  manufacturerForm.country = row.country ?? ''
  manufacturerForm.note = row.note ?? ''
}

function editMaterial(row: Material) {
  editingMaterialId.value = row.id
  materialForm.kind = row.kind
  materialForm.manufacturerId = row.manufacturer_id
  materialForm.type = row.type ?? 'dsp'
  materialForm.name = row.name
  materialForm.thicknessMm = String(row.thickness_mm)
  materialForm.color = row.color
  materialForm.decorCode = row.decor_code ?? ''
  materialForm.panelLengthMm = String(row.panel_length_mm ?? 2800)
  materialForm.panelWidthMm = String(row.panel_width_mm ?? 2070)
  materialForm.grainDirection = row.grain_direction ?? false
  materialForm.imageFileId = row.image_file_id ?? ''
}

function resetManufacturerForm() {
  editingManufacturerId.value = null
  manufacturerForm.name = ''
  manufacturerForm.country = ''
  manufacturerForm.note = ''
}

function resetMaterialForm() {
  editingMaterialId.value = null
  materialForm.kind = 'panel'
  materialForm.manufacturerId = activeManufacturers.value[0]?.id ?? ''
  materialForm.type = 'dsp'
  materialForm.name = ''
  materialForm.thicknessMm = '18'
  materialForm.color = ''
  materialForm.decorCode = ''
  materialForm.panelLengthMm = '2800'
  materialForm.panelWidthMm = '2070'
  materialForm.grainDirection = true
  materialForm.imageFileId = ''
}

function materialSpec(material: Material) {
  if (material.kind === 'edge') return `${material.thickness_mm} mm edge`
  return `${material.thickness_mm} mm · ${material.panel_length_mm}x${material.panel_width_mm} mm`
}

onMounted(async () => {
  await refreshManufacturers()
  await refreshMaterials()
  resetMaterialForm()
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Catalog</h1>
        <p class="mt-2 text-base text-ink-soft">
          Manage platform manufacturers and material master data.
        </p>
      </div>
      <div class="mp-chip bg-info-soft text-info">
        <span class="mp-dot" aria-hidden="true"></span>
        Platform master data
      </div>
    </div>

    <div
      v-if="admin.catalogError === 'permission_denied'"
      class="rounded-lg bg-danger-soft p-4 font-bold text-danger"
    >
      Catalog access is not available for this account.
    </div>

    <div class="grid gap-5 xl:grid-cols-[minmax(360px,0.82fr)_minmax(0,1.18fr)]">
      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Manufacturers</h2>
          <p class="mt-1 text-sm text-ink-soft">Create, edit, and status catalog makers.</p>
        </div>

        <form class="grid gap-3 p-5" @submit.prevent="saveManufacturer">
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="manufacturer-name"
              >Name</label
            >
            <input
              id="manufacturer-name"
              v-model="manufacturerForm.name"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="manufacturer-country">
                Country
              </label>
              <input
                id="manufacturer-country"
                v-model="manufacturerForm.country"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="manufacturer-note">
                Note
              </label>
              <input
                id="manufacturer-note"
                v-model="manufacturerForm.note"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              />
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              class="mp-button mp-button-primary"
              type="submit"
              :disabled="manufacturerSaving"
            >
              {{
                manufacturerSaving
                  ? 'Saving'
                  : editingManufacturerId
                    ? 'Save changes'
                    : 'Create manufacturer'
              }}
            </button>
            <button
              v-if="editingManufacturerId"
              type="button"
              class="mp-button mp-button-outline"
              @click="resetManufacturerForm"
            >
              Cancel edit
            </button>
          </div>
          <p
            v-if="manufacturerSaveError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            Manufacturer could not be saved.
          </p>
        </form>

        <div class="grid gap-3 border-t border-hairline p-5 sm:grid-cols-[1fr_180px_auto]">
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="manufacturer-search">
              Search
            </label>
            <input
              id="manufacturer-search"
              v-model="manufacturerSearch"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
            />
          </div>
          <FilterDropdown
            v-model="manufacturerStatus"
            label="Status"
            :options="statusFilterOptions"
          />
          <button
            class="mp-button mp-button-outline self-end"
            type="button"
            @click="refreshManufacturers"
          >
            Apply
          </button>
        </div>

        <div
          v-if="admin.catalogLoading"
          class="px-5 py-6 text-sm font-bold text-ink-soft"
          aria-live="polite"
        >
          Loading catalog records
        </div>
        <div v-else-if="admin.catalogError" class="px-5 py-6 text-sm font-bold text-danger">
          Catalog data could not be loaded. trace {{ admin.catalogTraceId ?? 'unavailable' }}
        </div>
        <div v-else-if="admin.manufacturers.length === 0" class="px-5 py-6 text-sm text-ink-soft">
          {{
            hasManufacturerFilters ? 'No manufacturers match the filters.' : 'No manufacturers yet.'
          }}
        </div>
        <div v-else class="divide-y divide-hairline">
          <article
            v-for="manufacturer in admin.manufacturers"
            :key="manufacturer.id"
            class="grid gap-3 px-5 py-4 md:grid-cols-[1fr_auto]"
          >
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <h3 class="truncate text-base font-extrabold text-ink">{{ manufacturer.name }}</h3>
                <span
                  class="mp-chip"
                  :class="
                    manufacturer.status === 'active'
                      ? 'bg-success-soft text-success'
                      : 'bg-danger-soft text-danger'
                  "
                >
                  <span class="mp-dot" aria-hidden="true"></span>
                  {{ manufacturer.status }}
                </span>
              </div>
              <p class="mt-1 text-sm text-ink-soft">
                {{ manufacturer.country || 'Country not set' }} ·
                {{ manufacturer.note || 'No note' }}
              </p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <button
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                type="button"
                @click="editManufacturer(manufacturer)"
              >
                Edit
              </button>
              <button
                class="mp-button min-h-9 px-3 text-xs"
                :class="
                  manufacturer.status === 'active'
                    ? 'border-danger bg-danger-soft text-danger'
                    : 'border-success bg-success-soft text-success'
                "
                type="button"
                @click="
                  admin.setManufacturerStatus(
                    manufacturer.id,
                    manufacturer.status === 'active' ? 'inactive' : 'active',
                  )
                "
              >
                {{ manufacturer.status === 'active' ? 'Deactivate' : 'Activate' }}
              </button>
            </div>
          </article>
        </div>
      </section>

      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Materials</h2>
          <p class="mt-1 text-sm text-ink-soft">Define panel and edge materials for branches.</p>
        </div>

        <form class="grid gap-3 p-5 lg:grid-cols-4" @submit.prevent="saveMaterial">
          <FormSelect v-model="materialForm.kind" label="Kind" :options="kindOptions" />
          <FormSelect
            v-model="materialForm.manufacturerId"
            label="Manufacturer"
            :options="manufacturerOptions"
            :error="manufacturerOptions.length === 0 ? 'Create an active manufacturer first' : null"
          />
          <FormSelect
            v-if="materialForm.kind === 'panel'"
            v-model="materialForm.type"
            label="Panel type"
            :options="panelTypeOptions"
          />
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="material-name">Name</label>
            <input
              id="material-name"
              v-model="materialForm.name"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="material-thickness">
              Thickness mm
            </label>
            <input
              id="material-thickness"
              v-model="materialForm.thicknessMm"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              inputmode="decimal"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="material-color">Color</label>
            <input
              id="material-color"
              v-model="materialForm.color"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="material-decor"
              >Decor code</label
            >
            <input
              id="material-decor"
              v-model="materialForm.decorCode"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
            />
          </div>
          <template v-if="materialForm.kind === 'panel'">
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="material-length">
                Panel length mm
              </label>
              <input
                id="material-length"
                v-model="materialForm.panelLengthMm"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="numeric"
                required
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="material-width">
                Panel width mm
              </label>
              <input
                id="material-width"
                v-model="materialForm.panelWidthMm"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="numeric"
                required
              />
            </div>
            <label
              class="flex min-h-11 items-center gap-3 self-end rounded-md border border-hairline-strong px-3 text-sm font-bold"
            >
              <input
                v-model="materialForm.grainDirection"
                type="checkbox"
                class="size-4 accent-accent"
              />
              Grain direction
            </label>
          </template>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="material-image">Image</label>
            <input
              id="material-image"
              type="file"
              accept="image/*"
              class="block min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 py-2 text-sm"
              @change="onMaterialFile"
            />
            <p v-if="materialForm.imageFileId" class="mt-1 font-mono text-[11px] text-ink-muted">
              image {{ materialForm.imageFileId.slice(0, 8) }}
            </p>
          </div>
          <div class="flex flex-wrap gap-2 lg:col-span-4">
            <button
              class="mp-button mp-button-primary"
              type="submit"
              :disabled="materialSaving || manufacturerOptions.length === 0"
            >
              {{
                materialSaving ? 'Saving' : editingMaterialId ? 'Save changes' : 'Create material'
              }}
            </button>
            <button
              v-if="editingMaterialId"
              type="button"
              class="mp-button mp-button-outline"
              @click="resetMaterialForm"
            >
              Cancel edit
            </button>
            <span v-if="files.uploading" class="mp-chip bg-info-soft text-info"
              >Uploading image</span
            >
          </div>
          <p
            v-if="materialSaveError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger lg:col-span-4"
          >
            Material could not be saved.
          </p>
        </form>

        <div class="grid gap-3 border-t border-hairline p-5 md:grid-cols-[1fr_180px_180px_auto]">
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="material-search"
              >Search</label
            >
            <input
              id="material-search"
              v-model="materialSearch"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
            />
          </div>
          <FilterDropdown v-model="materialStatus" label="Status" :options="statusFilterOptions" />
          <MultiSelectFilter v-model="materialKinds" label="Kinds" :options="kindOptions" />
          <button
            class="mp-button mp-button-outline self-end"
            type="button"
            @click="refreshMaterials"
          >
            Apply
          </button>
        </div>

        <div
          v-if="admin.catalogLoading"
          class="px-5 py-6 text-sm font-bold text-ink-soft"
          aria-live="polite"
        >
          Loading materials
        </div>
        <div v-else-if="admin.catalogError" class="px-5 py-6 text-sm font-bold text-danger">
          Materials could not be loaded. trace {{ admin.catalogTraceId ?? 'unavailable' }}
        </div>
        <div v-else-if="filteredMaterials.length === 0" class="px-5 py-6 text-sm text-ink-soft">
          {{ hasMaterialFilters ? 'No materials match the filters.' : 'No materials yet.' }}
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-[760px] w-full text-left text-sm">
            <thead class="bg-sunk text-xs uppercase text-ink-muted">
              <tr>
                <th class="px-5 py-3">Material</th>
                <th class="px-5 py-3">Spec</th>
                <th class="px-5 py-3">Status</th>
                <th class="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-hairline">
              <tr v-for="material in filteredMaterials" :key="material.id">
                <td class="px-5 py-4">
                  <div class="font-extrabold text-ink">{{ material.name }}</div>
                  <div class="font-mono text-xs text-ink-muted">
                    {{ material.manufacturer_name }} · {{ material.kind }}
                  </div>
                </td>
                <td class="px-5 py-4 text-ink-soft">
                  {{ materialSpec(material) }}
                </td>
                <td class="px-5 py-4">
                  <span
                    class="mp-chip"
                    :class="
                      material.status === 'active'
                        ? 'bg-success-soft text-success'
                        : 'bg-danger-soft text-danger'
                    "
                  >
                    <span class="mp-dot" aria-hidden="true"></span>
                    {{ material.status }}
                  </span>
                </td>
                <td class="px-5 py-4">
                  <div class="flex justify-end gap-2">
                    <button
                      class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                      type="button"
                      @click="editMaterial(material)"
                    >
                      Edit
                    </button>
                    <button
                      class="mp-button min-h-9 px-3 text-xs"
                      :class="
                        material.status === 'active'
                          ? 'border-danger bg-danger-soft text-danger'
                          : 'border-success bg-success-soft text-success'
                      "
                      type="button"
                      @click="
                        admin.setMaterialStatus(
                          material.id,
                          material.status === 'active' ? 'inactive' : 'active',
                        )
                      "
                    >
                      {{ material.status === 'active' ? 'Deactivate' : 'Activate' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </section>
</template>
