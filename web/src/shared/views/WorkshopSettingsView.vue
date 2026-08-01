<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { apiTraceId } from '@/shared/api/client'
import { traceLine, traceSuffix } from '@/shared/app/errorTrace'
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
const { t } = useI18n()
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
    toast.success(t('workshopAdmin.settings.logoUploaded'))
  } catch {
    logoError.value = t('workshopAdmin.settings.logoUploadFailed') + traceSuffix(files.traceId)
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
    toast.success(t('workshopAdmin.settings.saved'))
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
        <h1>{{ $t('workshopAdmin.settings.title') }}</h1>
      </div>
    </div>

    <div v-if="!auth.me?.is_owner" class="st-empty">
      <h3>{{ $t('workshopAdmin.settings.ownerOnlyTitle') }}</h3>
      <p>{{ $t('workshopAdmin.settings.ownerOnlyBody') }}</p>
    </div>

    <div v-else-if="workshop.setupLoading" class="card max-w-[720px] p-5" aria-live="polite">
      <span class="sk-line"></span>
      <span class="sk-line mt-3"></span>
      <span class="sk-line mt-3"></span>
    </div>

    <div v-else-if="workshop.setupError" class="st-error max-w-[720px]">
      <h3>{{ $t('workshopAdmin.settings.loadFailed') }}</h3>
      <p>{{ traceLine(workshop.setupTraceId) }}</p>
    </div>

    <form v-else class="card max-w-[720px]" novalidate @submit.prevent="save">
      <div class="card-b">
        <label class="field" for="workshop-settings-name">
          <span>{{ $t('workshopAdmin.settings.name') }}</span>
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
          :alt="$t('workshopAdmin.settings.logoAlt')"
          :label="$t('workshopAdmin.settings.logoLabel')"
          :title="$t('workshopAdmin.settings.logoTitle')"
          accept="image/png,image/jpeg,image/webp"
          :helper="$t('workshopAdmin.settings.logoHelper')"
          :uploading="files.uploading"
          :error="logoError"
          @select="onLogoSelect"
          @remove="removeLogo"
        />
        <div class="mt-5 flex items-center justify-end gap-3">
          <p v-if="saved" class="text-sm font-bold text-success">
            {{ $t('workshopAdmin.action.saved') }}
          </p>
          <p v-else-if="saveError" class="text-sm font-bold text-danger">
            {{ $t('workshopAdmin.action.saveFailed') }}{{ traceSuffix(saveTraceId) }}
          </p>
          <button class="mp-button mp-button-primary" type="submit" :disabled="saving">
            {{ saving ? $t('workshopAdmin.action.saving') : $t('workshopAdmin.action.save') }}
          </button>
        </div>
      </div>
    </form>
  </section>
</template>
