<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { buildAdminMaterialWriteRequest, composeMaterialName } from '@/shared/app/adminMaterials'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  positiveDecimal,
  positiveInteger,
  requiredText,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import {
  dropdownOption,
  materialKindLabel,
  materialStatusLabel,
  materialStatusTone,
} from '@/shared/app/adminUi'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import AdminModalCloseIcon from '@/shared/components/AdminModalCloseIcon.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import ImageUploadField from '@/shared/components/ImageUploadField.vue'
import MultiSelectFilter from '@/shared/components/MultiSelectFilter.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import {
  useAdminStore,
  type Material,
  type MaterialFilters,
  type MaterialKind,
  type MaterialStatus,
  type PanelMaterialType,
} from '@/shared/stores/admin'
import { useFilesStore } from '@/shared/stores/files'

const admin = useAdminStore()
const files = useFilesStore()
const toast = useToast()
const rolePath = useRolePath()
const modalOpen = ref(false)
const manufacturerModalOpen = ref(false)
const uploadError = ref<string | null>(null)
const statusTarget = ref<{ row: Material; status: MaterialStatus } | null>(null)
const formPanel = ref<HTMLElement | null>(null)
const inlineMfrPanel = ref<HTMLElement | null>(null)
const formTrap = useFocusTrap(formPanel, modalOpen, () => (modalOpen.value = false))
const inlineMfrTrap = useFocusTrap(
  inlineMfrPanel,
  manufacturerModalOpen,
  () => (manufacturerModalOpen.value = false),
)
const saving = ref(false)
const manufacturerSaving = ref(false)
const actionId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const saveError = ref<string | null>(null)
const manufacturerError = ref<string | null>(null)
const imageUploadResetKey = ref(0)
const search = ref('')
const statusFilter = ref('all')
const kindFilter = ref('all')
const manufacturerFilter = ref<string[]>([])
const typeFilter = ref<string[]>([])

const form = reactive({
  kind: 'panel' as MaterialKind,
  manufacturerId: '',
  type: 'dsp' as PanelMaterialType,
  thicknessMm: '18',
  color: '',
  decorCode: '',
  panelLengthMm: '2800',
  panelWidthMm: '2070',
  edgeWidthMm: '19',
  grainDirection: true,
  imageFileId: null as string | null,
})
const manufacturerForm = reactive({
  name: '',
  country: '',
  note: '',
})
type MaterialField =
  | 'manufacturerId'
  | 'thicknessMm'
  | 'color'
  | 'type'
  | 'panelLengthMm'
  | 'panelWidthMm'
  | 'edgeWidthMm'
type InlineManufacturerField = 'name'
const materialFieldErrors = reactive<FieldErrors<MaterialField>>({})
const inlineManufacturerFieldErrors = reactive<FieldErrors<InlineManufacturerField>>({})
const materialFieldIds: Record<MaterialField, string> = {
  manufacturerId: 'mat-manufacturer',
  thicknessMm: 'mat-thick',
  color: 'mat-color',
  type: 'mat-type',
  panelLengthMm: 'mat-len',
  panelWidthMm: 'mat-wid',
  edgeWidthMm: 'mat-edge-width',
}
const materialFieldOrder: MaterialField[] = [
  'manufacturerId',
  'thicknessMm',
  'color',
  'type',
  'panelLengthMm',
  'panelWidthMm',
  'edgeWidthMm',
]
const materialApiFieldMap: Partial<Record<string, MaterialField>> = {
  manufacturer_not_found: 'manufacturerId',
  material_color_required: 'color',
  invalid_thickness: 'thicknessMm',
  invalid_edge_width: 'edgeWidthMm',
  invalid_panel_material: 'type',
  invalid_panel_size: 'panelLengthMm',
  invalid_grain: 'type',
}
const materialApiLocMap: Partial<Record<string, MaterialField>> = {
  'body.manufacturer_id': 'manufacturerId',
  'body.thickness_mm': 'thicknessMm',
  'body.color': 'color',
  'body.type': 'type',
  'body.panel_length_mm': 'panelLengthMm',
  'body.panel_width_mm': 'panelWidthMm',
  'body.edge_width_mm': 'edgeWidthMm',
}

