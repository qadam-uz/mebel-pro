<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { buildDekorWriteRequest, composeDekorLabel } from '@/shared/app/adminDekorlar'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { DEKOR_TYPES, dekorTurLabel } from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import {
  adminErrorMessage,
  dropdownOption,
  materialStatusLabel,
  materialStatusTone,
} from '@/shared/app/adminUi'
import { apiErrorCode } from '@/shared/api/client'
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
  type Dekor,
  type DekorFilters,
  type DekorType,
  type MaterialStatus,
} from '@/shared/stores/admin'
import { useFilesStore } from '@/shared/stores/files'

const admin = useAdminStore()
const files = useFilesStore()
const toast = useToast()
const rolePath = useRolePath()
const modalOpen = ref(false)
const manufacturerModalOpen = ref(false)
const uploadError = ref<string | null>(null)
const statusTarget = ref<{ row: Dekor; status: MaterialStatus } | null>(null)
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
const manufacturerFilter = ref<string[]>([])
const turFilter = ref<string[]>([])

// A dekor is identity only: manufacturer, tur, kod, nomi, tolali, rasm. Thickness,
// sizes and price belong to the branch row that carries the dekor, so none of them
// have an input here — that split is the whole point of the catalog reshape.
const form = reactive({
  manufacturerId: '',
  tur: 'ldsp' as DekorType,
  kod: '',
  nomi: '',
  tolali: true,
  imageFileId: null as string | null,
})
const manufacturerForm = reactive({
  name: '',
  country: '',
  note: '',
})
type DekorField = 'manufacturerId' | 'tur' | 'kod' | 'nomi'
type InlineManufacturerField = 'name'
const dekorFieldErrors = reactive<FieldErrors<DekorField>>({})
const inlineManufacturerFieldErrors = reactive<FieldErrors<InlineManufacturerField>>({})
const dekorFieldIds: Record<DekorField, string> = {
  manufacturerId: 'dek-manufacturer',
  tur: 'dek-tur',
  kod: 'dek-kod',
  nomi: 'dek-nomi',
}
const dekorFieldOrder: DekorField[] = ['manufacturerId', 'tur', 'kod', 'nomi']
const dekorApiFieldMap: Partial<Record<string, DekorField>> = {
  manufacturer_not_found: 'manufacturerId',
  dekor_nomi_required: 'nomi',
  // The (manufacturer, tur, kod) uniqueness conflict — anchor it on the code,
  // which is the field the operator changes to resolve it.
  dekor_exists: 'kod',
}
const dekorApiLocMap: Partial<Record<string, DekorField>> = {
  'body.manufacturer_id': 'manufacturerId',
  'body.tur': 'tur',
  'body.kod': 'kod',
  'body.nomi': 'nomi',
}

const turOptions = computed<ChoiceOption[]>(() =>
  DEKOR_TYPES.map((tur) => ({ value: tur, label: dekorTurLabel(tur) })),
)
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

// Filtering + paging are server-side (the catalog holds hundreds of rows). Every
// filter change reloads from offset 0; "load more" appends the next page. Search
// is debounced so we don't round-trip per keystroke.
const hasActiveFilters = computed(
  () =>
    search.value.trim() !== '' ||
    turFilter.value.length > 0 ||
    statusFilter.value !== 'all' ||
    manufacturerFilter.value.length > 0,
)

function currentFilters(): DekorFilters {
  return {
    search: search.value.trim() || undefined,
    turlar: turFilter.value.length ? (turFilter.value as DekorType[]) : undefined,
    status: statusFilter.value === 'all' ? undefined : (statusFilter.value as MaterialStatus),
    manufacturerIds: manufacturerFilter.value.length ? manufacturerFilter.value : undefined,
  }
}

function reloadDekorlar() {
  void admin.loadDekorlar(currentFilters())
}

function loadMoreDekorlar() {
  void admin.loadDekorlar({ ...currentFilters(), offset: admin.dekorlar.length })
}

