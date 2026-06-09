<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { branchPillClass, branchStatusUz } from '@/shared/app/workshopUi'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

const auth = useAuthStore()
const workshop = useWorkshopStore()
const rolePath = useRolePath()
const showCreate = ref(false)
const creatingBranch = ref(false)
const branchError = ref<string | null>(null)
const branchForm = reactive({
  name: '',
  address: '',
  phone: '+998',
  latitude: '41.2995',
  longitude: '69.2401',
})
const hours = reactive([
  { key: 'monday', label: 'Du', open: true, from: '09:00', to: '18:00' },
  { key: 'tuesday', label: 'Se', open: true, from: '09:00', to: '18:00' },
  { key: 'wednesday', label: 'Cho', open: true, from: '09:00', to: '18:00' },
  { key: 'thursday', label: 'Pa', open: true, from: '09:00', to: '18:00' },
  { key: 'friday', label: 'Ju', open: true, from: '09:00', to: '18:00' },
  { key: 'saturday', label: 'Sha', open: true, from: '10:00', to: '16:00' },
  { key: 'sunday', label: 'Yak', open: false, from: '10:00', to: '16:00' },
])

function workingHoursPayload() {
  return Object.fromEntries(
    hours.map((day) => [
      day.key,
      day.open ? { open: day.from, close: day.to } : { open: null, close: null },
    ]),
  )
}

async function createBranch() {
  creatingBranch.value = true
  branchError.value = null
  try {
    await workshop.createBranch({
      name: branchForm.name,
      address: branchForm.address,
      phone: branchForm.phone,
      latitude: branchForm.latitude,
      longitude: branchForm.longitude,
      working_hours: workingHoursPayload(),
    })
    branchForm.name = ''
    branchForm.address = ''
    branchForm.phone = '+998'
    branchForm.latitude = '41.2995'
    branchForm.longitude = '69.2401'
    showCreate.value = false
  } catch {
    branchError.value = 'branch_create_failed'
  } finally {
    creatingBranch.value = false
  }
}

onMounted(() => {
  if (auth.me?.is_owner) void workshop.loadManagedBranches()
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Filiallar</h1>
        <p class="sub">
          {{ workshop.managedBranches.length }} filial · har birining materiali va narxi alohida.
        </p>
      </div>
      <div class="tools">
        <button
          v-if="auth.me?.is_owner"
          type="button"
          class="mp-button mp-button-primary"
          @click="showCreate = !showCreate"
        >
          Yangi filial
        </button>
      </div>
    </div>

    <section v-if="!auth.me?.is_owner" class="st-empty">
      <h3>Bu bo'lim faqat ustaxona egasi uchun</h3>
      <p>Filial yaratish va holatini boshqarish egaga tegishli.</p>
    </section>

    <template v-else>
      <section v-if="showCreate" class="card mb-5">
        <div class="card-h">
          <h2>Yangi filial</h2>
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            @click="showCreate = false"
          >
            Bekor
          </button>
        </div>
        <form
          class="card-b grid gap-3 md:grid-cols-2 xl:grid-cols-4"
          @submit.prevent="createBranch"
        >
          <label class="field">
            <span>Nom</span>
            <input v-model="branchForm.name" class="mp-input" placeholder="Sergeli" required />
          </label>
          <label class="field">
            <span>Telefon</span>
            <input v-model="branchForm.phone" class="mp-input" required />
          </label>
          <label class="field">
            <span>Lat</span>
            <input v-model="branchForm.latitude" class="mp-input" inputmode="decimal" required />
          </label>
          <label class="field">
            <span>Lng</span>
            <input v-model="branchForm.longitude" class="mp-input" inputmode="decimal" required />
          </label>
          <label class="field md:col-span-2 xl:col-span-4">
            <span>Manzil</span>
            <input
              v-model="branchForm.address"
              class="mp-input"
              placeholder="Sergeli 1-mavze 4"
              required
            />
          </label>
          <fieldset class="md:col-span-2 xl:col-span-4">
            <legend class="mb-2 text-sm font-extrabold text-ink">Ish vaqti</legend>
            <div class="grid gap-2 md:grid-cols-2 xl:grid-cols-7">
              <div
                v-for="day in hours"
                :key="day.key"
                class="rounded-md border border-hairline bg-sunk p-3"
              >
                <label class="flex items-center gap-2 text-sm font-extrabold text-ink">
                  <input v-model="day.open" type="checkbox" class="size-4 accent-accent" />
                  {{ day.label }}
                </label>
                <div class="mt-2 grid grid-cols-2 gap-2">
                  <input
                    v-model="day.from"
                    class="mp-input min-h-9 px-2 text-sm"
                    type="time"
                    :disabled="!day.open"
                  />
                  <input
                    v-model="day.to"
                    class="mp-input min-h-9 px-2 text-sm"
                    type="time"
                    :disabled="!day.open"
                  />
                </div>
              </div>
            </div>
          </fieldset>
          <button
            type="submit"
            class="mp-button mp-button-primary md:col-span-2 xl:col-span-4"
            :disabled="creatingBranch"
          >
            {{ creatingBranch ? 'Yaratilmoqda' : 'Yaratish' }}
          </button>
          <p
            v-if="branchError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger md:col-span-2 xl:col-span-4"
          >
            Filial yaratilmadi.
          </p>
        </form>
      </section>

      <section v-if="workshop.setupLoading" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="workshop.setupError" class="st-error">
        <h3>Filiallarni yuklab bo'lmadi</h3>
        <p>trace_id: {{ workshop.setupTraceId ?? 'unavailable' }}</p>
      </section>

      <section v-else-if="workshop.managedBranches.length === 0" class="st-empty">
        <h3>Hali filial yo'q</h3>
        <p>Birinchi filial yaratilgach, mijozlar buyurtma beradigan manzil paydo bo'ladi.</p>
      </section>

      <div v-else class="br-grid">
        <RouterLink
          v-for="branch in workshop.managedBranches"
          :key="branch.id"
          :to="rolePath(`/workshop/branches/${branch.id}`)"
          class="br-card"
        >
          <div class="top">
            <div class="min-w-0">
              <h3>{{ branch.name }}</h3>
              <div class="addr">{{ branch.address }} · {{ branch.phone }}</div>
            </div>
            <span :class="branchPillClass(branch.status)">
              <span class="pd"></span>{{ branchStatusUz[branch.status] }}
            </span>
          </div>
          <div class="kpi-grid">
            <div>
              <div class="l">Faol buyurtma</div>
              <div class="v">{{ branch.active_orders_count }}</div>
            </div>
            <div>
              <div class="l">Holat</div>
              <div class="v text-base">{{ branch.status === 'active' ? 'OK' : '!' }}</div>
            </div>
            <div>
              <div class="l">Materiallar</div>
              <div class="v text-base">Boshqarish</div>
            </div>
            <div>
              <div class="l">Xodimlar</div>
              <div class="v text-base">Ruxsatlar</div>
            </div>
          </div>
        </RouterLink>
      </div>
    </template>
  </section>
</template>