const kindOptions = [
  dropdownOption('all', 'Hammasi', 'panel va kromka'),
  dropdownOption('panel', 'Panel', 'plita materiallari'),
  dropdownOption('edge', 'Kromka', 'kromka'),
]
const statusOptions = [
  dropdownOption('all', 'Hammasi', 'barcha holatlar'),
  dropdownOption('active', 'Faol', "filial tanlovida ko'rinadi"),
  dropdownOption('inactive', 'Faol emas', 'yangi tanlovdan yashirilgan'),
]
const manufacturerFilterOptions = computed<ChoiceOption[]>(() =>
  admin.manufacturers.map((manufacturer) => ({
    value: manufacturer.id,
    label: manufacturer.name,
    meta: manufacturer.country ?? '',
  })),
)
const manufacturerChoiceOptions = computed<ChoiceOption[]>(() =>
  admin.manufacturers
    .filter((manufacturer) => manufacturer.status === 'active')
    .map((manufacturer) => ({
      value: manufacturer.id,
      label: manufacturer.name,
      meta: manufacturer.country ?? '',
    })),
)
const materialTypeOptions: ChoiceOption[] = [
  { value: 'dsp', label: 'DSP' },
  { value: 'mdf', label: 'MDF' },
  { value: 'plywood', label: 'Plywood' },
  { value: 'natural_wood', label: "Tabiiy yog'och" },
  { value: 'other', label: 'Boshqa' },
]
const materialTypeFilterOptions = computed<ChoiceOption[]>(() => materialTypeOptions)
const materialKindOptions: ChoiceOption[] = [
  { value: 'panel', label: 'Panel', meta: 'plita materiali' },
  { value: 'edge', label: 'Kromka', meta: 'kromka' },
]

// Filtering + paging are server-side (the catalog holds hundreds of rows). Every
// filter change reloads from offset 0; "load more" appends the next page. Search
// is debounced so we don't round-trip per keystroke.
const hasActiveFilters = computed(
  () =>
    search.value.trim() !== '' ||
    kindFilter.value !== 'all' ||
    statusFilter.value !== 'all' ||
    manufacturerFilter.value.length > 0 ||
    typeFilter.value.length > 0,
)

function currentFilters(): MaterialFilters {
  return {
    search: search.value.trim() || undefined,
    kind: kindFilter.value === 'all' ? undefined : (kindFilter.value as MaterialKind),
    status: statusFilter.value === 'all' ? undefined : (statusFilter.value as MaterialStatus),
    manufacturerIds: manufacturerFilter.value.length ? manufacturerFilter.value : undefined,
    materialTypes: typeFilter.value.length ? (typeFilter.value as PanelMaterialType[]) : undefined,
  }
}

function reloadMaterials() {
  void admin.loadMaterials(currentFilters())
}

function loadMoreMaterials() {
  void admin.loadMaterials({ ...currentFilters(), offset: admin.materials.length })
}

let searchTimer: number | undefined
watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(reloadMaterials, SEARCH_DEBOUNCE_MS)
})
watch([kindFilter, statusFilter, manufacturerFilter, typeFilter], reloadMaterials)

// AB-22: panels must have length >= width (the cut grain/orientation assumption).
const dimensionError = computed(
  () =>
    form.kind === 'panel' &&
    Number(form.panelLengthMm) > 0 &&
    Number(form.panelWidthMm) > 0 &&
    Number(form.panelLengthMm) < Number(form.panelWidthMm),
)
const selectedManufacturerName = computed(
  () => admin.manufacturers.find((manufacturer) => manufacturer.id === form.manufacturerId)?.name,
)
const materialNamePreview = computed(() =>
  composeMaterialName(form, selectedManufacturerName.value),
)
const materialImageTitle = computed(() => materialNamePreview.value || 'Material rasmi')
const materialImageMeta = computed(() =>
  [
    materialKindLabel(form.kind),
    selectedManufacturerName.value,
    form.thicknessMm ? `${form.thicknessMm} mm` : null,
  ]
    .filter(Boolean)
    .join(' · '),
)

function clearFilters() {
  search.value = ''
  statusFilter.value = 'all'
  kindFilter.value = 'all'
  manufacturerFilter.value = []
  typeFilter.value = []
}

