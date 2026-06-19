<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import { apiTraceId } from '@/shared/api/client'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import { useToast } from '@/shared/composables/useToast'
import { useAuthStore } from '@/shared/stores/auth'
import { useFilesStore } from '@/shared/stores/files'
import { useWorkshopStore } from '@/shared/stores/workshop'

const auth = useAuthStore()
const workshop = useWorkshopStore()
const files = useFilesStore()
const toast = useToast()
const form = reactive({
  name: '',
  phone: '',
  address: '',
  logoFileId: '',
})

watch(
  () => workshop.settings,
  (settings) => {
    if (!settings) return
    form.name = settings.name
    form.phone = settings.phone
    form.address = settings.address ?? ''
    form.logoFileId = settings.logo_file_id ?? ''
  },
  { immediate: true },
)

const saving = ref(false)
const saveError = ref<string | null>(null)
const saveTraceId = ref<string | null>(null)
const logoError = ref<string | null>(null)
const saved = ref(false)

async function onLogoFile(event: Event) {
  const target = event.target as HTMLInputElement
  logoError.value = null
  const file = target.files?.[0]
  if (!file) return
  try {
    const uploaded = await files.upload(file)
    form.logoFileId = uploaded.id
    saved.value = false
    toast.success('Logo yuklandi. Saqlashni unutmang.')
  } catch {
    logoError.value = files.traceId
      ? `Logoni yuklab bo'lmadi · trace_id: ${files.traceId}`
      : "Logoni yuklab bo'lmadi"
  } finally {
    target.value = ''
  }
}

function removeLogo() {
  form.logoFileId = ''
  saved.value = false
  logoError.value = null
}

async function save() {
  saving.value = true
  saveError.value = null
  saved.value = false
  try {
    await workshop.updateSettings({
      name: form.name,
      phone: form.phone,
      address: form.address || null,
      logo_file_id: form.logoFileId || null,
    })
    saved.value = true
    toast.success('Ustaxona sozlamalari saqlandi.')
  } catch (caught) {
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
        <p class="sub">Ustaxona profili — nom, logo, telefon, manzil.</p>
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

    <form v-else class="card max-w-[720px]" @submit.prevent="save">
      <div class="card-h"><h2>Ustaxona profili</h2></div>
      <div class="card-b">
        <label class="field">
          <span>Ustaxona nomi</span>
          <input v-model="form.name" class="mp-input" required />
        </label>
        <label class="field">
          <span>Telefon</span>
          <input v-model="form.phone" class="mp-input" required />
        </label>
        <label class="field">
          <span>Manzil</span>
          <input v-model="form.address" class="mp-input" />
        </label>
        <div class="field">
          <label for="workshop-logo-upload">Logo</label>
          <div
            class="flex flex-col gap-3 rounded-md border border-hairline-strong bg-elevated p-3 sm:flex-row sm:items-center"
          >
            <div
              class="grid h-20 w-20 shrink-0 place-items-center overflow-hidden rounded-md border border-hairline bg-sunk"
            >
              <AuthFileImage
                v-if="form.logoFileId"
                :file-id="form.logoFileId"
                alt="Ustaxona logosi"
                class="h-full w-full object-contain"
              />
              <span v-else class="px-2 text-center text-xs font-bold text-ink-muted">
                Logo yo'q
              </span>
            </div>
            <div class="min-w-0 flex-1">
              <input
                id="workshop-logo-upload"
                class="block min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 py-2 text-sm"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                :disabled="files.uploading"
                @change="onLogoFile"
              />
              <p v-if="logoError" class="mt-2 text-xs font-bold text-danger">
                {{ logoError }}
              </p>
              <p v-else class="mt-2 text-xs text-ink-muted">
                PNG, JPG yoki WebP. Saqlash bosilgandan keyin logo profilga biriktiriladi.
              </p>
              <button
                v-if="form.logoFileId"
                type="button"
                class="mt-3 text-sm font-bold text-danger hover:underline"
                @click="removeLogo"
              >
                Logoni olib tashlash
              </button>
            </div>
          </div>
        </div>
        <div class="flex items-center justify-end gap-3">
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
