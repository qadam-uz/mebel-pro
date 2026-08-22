<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { buildDecorWriteRequest, composeDecorLabel } from '@/shared/app/adminDecors'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { DECOR_TYPES, decorTypeLabel } from '@/shared/app/materialLabel'
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
  type Decor,
  type DecorFilters,
  type DecorType,
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
const statusTarget = ref<{ row: Decor; status: MaterialStatus } | null>(null)
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

// A decor is identity only: manufacturer, type, code, name, has_grain, rasm. Thickness,
// sizes and price belong to the branch row that carries the decor, so none of them
// have an input here — that split is the whole point of the catalog reshape.
const form = reactive({
  manufacturerId: '',
  code: '',
  name: '',
  has_grain: true,
  imageFileId: null as string | null,
})
const manufacturerForm = reactive({
  name: '',
  country: '',
  note: '',
})
type DecorField = 'manufacturerId' | 'code' | 'name'
type InlineManufacturerField = 'name'
const decorFieldErrors = reactive<FieldErrors<DecorField>>({})
const inlineManufacturerFieldErrors = reactive<FieldErrors<InlineManufacturerField>>({})
const decorFieldIds: Record<DecorField, string> = {
  manufacturerId: 'dek-manufacturer',
  code: 'dek-code',
  name: 'dek-name',
}
const decorFieldOrder: DecorField[] = ['manufacturerId', 'code', 'name']
const decorApiFieldMap: Partial<Record<string, DecorField>> = {
  manufacturer_not_found: 'manufacturerId',
  decor_name_required: 'name',
  // The (manufacturer, code) uniqueness conflict — anchor it on the code, which
  // is the field the operator changes to resolve it. `type` left this identity
  // with the format reshape.
  decor_exists: 'code',
}
const decorApiLocMap: Partial<Record<string, DecorField>> = {
  'body.manufacturer_id': 'manufacturerId',
  'body.code': 'code',
  'body.name': 'name',
}

const turOptions = computed<ChoiceOption[]>(() =>
  DECOR_TYPES.map((type) => ({ value: type, label: decorTypeLabel(type) })),
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

function currentFilters(): DecorFilters {
  return {
    search: search.value.trim() || undefined,
    types: turFilter.value.length ? (turFilter.value as DecorType[]) : undefined,
    status: statusFilter.value === 'all' ? undefined : (statusFilter.value as MaterialStatus),
    manufacturerIds: manufacturerFilter.value.length ? manufacturerFilter.value : undefined,
  }
}

function reloadDecors() {
  void admin.loadDecors(currentFilters())
}

function loadMoreDecors() {
  void admin.loadDecors({ ...currentFilters(), offset: admin.decors.length })
}

let searchTimer: number | undefined
watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(reloadDecors, SEARCH_DEBOUNCE_MS)
})
watch([turFilter, statusFilter, manufacturerFilter], reloadDecors)

const selectedManufacturerName = computed(
  () => admin.manufacturers.find((manufacturer) => manufacturer.id === form.manufacturerId)?.name,
)
const decorLabelPreview = computed(() => composeDecorLabel(form, selectedManufacturerName.value))
const decorImageTitle = computed(() => decorLabelPreview.value || 'Dekor rasmi')
// Only the maker: a decor is identity, and the substrate belongs to its formats.
const decorImageMeta = computed(() => selectedManufacturerName.value ?? '')
// The swatch is what the operator recognises the decor by before the photo
// uploads, so the preview card shows the same one the table will.
const previewSwatchClass = computed(() =>
  materialSwatchClass({
    id: editingId.value ?? 'preview',
    name: form.name,
    code: form.code || null,
  }),
)

/**
 * Warns on the (manufacturer, type, code) triple the backend enforces — and, for a
 * decor with no code, on the (manufacturer, type, name) triple the second partial
 * index covers. It is a WARNING, not a gate: the check can only see the page
 * currently loaded, so a real duplicate three pages down would pass silently. The
 * server has the final say and returns `decor_exists`.
 */
