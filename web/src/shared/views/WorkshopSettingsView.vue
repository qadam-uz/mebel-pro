<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import { apiTraceId } from '@/shared/api/client'
import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import ImageUploadField from '@/shared/components/ImageUploadField.vue'
import { useToast } from '@/shared/composables/useToast'
import { useAuthStore } from '@/shared/stores/auth'
import { useFilesStore } from '@/shared/stores/files'
import { useWorkshopStore } from '@/shared/stores/workshop'

type SettingsField = 'name'

const auth = useAuthStore()
const workshop = useWorkshopStore()
const files = useFilesStore()
const toast = useToast()
const form = reactive({
  name: '',
  logoFileId: '',
})
const fieldErrors = reactive<FieldErrors<SettingsField>>({})
const fieldOrder: SettingsField[] = ['name']
const fieldIds: Record<SettingsField, string> = {
  name: 'workshop-settings-name',
}

watch(
  () => workshop.settings,
  (settings) => {
    if (!settings) return
    form.name = settings.name
    form.logoFileId = settings.logo_file_id ?? ''
  },
  { immediate: true },
)

const saving = ref(false)
const saveError = ref<string | null>(null)
const saveTraceId = ref<string | null>(null)
const logoError = ref<string | null>(null)
const saved = ref(false)

async function onLogoSelect(file: File) {
  logoError.value = null
  try {
    const uploaded = await files.upload(file)
    form.logoFileId = uploaded.id
    saved.value = false
    toast.success('Logo yuklandi. Saqlashni unutmang.')
  } catch {
    logoError.value = files.traceId
      ? `Logoni yuklab bo'lmadi · trace_id: ${files.traceId}`
      : "Logoni yuklab bo'lmadi"
  }
}

function removeLogo() {
  form.logoFileId = ''
  saved.value = false
  logoError.value = null
}

function validateSettingsForm() {
  clearFieldErrors(fieldErrors)
  fieldErrors.name = requiredText(form.name) ?? undefined
  const hasErrors = fieldOrder.some((field) => Boolean(fieldErrors[field]))
  if (hasErrors) focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
  return !hasErrors
}

async function save() {
  if (!validateSettingsForm()) return
  saving.value = true
  saveError.value = null
  saved.value = false
  try {
    await workshop.updateSettings({
      name: form.name,
      logo_file_id: form.logoFileId || null,
    })
    saved.value = true
    toast.success('Ustaxona sozlamalari saqlandi.')
  } catch (caught) {
    Object.assign(
      fieldErrors,
      fieldErrorsFromApi<SettingsField>(
        caught,
        { workshop_name_required: 'name' },
        { name: 'name' },
      ),
    )
    if (fieldErrors.name) focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
    saveError.value = 'settings_save_failed'
    saveTraceId.value = apiTraceId(caught)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void workshop.loadSettings()
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Ustaxona sozlamalari</h1>
      </div>
    </div>

    <div v-if="!auth.me?.is_owner" class="st-empty">
      <h3>Bu sahifa faqat ustaxona egasiga ochiq</h3>
      <p>Sizda bu bo'limni ko'rish uchun ruxsat yo'q — ustaxona egasiga murojaat qiling.</p>
    </div>

    <div v-else-if="workshop.setupLoading" class="card max-w-[720px] p-5" aria-live="polite">
      <span class="sk-line"></span>
      <span class="sk-line mt-3"></span>
      <span class="sk-line mt-3"></span>
    </div>

    <div v-else-if="workshop.setupError" class="st-error max-w-[720px]">
      <h3>Sozlamalarni yuklab bo'lmadi</h3>
      <p>trace_id: {{ workshop.setupTraceId ?? 'unavailable' }}</p>
    </div>

    <form v-else class="card max-w-[720px]" novalidate @submit.prevent="save">
      <div class="card-h"><h2>Ustaxona profili</h2></div>
      <div class="card-b">
        <label class="field" for="workshop-settings-name">
          <span>Ustaxona nomi</span>
          <input
            id="workshop-settings-name"
            v-model="form.name"
            class="mp-input"
            required
            :aria-invalid="!!fieldErrors.name"
            :aria-describedby="fieldErrors.name ? 'workshop-settings-name-error' : undefined"
          />
          <span v-if="fieldErrors.name" id="workshop-settings-name-error" class="mp-field-error">
            {{ fieldErrors.name }}
          </span>
        </label>
        <ImageUploadField
          id="workshop-logo-upload"
          :file-id="form.logoFileId || null"
          alt="Ustaxona logosi"
          label="Logo"
          title="Ustaxona logotipi"
          accept="image/png,image/jpeg,image/webp"
          helper="PNG, JPG yoki WebP. Saqlashdan keyin logo profilga biriktiriladi."
          :uploading="files.uploading"
          :error="logoError"
          @select="onLogoSelect"
          @remove="removeLogo"
        />
        <div class="mt-5 flex items-center justify-end gap-3">
          <p v-if="saved" class="text-sm font-bold text-success">Saqlandi</p>
          <p v-else-if="saveError" class="text-sm font-bold text-danger">
            Saqlab bo'lmadi · trace_id: {{ saveTraceId ?? 'unavailable' }}
          </p>
          <button class="mp-button mp-button-primary" type="submit" :disabled="saving">
            {{ saving ? 'Saqlanmoqda' : 'Saqlash' }}
          </button>
        </div>
      </div>
    </form>
  </section>
</template>