function openCreate() {
  editingId.value = null
  form.kind = 'panel'
  form.manufacturerId = admin.manufacturers.find((row) => row.status === 'active')?.id ?? ''
  form.type = 'dsp'
  form.thicknessMm = '18'
  form.color = ''
  form.decorCode = ''
  form.panelLengthMm = '2800'
  form.panelWidthMm = '2070'
  form.edgeWidthMm = '19'
  form.grainDirection = true
  form.imageFileId = null
  saveError.value = null
  uploadError.value = null
  imageUploadResetKey.value += 1
  clearFieldErrors(materialFieldErrors)
  modalOpen.value = true
}

function openEdit(material: Material) {
  editingId.value = material.id
  form.kind = material.kind
  form.manufacturerId = material.manufacturer_id
  form.type = material.type ?? 'dsp'
  form.thicknessMm = material.thickness_mm
  form.color = material.color
  form.decorCode = material.decor_code ?? ''
  form.panelLengthMm = String(material.panel_length_mm ?? 2800)
  form.panelWidthMm = String(material.panel_width_mm ?? 2070)
  form.edgeWidthMm = String(material.edge_width_mm ?? 19)
  form.grainDirection = material.grain_direction ?? false
  form.imageFileId = material.image_file_id
  saveError.value = null
  uploadError.value = null
  imageUploadResetKey.value += 1
  clearFieldErrors(materialFieldErrors)
  modalOpen.value = true
}

function openInlineManufacturer() {
  clearFieldErrors(inlineManufacturerFieldErrors)
  manufacturerError.value = null
  manufacturerModalOpen.value = true
}

function materialSpec(material: Material) {
  if (material.kind === 'panel') {
    return `${materialTypeLabel(material.type)} . ${material.panel_length_mm} x ${material.panel_width_mm} mm`
  }
  return `kromka · ${material.thickness_mm} x ${material.edge_width_mm ?? '-'} mm`
}

function materialTypeLabel(type: PanelMaterialType | null | undefined) {
  return materialTypeOptions.find((option) => option.value === type)?.label ?? 'Panel'
}

async function onMaterialFile(file: File) {
  uploadError.value = null
  try {
    const uploaded = await files.upload(file)
    form.imageFileId = uploaded.id
    toast.success('Rasm yuklandi')
  } catch {
    uploadError.value = "Rasmni yuklab bo'lmadi. Boshqa fayl bilan qayta urinib ko'ring."
    imageUploadResetKey.value += 1
    toast.danger("Rasmni yuklab bo'lmadi")
  }
}

function removeImage() {
  form.imageFileId = null
  uploadError.value = null
  imageUploadResetKey.value += 1
}