let searchTimer: number | undefined
watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(reloadDekorlar, SEARCH_DEBOUNCE_MS)
})
watch([turFilter, statusFilter, manufacturerFilter], reloadDekorlar)

const selectedManufacturerName = computed(
  () => admin.manufacturers.find((manufacturer) => manufacturer.id === form.manufacturerId)?.name,
)
const dekorLabelPreview = computed(() => composeDekorLabel(form, selectedManufacturerName.value))
const dekorImageTitle = computed(() => dekorLabelPreview.value || 'Dekor rasmi')
const dekorImageMeta = computed(() =>
  [dekorTurLabel(form.tur), selectedManufacturerName.value].filter(Boolean).join(' · '),
)
// The swatch is what the operator recognises the dekor by before the photo
// uploads, so the preview card shows the same one the table will.
const previewSwatchClass = computed(() =>
  materialSwatchClass({ id: editingId.value ?? 'preview', nomi: form.nomi, kod: form.kod || null }),
)

/**
 * Warns on the (manufacturer, tur, kod) triple the backend enforces — and, for a
 * dekor with no code, on the (manufacturer, tur, nomi) triple the second partial
 * index covers. It is a WARNING, not a gate: the check can only see the page
 * currently loaded, so a real duplicate three pages down would pass silently. The
 * server has the final say and returns `dekor_exists`.
 */
const duplicateWarning = computed(() => {
  if (!form.manufacturerId) return null
  const kod = form.kod.trim().toLowerCase()
  const nomi = form.nomi.trim().toLowerCase()
  if (!kod && !nomi) return null
  const clash = admin.dekorlar.find((row) => {
    if (row.id === editingId.value) return false
    if (row.manufacturer_id !== form.manufacturerId || row.tur !== form.tur) return false
    return kod ? (row.kod ?? '').toLowerCase() === kod : !row.kod && row.nomi.toLowerCase() === nomi
  })
  return clash ? clash.label : null
})

function clearFilters() {
  search.value = ''
  statusFilter.value = 'all'
  turFilter.value = []
  manufacturerFilter.value = []
}

function openCreate() {
  editingId.value = null
  form.manufacturerId = admin.manufacturers.find((row) => row.status === 'active')?.id ?? ''
  form.tur = 'ldsp'
  form.kod = ''
  form.nomi = ''
  form.tolali = true
  form.imageFileId = null
  saveError.value = null
  uploadError.value = null
  imageUploadResetKey.value += 1
  clearFieldErrors(dekorFieldErrors)
  modalOpen.value = true
}

function openEdit(dekor: Dekor) {
  editingId.value = dekor.id
  form.manufacturerId = dekor.manufacturer_id
  form.tur = dekor.tur
  form.kod = dekor.kod ?? ''
  form.nomi = dekor.nomi
  form.tolali = dekor.tolali
  form.imageFileId = dekor.image_file_id
  saveError.value = null
  uploadError.value = null
  imageUploadResetKey.value += 1
  clearFieldErrors(dekorFieldErrors)
  modalOpen.value = true
}

function openInlineManufacturer() {
  clearFieldErrors(inlineManufacturerFieldErrors)
  manufacturerError.value = null
  manufacturerModalOpen.value = true
}

async function onDekorFile(file: File) {
  uploadError.value = null
  try {
    const uploaded = await files.upload(file)
    form.imageFileId = uploaded.id
    toast.success('Rasm yuklandi')
  } catch (error) {
    // The upload endpoint names its own refusals (wrong type, too large, storage
    // down); an operator who is told "rasmni yuklab bo'lmadi" retries the same
    // file forever (QAD-163).
    const message = adminErrorMessage(
      apiErrorCode(error),
      "Rasmni yuklab bo'lmadi. Boshqa fayl bilan qayta urinib ko'ring.",
    )
    uploadError.value = message
    imageUploadResetKey.value += 1
    toast.danger(message)
  }
}

function removeImage() {
  form.imageFileId = null
  uploadError.value = null
  imageUploadResetKey.value += 1
}

