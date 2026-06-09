<script setup lang="ts">
import { onMounted, reactive, watch } from 'vue'

import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

const auth = useAuthStore()
const workshop = useWorkshopStore()
const form = reactive({
  name: '',
  phone: '',
  address: '',
})

watch(
  () => workshop.settings,
  (settings) => {
    if (!settings) return
    form.name = settings.name
    form.phone = settings.phone
    form.address = settings.address ?? ''
  },
  { immediate: true },
)

async function save() {
  await workshop.updateSettings({
    name: form.name,
    phone: form.phone,
    address: form.address || null,
  })
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
        <label class="field">
          <span>Logo</span>
          <input class="mp-input" type="file" />
        </label>
        <div class="flex justify-end">
          <button class="mp-button mp-button-primary" type="submit">Saqlash</button>
        </div>
      </div>
    </form>
  </section>
</template>