function validateMaterialForm() {
  clearFieldErrors(materialFieldErrors)
  const set = (field: MaterialField, error: string | null) => {
    if (error) materialFieldErrors[field] = error
  }
  set('manufacturerId', requiredText(form.manufacturerId, 'Ishlab chiqaruvchini tanlang.'))
  set('thicknessMm', requiredText(form.thicknessMm) ?? positiveDecimal(form.thicknessMm))
  set('color', requiredText(form.color))
  if (form.kind === 'panel') {
    set('type', requiredText(form.type))
    set('panelLengthMm', requiredText(form.panelLengthMm) ?? positiveInteger(form.panelLengthMm))
    set('panelWidthMm', requiredText(form.panelWidthMm) ?? positiveInteger(form.panelWidthMm))
    if (!materialFieldErrors.panelLengthMm && dimensionError.value) {
      materialFieldErrors.panelLengthMm = "Uzunlik enidan kichik bo'lmasligi kerak."
    }
  } else {
    set('edgeWidthMm', requiredText(form.edgeWidthMm) ?? positiveInteger(form.edgeWidthMm))
  }
  const hasErrors = materialFieldOrder.some((field) => Boolean(materialFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(materialFieldErrors, materialFieldOrder, materialFieldIds)
  return !hasErrors
}

async function save() {
  if (!validateMaterialForm()) return
  saving.value = true
  saveError.value = null
  try {
    const payload = buildAdminMaterialWriteRequest(form)
    if (editingId.value) await admin.updateMaterial(editingId.value, payload)
    else await admin.createMaterial(payload)
    modalOpen.value = false
    toast.success(editingId.value ? 'Material yangilandi' : "Material qo'shildi")
  } catch (error) {
    const fields = fieldErrorsFromApi<MaterialField>(error, materialApiFieldMap, materialApiLocMap)
    if (Object.keys(fields).length > 0) {
      Object.assign(materialFieldErrors, fields)
      focusFirstFieldError(materialFieldErrors, materialFieldOrder, materialFieldIds)
    } else {
      saveError.value = 'material_save_failed'
      toast.danger('Material saqlanmadi')
    }
  } finally {
    saving.value = false
  }
}

async function saveInlineManufacturer() {
  clearFieldErrors(inlineManufacturerFieldErrors)
  const nameError = requiredText(manufacturerForm.name)
  if (nameError) {
    inlineManufacturerFieldErrors.name = nameError
    focusFirstFieldError(inlineManufacturerFieldErrors, ['name'], { name: 'inline-mfr-name' })
    return
  }
  manufacturerSaving.value = true
  manufacturerError.value = null
  try {
    const created = await admin.createManufacturer({
      name: manufacturerForm.name,
      country: manufacturerForm.country || null,
      note: manufacturerForm.note || null,
    })
    form.manufacturerId = created.id
    manufacturerForm.name = ''
    manufacturerForm.country = ''
    manufacturerForm.note = ''
    manufacturerModalOpen.value = false
  } catch (error) {
    Object.assign(
      inlineManufacturerFieldErrors,
      fieldErrorsFromApi<InlineManufacturerField>(error, {
        manufacturer_name_required: 'name',
        manufacturer_name_exists: 'name',
      }),
    )
    if (inlineManufacturerFieldErrors.name) {
      focusFirstFieldError(inlineManufacturerFieldErrors, ['name'], { name: 'inline-mfr-name' })
    } else {
      manufacturerError.value = 'manufacturer_save_failed'
    }
  } finally {
    manufacturerSaving.value = false
  }
}

function askStatus(row: Material, status: MaterialStatus) {
  statusTarget.value = { row, status }
}

async function confirmStatus() {
  const target = statusTarget.value
  if (!target) return
  statusTarget.value = null
  actionId.value = target.row.id
  try {
    await admin.setMaterialStatus(target.row.id, target.status)
    toast.success(target.status === 'active' ? 'Faollashtirildi' : 'Faol emas qilindi')
  } catch {
    toast.danger('Amal bajarilmadi')
  } finally {
    actionId.value = null
  }
}

onMounted(async () => {
  await Promise.all([admin.loadManufacturers(), admin.loadMaterials()])
})
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Material katalogi</h1>
      </div>
      <button type="button" class="admin-primary-action" @click="openCreate">
        + Yangi material
      </button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span>Qidirish</span>
        <input v-model="search" placeholder="Material nomi" />
      </label>
      <FormSelect
        v-model="kindFilter"
        class="admin-filter-select"
        label="Tur"
        :options="kindOptions"
      />
      <MultiSelectFilter
        v-model="manufacturerFilter"
        label="Ishlab chiqaruvchilar"
        :options="manufacturerFilterOptions"
        empty-label="Hammasi"
        selected-label="tanlangan"
      />
      <MultiSelectFilter
        v-model="typeFilter"
        label="Panel turlari"
        :options="materialTypeFilterOptions"
        empty-label="Hammasi"
        selected-label="tanlangan"
      />
      <FormSelect
        v-model="statusFilter"
        class="admin-filter-select"
        label="Holat"
        :options="statusOptions"
      />
    </div>

    <section
      v-if="admin.materialsLoading && admin.materials.length === 0"
      class="admin-card p-5"
      aria-live="polite"
    >
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="admin.materialsError"
      :code="admin.materialsError"
      :trace-id="admin.materialsTraceId"
      title="Materiallar yuklanmadi"
      @retry="reloadMaterials()"
    />

    <section v-else-if="admin.materials.length === 0" class="admin-empty">
      <template v-if="!hasActiveFilters">
        <h3>Material yo'q</h3>
        <p>Avval ishlab chiqaruvchi qo'shing, keyin panel yoki kromka material yarating.</p>
        <div class="mt-3 flex flex-wrap justify-center gap-2">
          <button type="button" class="admin-primary-action" @click="openCreate">
            + Yangi material
          </button>
          <RouterLink
            :to="rolePath('/admin/catalog/manufacturers')"
            class="mp-button mp-button-outline"
          >
            Ishlab chiqaruvchilar
          </RouterLink>
        </div>
      </template>
      <template v-else>
        <h3>Filtrlarga mos material yo'q</h3>
        <p>Filtrlarni o'zgartiring yoki tozalang.</p>
        <button type="button" class="mp-button mp-button-outline mt-3" @click="clearFilters">
          Filtrlarni tozalash
        </button>
      </template>
    </section>

    <section v-else class="admin-card">
      <div class="admin-table-wrap">
        <table class="admin-table wide">
          <thead>
            <tr>
              <th><span class="sr-only">Rasm</span></th>
              <th>Material</th>
              <th>Ishlab chiqaruvchi</th>
              <th>Tur</th>
              <th>Turi / o'lcham</th>
              <th>Qalinligi</th>
              <th>Panel o'lchami</th>
              <th>Tekstura</th>
              <th>Holat</th>
              <th>Ustaxonalar</th>
              <th><span class="sr-only">Amallar</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="material in admin.materials" :key="material.id">
              <td>
                <div class="admin-material-thumb">
                  <span
                    class="admin-material-thumb-swatch sw"
                    :class="materialSwatchClass(material)"
                    aria-hidden="true"
                  ></span>
                  <span class="admin-material-thumb-mark" aria-hidden="true">
                    {{ material.kind === 'panel' ? 'P' : 'K' }}
                  </span>
                  <AuthFileImage
                    v-if="material.image_file_id"
                    :file-id="material.image_file_id"
                    :alt="material.name"
                    class="admin-material-thumb-img"
                  />
                </div>
              </td>
              <td class="nm">
                {{ material.name }}
                <small>{{ material.color }} . {{ material.decor_code ?? "dekor yo'q" }}</small>
              </td>
              <td>{{ material.manufacturer_name }}</td>
              <td>
                <span
                  class="admin-pill"
                  :class="material.kind === 'panel' ? 'admin-pill-success' : 'admin-pill-info'"
                >
                  {{ materialKindLabel(material.kind) }}
                </span>
              </td>
              <td>{{ materialSpec(material) }}</td>
              <td class="admin-mono">{{ material.thickness_mm }} mm</td>
              <td class="admin-mono">
                <template v-if="material.kind === 'panel'">
                  {{ material.panel_length_mm }} x {{ material.panel_width_mm }}
                </template>
                <template v-else>-</template>
              </td>
              <td>{{ material.grain_direction ? 'bor' : '-' }}</td>
              <td>
                <span class="admin-pill" :class="materialStatusTone(material.status)">
                  {{ materialStatusLabel(material.status) }}
                </span>
              </td>
              <td class="admin-mono">{{ material.branch_usage_count }}</td>
              <td class="admin-right">
                <div class="flex justify-end gap-2">
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :aria-label="`${material.name} materialini tahrirlash`"
                    @click="openEdit(material)"
                  >
                    Tahrirlash
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :disabled="actionId === material.id"
                    :aria-label="
                      material.status === 'active'
                        ? `${material.name} materialini faol emas qilish`
                        : `${material.name} materialini faollashtirish`
                    "
                    @click="
                      askStatus(material, material.status === 'active' ? 'inactive' : 'active')
                    "
                  >
                    {{ material.status === 'active' ? 'Faol emas qilish' : 'Faollashtirish' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="admin.materialsHasMore" class="mt-4 flex justify-center">
      <button
        type="button"
        class="mp-button mp-button-outline"
        :disabled="admin.materialsLoading"
        @click="loadMoreMaterials"
      >
        {{ admin.materialsLoading ? 'Yuklanmoqda' : "Ko'proq yuklash" }}
      </button>
    </div>

    <template v-if="modalOpen">
      <div class="admin-modal-scrim" aria-hidden="true" @click="modalOpen = false"></div>
      <section
        ref="formPanel"
        class="admin-modal wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="material-title"
        tabindex="-1"
        @keydown="formTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="material-title">{{ editingId ? 'Material tahrirlash' : 'Yangi material' }}</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="modalOpen = false"
          >
            <AdminModalCloseIcon />
          </button>
        </div>
        <form novalidate @submit.prevent="save">
          <div class="admin-modal-b">
            <div class="admin-form-grid three">
              <FormSelect
                id="mat-kind"
                v-model="form.kind"
                label="Tur"
                :options="materialKindOptions"
                class="admin-full"
                :disabled="!!editingId"
                required
              />
              <div class="admin-full grid gap-2 md:grid-cols-[1fr_auto]">
                <FormSelect
                  id="mat-manufacturer"
                  v-model="form.manufacturerId"
                  label="Ishlab chiqaruvchi"
                  :options="manufacturerChoiceOptions"
                  placeholder="Ishlab chiqaruvchini tanlang"
                  :error="materialFieldErrors.manufacturerId"
                  required
                />
                <button
                  type="button"
                  class="mp-button mp-button-outline self-end"
                  @click="openInlineManufacturer"
                >
                  + Yangi ishlab chiqaruvchi
                </button>
              </div>
              <div class="admin-field admin-full">
                <span>Nomi (avtomatik)</span>
                <div
                  class="rounded-md border border-hairline bg-sunk px-3 py-2 text-sm font-bold text-ink"
                >
                  {{ materialNamePreview }}
                </div>
              </div>
              <FormSelect
                v-if="form.kind === 'panel'"
                id="mat-type"
                v-model="form.type"
                label="Panel turi"
                :options="materialTypeOptions"
                :error="materialFieldErrors.type"
                required
              />
              <label class="admin-field" for="mat-thick">
                <span>Qalinligi, mm</span>
                <input
                  id="mat-thick"
                  v-model="form.thicknessMm"
                  inputmode="decimal"
                  required
                  :aria-invalid="!!materialFieldErrors.thicknessMm"
                  aria-describedby="mat-thick-error"
                />
                <span
                  v-if="materialFieldErrors.thicknessMm"
                  id="mat-thick-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ materialFieldErrors.thicknessMm }}
                </span>
              </label>
              <label v-if="form.kind === 'edge'" class="admin-field" for="mat-edge-width">
                <span>Eni (mm)</span>
                <input
                  id="mat-edge-width"
                  v-model="form.edgeWidthMm"
                  inputmode="numeric"
                  required
                  :aria-invalid="!!materialFieldErrors.edgeWidthMm"
                  aria-describedby="mat-edge-width-error"
                />
                <span
                  v-if="materialFieldErrors.edgeWidthMm"
                  id="mat-edge-width-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ materialFieldErrors.edgeWidthMm }}
                </span>
              </label>
              <label class="admin-field" for="mat-color">
                <span>Rang / decor</span>
                <input
                  id="mat-color"
                  v-model="form.color"
                  required
                  :aria-invalid="!!materialFieldErrors.color"
                  aria-describedby="mat-color-error"
                />
                <span
                  v-if="materialFieldErrors.color"
                  id="mat-color-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ materialFieldErrors.color }}
                </span>
              </label>
              <label class="admin-field" for="mat-decor">
                <span>Decor kodi</span>
                <input id="mat-decor" v-model="form.decorCode" />
              </label>
              <template v-if="form.kind === 'panel'">
                <label class="admin-field" for="mat-len">
                  <span>Uzunlik, mm</span>
                  <input
                    id="mat-len"
                    v-model="form.panelLengthMm"
                    inputmode="numeric"
                    required
                    :aria-invalid="!!materialFieldErrors.panelLengthMm"
                    aria-describedby="mat-len-error"
                  />
                  <span
                    v-if="materialFieldErrors.panelLengthMm"
                    id="mat-len-error"
                    class="admin-field-error"
                    role="alert"
                  >
                    {{ materialFieldErrors.panelLengthMm }}
                  </span>
                </label>
                <label class="admin-field" for="mat-wid">
                  <span>Eni, mm</span>
                  <input
                    id="mat-wid"
                    v-model="form.panelWidthMm"
                    inputmode="numeric"
                    required
                    :aria-invalid="!!materialFieldErrors.panelWidthMm"
                    aria-describedby="mat-wid-error"
                  />
                  <span
                    v-if="materialFieldErrors.panelWidthMm"
                    id="mat-wid-error"
                    class="admin-field-error"
                    role="alert"
                  >
                    {{ materialFieldErrors.panelWidthMm }}
                  </span>
                </label>
                <p
                  v-if="dimensionError"
                  class="admin-full text-xs font-bold text-danger"
                  role="alert"
                >
                  Uzunlik enidan kichik bo'lmasligi kerak.
                </p>
                <label
                  class="flex min-h-11 items-center gap-3 self-end rounded-md border border-hairline-strong px-3 text-sm font-bold"
                >
                  <input
                    v-model="form.grainDirection"
                    type="checkbox"
                    class="size-4 accent-accent"
                  />
                  Tekstura yo'nalishi bor
                </label>
              </template>
              <ImageUploadField
                id="mat-image"
                :file-id="form.imageFileId"
                :alt="materialImageTitle"
                :title="materialImageTitle"
                :meta="materialImageMeta"
                :uploading="files.uploading"
                :error="uploadError"
                :reset-key="imageUploadResetKey"
                @select="onMaterialFile"
                @remove="removeImage"
              />
            </div>
            <p
              v-if="saveError"
              class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Material saqlanmadi.
            </p>
          </div>
          <div class="admin-modal-f">
            <button type="button" class="mp-button mp-button-outline" @click="modalOpen = false">
              Bekor
            </button>
            <button
              type="submit"
              class="mp-button mp-button-primary"
              :disabled="saving || files.uploading || dimensionError"
            >
              {{ files.uploading ? 'Rasm yuklanmoqda' : saving ? 'Saqlanmoqda' : 'Saqlash' }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <template v-if="manufacturerModalOpen">
      <div
        class="admin-modal-scrim"
        aria-hidden="true"
        @click="manufacturerModalOpen = false"
      ></div>
      <section
        ref="inlineMfrPanel"
        class="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="inline-mfr-title"
        tabindex="-1"
        @keydown="inlineMfrTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="inline-mfr-title">Yangi ishlab chiqaruvchi</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="manufacturerModalOpen = false"
          >
            <AdminModalCloseIcon />
          </button>
        </div>
        <form novalidate @submit.prevent="saveInlineManufacturer">
          <div class="admin-modal-b">
            <div class="admin-form-grid">
              <label class="admin-field admin-full" for="inline-mfr-name">
                <span>Nomi</span>
                <input
                  id="inline-mfr-name"
                  v-model="manufacturerForm.name"
                  required
                  :aria-invalid="!!inlineManufacturerFieldErrors.name"
                  aria-describedby="inline-mfr-name-error"
                />
                <span
                  v-if="inlineManufacturerFieldErrors.name"
                  id="inline-mfr-name-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ inlineManufacturerFieldErrors.name }}
                </span>
              </label>
              <label class="admin-field" for="inline-mfr-country">
                <span>Davlat</span>
                <input id="inline-mfr-country" v-model="manufacturerForm.country" />
              </label>
              <label class="admin-field admin-full" for="inline-mfr-note">
                <span>Izoh</span>
                <textarea id="inline-mfr-note" v-model="manufacturerForm.note"></textarea>
              </label>
            </div>
            <p
              v-if="manufacturerError"
              class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Ishlab chiqaruvchi yaratilmadi.
            </p>
          </div>
          <div class="admin-modal-f">
            <button
              type="button"
              class="mp-button mp-button-outline"
              @click="manufacturerModalOpen = false"
            >
              Bekor
            </button>
            <button
              type="submit"
              class="mp-button mp-button-primary"
              :disabled="manufacturerSaving"
            >
              {{ manufacturerSaving ? 'Saqlanmoqda' : 'Saqlash' }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <ConfirmDialog
      :open="statusTarget !== null"
      :title="statusTarget?.status === 'inactive' ? 'Faol emas qilish' : 'Faollashtirish'"
      :message="
        statusTarget?.status === 'inactive'
          ? `${statusTarget?.row.name} faol emas qilinadi — uni filiallarning yangi tanlovlaridan yashiriladi; mavjud buyurtmalarga ta'sir qilmaydi.`
          : `${statusTarget?.row.name} faollashtiriladi va filial tanlovida ko'rinadi.`
      "
      confirm-label="Tasdiqlash"
      cancel-label="Bekor qilish"
      :danger="statusTarget?.status === 'inactive'"
      :busy="actionId === statusTarget?.row.id"
      @confirm="confirmStatus"
      @cancel="statusTarget = null"
    />
  </section>
</template>