const duplicateWarning = computed(() => {
  if (!form.manufacturerId) return null
  const code = form.code.trim().toLowerCase()
  const name = form.name.trim().toLowerCase()
  if (!code && !name) return null
  const clash = admin.decors.find((row) => {
    if (row.id === editingId.value) return false
    if (row.manufacturer_id !== form.manufacturerId) return false
    return code
      ? (row.code ?? '').toLowerCase() === code
      : !row.code && row.name.toLowerCase() === name
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
  form.code = ''
  form.name = ''
  form.has_grain = true
  form.imageFileId = null
  saveError.value = null
  uploadError.value = null
  imageUploadResetKey.value += 1
  clearFieldErrors(decorFieldErrors)
  modalOpen.value = true
}

function openEdit(decor: Decor) {
  editingId.value = decor.id
  form.manufacturerId = decor.manufacturer_id
  form.code = decor.code ?? ''
  form.name = decor.name
  form.has_grain = decor.has_grain
  form.imageFileId = decor.image_file_id
  saveError.value = null
  uploadError.value = null
  imageUploadResetKey.value += 1
  clearFieldErrors(decorFieldErrors)
  modalOpen.value = true
}

function openInlineManufacturer() {
  clearFieldErrors(inlineManufacturerFieldErrors)
  manufacturerError.value = null
  manufacturerModalOpen.value = true
}

async function onDecorFile(file: File) {
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

// `type` renders as chips, not a <FormSelect>, so its required-ness cannot ride on
// the control's own `required` attribute — it is checked here, at form level.
function validateDecorForm() {
  clearFieldErrors(decorFieldErrors)
  const set = (field: DecorField, error: string | null) => {
    if (error) decorFieldErrors[field] = error
  }
  set('manufacturerId', requiredText(form.manufacturerId, 'Ishlab chiqaruvchini tanlang.'))
  set('name', requiredText(form.name))
  const hasErrors = decorFieldOrder.some((field) => Boolean(decorFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(decorFieldErrors, decorFieldOrder, decorFieldIds)
  return !hasErrors
}

async function save() {
  if (!validateDecorForm()) return
  saving.value = true
  saveError.value = null
  try {
    const payload = buildDecorWriteRequest(form)
    if (editingId.value) await admin.updateDecor(editingId.value, payload)
    else await admin.createDecor(payload)
    modalOpen.value = false
    toast.success(editingId.value ? 'Dekor yangilandi' : "Dekor qo'shildi")
  } catch (error) {
    const fields = fieldErrorsFromApi<DecorField>(error, decorApiFieldMap, decorApiLocMap)
    if (Object.keys(fields).length > 0) {
      Object.assign(decorFieldErrors, fields)
      focusFirstFieldError(decorFieldErrors, decorFieldOrder, decorFieldIds)
    } else {
      saveError.value = 'decor_save_failed'
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

function askStatus(row: Decor, status: MaterialStatus) {
  statusTarget.value = { row, status }
}

async function confirmStatus() {
  const target = statusTarget.value
  if (!target) return
  statusTarget.value = null
  actionId.value = target.row.id
  try {
    await admin.setDecorStatus(target.row.id, target.status)
    toast.success(target.status === 'active' ? 'Faollashtirildi' : 'Faol emas qilindi')
  } catch (error) {
    toast.danger(adminErrorMessage(apiErrorCode(error), "Dekor holatini o'zgartirib bo'lmadi."))
  } finally {
    actionId.value = null
  }
}

onMounted(async () => {
  await Promise.all([admin.loadManufacturers(), admin.loadDecors()])
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
      v-if="admin.decorsLoading && admin.decors.length === 0"
      class="admin-card p-5"
      aria-live="polite"
    >
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="admin.decorsError"
      :code="admin.decorsError"
      :trace-id="admin.decorsTraceId"
      title="Dekors yuklanmadi"
      @retry="reloadDecors()"
    />

    <section v-else-if="admin.decors.length === 0" class="admin-empty">
      <template v-if="!hasActiveFilters">
        <h3>Dekor yo'q</h3>
        <p>Avval ishlab chiqaruvchi qo'shing, keyin decor yarating.</p>
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
        <h3>Filtrlarga mos decor yo'q</h3>
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
              <th class="admin-right">Formatlar</th>
              <th>Tekstura</th>
              <th class="admin-right">Filiallar</th>
              <th>Holat</th>
              <th><span class="sr-only">Amallar</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="decor in admin.decors" :key="decor.id">
              <td>
                <div class="admin-material-thumb">
                  <span
                    class="admin-material-thumb-swatch sw"
                    :class="materialSwatchClass(decor)"
                    aria-hidden="true"
                  ></span>
                  <AuthFileImage
                    v-if="decor.image_file_id"
                    :file-id="decor.image_file_id"
                    :alt="decor.label"
                    class="admin-material-thumb-img"
                  />
                </div>
              </td>
              <td class="nm">
                {{ decor.name }}
                <small>{{ decor.code ?? "code yo'q" }}</small>
              </td>
              <td>{{ decor.manufacturer_name }}</td>
              <!-- A decor with no format is a name nobody can attach anything
                   of, so the count is the "is this entry finished" signal. -->
              <td class="admin-right admin-mono">{{ decor.format_count }}</td>
              <td>{{ decor.has_grain ? 'Bor' : "Yo'q" }}</td>
              <td class="admin-right admin-mono">{{ decor.branch_usage_count }}</td>
              <td>
                <span class="admin-pill" :class="materialStatusTone(decor.status)">
                  {{ materialStatusLabel(decor.status) }}
                </span>
              </td>
              <td class="admin-right">
                <div class="flex flex-wrap justify-end gap-2">
                  <RouterLink
                    :to="rolePath(`/admin/catalog/decors/${decor.id}`)"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :aria-label="`${decor.label} tafsilotlarini ochish`"
                  >
                    Tafsilotlar
                  </RouterLink>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :aria-label="`${decor.label} dekorini tahrirlash`"
                    @click="openEdit(decor)"
                  >
                    Tahrirlash
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :disabled="actionId === decor.id"
                    :aria-label="
                      decor.status === 'active'
                        ? `${decor.label} decorini faol emas qilish`
                        : `${decor.label} decorini faollashtirish`
                    "
                    @click="askStatus(decor, decor.status === 'active' ? 'inactive' : 'active')"
                  >
                    {{ decor.status === 'active' ? 'Faol emas qilish' : 'Faollashtirish' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="admin.decorsHasMore" class="mt-4 flex justify-center">
      <button
        type="button"
        class="mp-button mp-button-outline"
        :disabled="admin.decorsLoading"
        @click="loadMoreDecors"
      >
        {{ admin.decorsLoading ? 'Yuklanmoqda' : "Ko'proq yuklash" }}
      </button>
    </div>

    <template v-if="modalOpen">
      <div class="admin-modal-scrim" aria-hidden="true" @click="modalOpen = false"></div>
      <section
        ref="formPanel"
        class="admin-modal wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="decor-title"
        tabindex="-1"
        @keydown="formTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="decor-title">{{ editingId ? 'Dekor tahrirlash' : 'Yangi dekor' }}</h3>
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
                  :error="decorFieldErrors.manufacturerId"
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

              <label class="admin-field" for="dek-code">
                <span>Kod</span>
                <input
                  id="dek-code"
                  v-model="form.code"
                  placeholder="H1334 ST9"
                  :aria-invalid="!!decorFieldErrors.code"
                  aria-describedby="dek-code-error"
                />
                <span
                  v-if="decorFieldErrors.code"
                  id="dek-code-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ decorFieldErrors.code }}
                </span>
              </label>

              <label class="admin-field" for="dek-name">
                <span>Nomi</span>
                <input
                  id="dek-name"
                  v-model="form.name"
                  required
                  placeholder="Dub Sonoma"
                  :aria-invalid="!!decorFieldErrors.name"
                  aria-describedby="dek-name-error"
                />
                <span
                  v-if="decorFieldErrors.name"
                  id="dek-name-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ decorFieldErrors.name }}
                </span>
              </label>

              <label
                class="flex min-h-11 items-center gap-3 self-end rounded-md border border-hairline-strong px-3 text-sm font-bold"
              >
                <input v-model="form.has_grain" type="checkbox" class="size-4 accent-accent" />
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
                      {{ decorLabelPreview }}
                    </span>
                    <span class="block text-xs font-bold text-ink-soft">
                      {{
                        form.has_grain
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
                Shu ishlab chiqaruvchida shu kod bilan dekor bor:
                {{ duplicateWarning }}. Saqlash rad etilishi mumkin.
              </p>

              <ImageUploadField
                id="dek-image"
                :file-id="form.imageFileId"
                :alt="decorImageTitle"
                :title="decorImageTitle"
                :meta="decorImageMeta"
                :uploading="files.uploading"
                :error="uploadError"
                :reset-key="imageUploadResetKey"
                @select="onDecorFile"
                @remove="removeImage"
              />
            </div>
            <p
              v-if="saveError"
              class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Decor saqlanmadi.
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