// `tur` renders as chips, not a <FormSelect>, so its required-ness cannot ride on
// the control's own `required` attribute — it is checked here, at form level.
function validateDekorForm() {
  clearFieldErrors(dekorFieldErrors)
  const set = (field: DekorField, error: string | null) => {
    if (error) dekorFieldErrors[field] = error
  }
  set('manufacturerId', requiredText(form.manufacturerId, 'Ishlab chiqaruvchini tanlang.'))
  set('tur', requiredText(form.tur, 'Turni tanlang.'))
  set('nomi', requiredText(form.nomi))
  const hasErrors = dekorFieldOrder.some((field) => Boolean(dekorFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(dekorFieldErrors, dekorFieldOrder, dekorFieldIds)
  return !hasErrors
}

async function save() {
  if (!validateDekorForm()) return
  saving.value = true
  saveError.value = null
  try {
    const payload = buildDekorWriteRequest(form)
    if (editingId.value) await admin.updateDekor(editingId.value, payload)
    else await admin.createDekor(payload)
    modalOpen.value = false
    toast.success(editingId.value ? 'Dekor yangilandi' : "Dekor qo'shildi")
  } catch (error) {
    const fields = fieldErrorsFromApi<DekorField>(error, dekorApiFieldMap, dekorApiLocMap)
    if (Object.keys(fields).length > 0) {
      Object.assign(dekorFieldErrors, fields)
      focusFirstFieldError(dekorFieldErrors, dekorFieldOrder, dekorFieldIds)
    } else {
      saveError.value = 'dekor_save_failed'
      toast.danger('Dekor saqlanmadi')
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

function askStatus(row: Dekor, status: MaterialStatus) {
  statusTarget.value = { row, status }
}

async function confirmStatus() {
  const target = statusTarget.value
  if (!target) return
  statusTarget.value = null
  actionId.value = target.row.id
  try {
    await admin.setDekorStatus(target.row.id, target.status)
    toast.success(target.status === 'active' ? 'Faollashtirildi' : 'Faol emas qilindi')
  } catch (error) {
    toast.danger(adminErrorMessage(apiErrorCode(error), "Dekor holatini o'zgartirib bo'lmadi."))
  } finally {
    actionId.value = null
  }
}

onMounted(async () => {
  await Promise.all([admin.loadManufacturers(), admin.loadDekorlar()])
})
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Dekorlar</h1>
      </div>
      <button type="button" class="admin-primary-action" @click="openCreate">+ Yangi dekor</button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span>Qidirish</span>
        <input v-model="search" placeholder="Dekor nomi yoki kodi" />
      </label>
      <MultiSelectFilter
        v-model="turFilter"
        label="Tur"
        :options="turOptions"
        empty-label="Hammasi"
        selected-label="tanlangan"
      />
      <MultiSelectFilter
        v-model="manufacturerFilter"
        label="Ishlab chiqaruvchilar"
        :options="manufacturerFilterOptions"
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
      v-if="admin.dekorlarLoading && admin.dekorlar.length === 0"
      class="admin-card p-5"
      aria-live="polite"
    >
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="admin.dekorlarError"
      :code="admin.dekorlarError"
      :trace-id="admin.dekorlarTraceId"
      title="Dekorlar yuklanmadi"
      @retry="reloadDekorlar()"
    />

    <section v-else-if="admin.dekorlar.length === 0" class="admin-empty">
      <template v-if="!hasActiveFilters">
        <h3>Dekor yo'q</h3>
        <p>Avval ishlab chiqaruvchi qo'shing, keyin dekor yarating.</p>
        <div class="mt-3 flex flex-wrap justify-center gap-2">
          <button type="button" class="admin-primary-action" @click="openCreate">
            + Yangi dekor
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
        <h3>Filtrlarga mos dekor yo'q</h3>
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
              <th>Dekor</th>
              <th>Ishlab chiqaruvchi</th>
              <th>Tur</th>
              <th>Tekstura</th>
              <th class="admin-right">Filiallar</th>
              <th>Holat</th>
              <th><span class="sr-only">Amallar</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="dekor in admin.dekorlar" :key="dekor.id">
              <td>
                <div class="admin-material-thumb">
                  <span
                    class="admin-material-thumb-swatch sw"
                    :class="materialSwatchClass(dekor)"
                    aria-hidden="true"
                  ></span>
                  <span class="admin-material-thumb-mark" aria-hidden="true">
                    {{ dekor.tur === 'kromka' ? 'K' : 'L' }}
                  </span>
                  <AuthFileImage
                    v-if="dekor.image_file_id"
                    :file-id="dekor.image_file_id"
                    :alt="dekor.label"
                    class="admin-material-thumb-img"
                  />
                </div>
              </td>
              <td class="nm">
                {{ dekor.nomi }}
                <small>{{ dekor.kod ?? "kod yo'q" }}</small>
              </td>
              <td>{{ dekor.manufacturer_name }}</td>
              <td>
                <span
                  class="admin-pill"
                  :class="dekor.tur === 'kromka' ? 'admin-pill-info' : 'admin-pill-success'"
                >
                  {{ dekorTurLabel(dekor.tur) }}
                </span>
              </td>
              <td>{{ dekor.tolali ? 'Bor' : "Yo'q" }}</td>
              <td class="admin-right admin-mono">{{ dekor.branch_usage_count }}</td>
              <td>
                <span class="admin-pill" :class="materialStatusTone(dekor.holat)">
                  {{ materialStatusLabel(dekor.holat) }}
                </span>
              </td>
              <td class="admin-right">
                <div class="flex flex-wrap justify-end gap-2">
                  <RouterLink
                    :to="rolePath(`/admin/catalog/dekorlar/${dekor.id}`)"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :aria-label="`${dekor.label} tafsilotlarini ochish`"
                  >
                    Tafsilotlar
                  </RouterLink>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :aria-label="`${dekor.label} dekorini tahrirlash`"
                    @click="openEdit(dekor)"
                  >
                    Tahrirlash
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :disabled="actionId === dekor.id"
                    :aria-label="
                      dekor.holat === 'active'
                        ? `${dekor.label} dekorini faol emas qilish`
                        : `${dekor.label} dekorini faollashtirish`
                    "
                    @click="askStatus(dekor, dekor.holat === 'active' ? 'inactive' : 'active')"
                  >
                    {{ dekor.holat === 'active' ? 'Faol emas qilish' : 'Faollashtirish' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="admin.dekorlarHasMore" class="mt-4 flex justify-center">
      <button
        type="button"
        class="mp-button mp-button-outline"
        :disabled="admin.dekorlarLoading"
        @click="loadMoreDekorlar"
      >
        {{ admin.dekorlarLoading ? 'Yuklanmoqda' : "Ko'proq yuklash" }}
      </button>
    </div>

    <template v-if="modalOpen">
      <div class="admin-modal-scrim" aria-hidden="true" @click="modalOpen = false"></div>
      <section
        ref="formPanel"
        class="admin-modal wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dekor-title"
        tabindex="-1"
        @keydown="formTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="dekor-title">{{ editingId ? 'Dekor tahrirlash' : 'Yangi dekor' }}</h3>
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
              <div class="admin-full grid gap-2 md:grid-cols-[1fr_auto]">
                <FormSelect
                  id="dek-manufacturer"
                  v-model="form.manufacturerId"
                  label="Ishlab chiqaruvchi"
                  :options="manufacturerChoiceOptions"
                  placeholder="Ishlab chiqaruvchini tanlang"
                  :error="dekorFieldErrors.manufacturerId"
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

              <!-- `tur` is a chip group, not a <FormSelect>: seven values the
                   operator compares side by side, and the choice drives which
                   formats a branch can register later. Plain toggle buttons —
                   Tab reaches each one — rather than role="radio", which would
                   promise arrow-key roving this does not implement. -->
              <div class="admin-field admin-full">
                <span id="dek-tur-label">Tur</span>
                <div
                  id="dek-tur"
                  class="flex flex-wrap gap-2"
                  role="group"
                  aria-labelledby="dek-tur-label"
                  tabindex="-1"
                >
                  <button
                    v-for="option in turOptions"
                    :key="option.value"
                    type="button"
                    class="mp-filter-chip"
                    :class="
                      form.tur === option.value
                        ? 'border-accent bg-accent-soft text-accent'
                        : undefined
                    "
                    :aria-pressed="form.tur === option.value"
                    @click="form.tur = option.value as DekorType"
                  >
                    <span class="mp-filter-chip-dot" aria-hidden="true"></span>
                    {{ option.label }}
                  </button>
                </div>
                <span v-if="dekorFieldErrors.tur" class="admin-field-error" role="alert">
                  {{ dekorFieldErrors.tur }}
                </span>
              </div>

              <label class="admin-field" for="dek-kod">
                <span>Kod</span>
                <input
                  id="dek-kod"
                  v-model="form.kod"
                  placeholder="H1334 ST9"
                  :aria-invalid="!!dekorFieldErrors.kod"
                  aria-describedby="dek-kod-error"
                />
                <span
                  v-if="dekorFieldErrors.kod"
                  id="dek-kod-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ dekorFieldErrors.kod }}
                </span>
              </label>

              <label class="admin-field" for="dek-nomi">
                <span>Nomi</span>
                <input
                  id="dek-nomi"
                  v-model="form.nomi"
                  required
                  placeholder="Dub Sonoma"
                  :aria-invalid="!!dekorFieldErrors.nomi"
                  aria-describedby="dek-nomi-error"
                />
                <span
                  v-if="dekorFieldErrors.nomi"
                  id="dek-nomi-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ dekorFieldErrors.nomi }}
                </span>
              </label>

              <label
                class="flex min-h-11 items-center gap-3 self-end rounded-md border border-hairline-strong px-3 text-sm font-bold"
              >
                <input v-model="form.tolali" type="checkbox" class="size-4 accent-accent" />
                Tekstura yo'nalishi bor
              </label>

              <div class="admin-field admin-full">
                <span>Dekor kartasi (avtomatik)</span>
                <div
                  class="flex items-center gap-3 rounded-md border border-hairline bg-sunk px-3 py-2"
                >
                  <span class="sw" :class="previewSwatchClass" aria-hidden="true"></span>
                  <span class="min-w-0">
                    <span class="block truncate text-sm font-bold text-ink">
                      {{ dekorLabelPreview }}
                    </span>
                    <span class="block text-xs font-bold text-ink-soft">
                      {{
                        form.tolali
                          ? $t('cutting.material.grained')
                          : $t('cutting.material.grainless')
                      }}
                    </span>
                  </span>
                </div>
              </div>

              <p
                v-if="duplicateWarning"
                class="admin-full rounded-md bg-warning-soft px-3 py-2 text-xs font-bold text-warning"
                role="status"
              >
                Shu ishlab chiqaruvchida bir xil tur va kod bilan dekor bor:
                {{ duplicateWarning }}. Saqlash rad etilishi mumkin.
              </p>

              <ImageUploadField
                id="dek-image"
                :file-id="form.imageFileId"
                :alt="dekorImageTitle"
                :title="dekorImageTitle"
                :meta="dekorImageMeta"
                :uploading="files.uploading"
                :error="uploadError"
                :reset-key="imageUploadResetKey"
                @select="onDekorFile"
                @remove="removeImage"
              />
            </div>
            <p
              v-if="saveError"
              class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Dekor saqlanmadi.
            </p>
          </div>
          <div class="admin-modal-f">
            <button type="button" class="mp-button mp-button-outline" @click="modalOpen = false">
              Bekor
            </button>
            <button
              type="submit"
              class="mp-button mp-button-primary"
              :disabled="saving || files.uploading"
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
          ? `${statusTarget?.row.label} faol emas qilinadi — uni filiallarning yangi tanlovlaridan yashiriladi; mavjud buyurtmalarga ta'sir qilmaydi.`
          : `${statusTarget?.row.label} faollashtiriladi va filial tanlovida ko'rinadi.`
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
