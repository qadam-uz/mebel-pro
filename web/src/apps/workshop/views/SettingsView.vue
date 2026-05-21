<script setup lang="ts">
// Settings → Profile (owner-only) — workshop profile (name, phone, address).
// Mirrors prototype workshop/settings.html.
import { onMounted, ref } from 'vue'
import { ApiError } from '@/shared/api'
import { ErrorState, FormField } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { useToast } from '@/shared/composables/useToast'
import * as api from '../api'

const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const saving = ref(false)
const form = ref({ name: '', phone: '', address: '' })

async function load() {
  loading.value = true
  error.value = null
  try {
    const p = await api.getWorkshopProfile()
    form.value = { name: p.name, phone: p.phone, address: p.address ?? '' }
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await api.editWorkshopProfile({
      name: form.value.name.trim(),
      phone: form.value.phone.trim(),
      address: form.value.address.trim() || null,
    })
    toast.ok(t('workshop.profileSaved'))
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('workshop.settingsTitle') }}</h1>
        <p class="sub">{{ t('workshop.settingsSub') }}</p>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />
    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 50%" /></div>
    </div>
    <section v-else class="card">
      <div class="card-b">
        <FormField v-model="form.name" :label="t('workshop.workshopName')" required />
        <FormField v-model="form.phone" :label="t('workshop.workshopPhone')" required />
        <FormField v-model="form.address" :label="t('workshop.workshopAddress')" />
        <button
          class="btn btn-acc btn-sm"
          type="button"
          :disabled="saving || !form.name.trim() || !form.phone.trim()"
          @click="save"
        >
          {{ t('common.save') }}
        </button>
      </div>
    </section>
  </div>
</template>
