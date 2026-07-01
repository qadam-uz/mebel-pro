<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  clearFieldErrors,
  coordinateFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  type FieldErrors,
  uzPhone,
} from '@/shared/app/adminValidation'
import { useRolePath } from '@/shared/app/paths'
import { branchPillClass, branchStatusUz } from '@/shared/app/workshopUi'
import { useToast } from '@/shared/composables/useToast'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

type BranchField = 'name' | 'address' | 'phone' | 'latitude' | 'longitude'

const auth = useAuthStore()
const workshop = useWorkshopStore()
const rolePath = useRolePath()
const toast = useToast()
const showCreate = ref(false)
const creatingBranch = ref(false)
const branchError = ref<string | null>(null)
const branchForm = reactive({
  name: '',
  address: '',
  phone: '+998',
  latitude: '',
  longitude: '',
})
const branchFieldErrors = reactive<FieldErrors<BranchField>>({})
const branchFieldOrder: BranchField[] = ['name', 'address', 'phone', 'latitude', 'longitude']
const branchFieldIds: Record<BranchField, string> = {
  name: 'branch-name',
  phone: 'branch-phone',
  latitude: 'branch-latitude',
  longitude: 'branch-longitude',
  address: 'branch-address',
}
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

function validateBranchForm() {
  clearFieldErrors(branchFieldErrors)
  branchFieldErrors.name = requiredText(branchForm.name) ?? undefined
  branchFieldErrors.address = requiredText(branchForm.address) ?? undefined
  branchFieldErrors.phone = requiredText(branchForm.phone) ?? uzPhone(branchForm.phone) ?? undefined
  const coords = coordinateFieldErrors(branchForm.latitude, branchForm.longitude)
  branchFieldErrors.latitude = coords.latitude ?? undefined
  branchFieldErrors.longitude = coords.longitude ?? undefined
  const hasErrors = branchFieldOrder.some((field) => Boolean(branchFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(branchFieldErrors, branchFieldOrder, branchFieldIds)
  return !hasErrors
}

function optionalCoordinate(value: string) {
  return value.trim() || null
}

async function createBranch() {
  if (!validateBranchForm()) return
  creatingBranch.value = true
  branchError.value = null
  try {
    await workshop.createBranch({
      name: branchForm.name,
      address: branchForm.address,
      phone: branchForm.phone,
      latitude: optionalCoordinate(branchForm.latitude),
      longitude: optionalCoordinate(branchForm.longitude),
      working_hours: workingHoursPayload(),
    })
    branchForm.name = ''
    branchForm.address = ''
    branchForm.phone = '+998'
    branchForm.latitude = ''
    branchForm.longitude = ''
    showCreate.value = false
    toast.success("Filial qo'shildi.")
  } catch (caught) {
    Object.assign(
      branchFieldErrors,
      fieldErrorsFromApi<BranchField>(
        caught,
        {
          branch_name_required: 'name',
          branch_address_required: 'address',
          invalid_phone: 'phone',
          invalid_coordinates: 'latitude',
          invalid_latitude: 'latitude',
          invalid_longitude: 'longitude',
        },
        {
          name: 'name',
          phone: 'phone',
          latitude: 'latitude',
          longitude: 'longitude',
          address: 'address',
        },
      ),
    )
    if (branchFieldOrder.some((field) => Boolean(branchFieldErrors[field]))) {
      focusFirstFieldError(branchFieldErrors, branchFieldOrder, branchFieldIds)
    }
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
      <section v-if="showCreate" class="card mb-5 max-w-[1120px]">
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
        <form class="card-b grid gap-3" novalidate @submit.prevent="createBranch">
          <div class="grid gap-3 md:grid-cols-2">
            <label class="field" for="branch-name">
              <span>Nom</span>
              <input
                id="branch-name"
                v-model="branchForm.name"
                class="mp-input"
                placeholder="Sergeli"
                required
                :aria-invalid="!!branchFieldErrors.name"
                :aria-describedby="branchFieldErrors.name ? 'branch-name-error' : undefined"
              />
              <span v-if="branchFieldErrors.name" id="branch-name-error" class="mp-field-error">
                {{ branchFieldErrors.name }}
              </span>
            </label>
            <label class="field" for="branch-address">
              <span>Manzil</span>
              <input
                id="branch-address"
                v-model="branchForm.address"
                class="mp-input"
                placeholder="Sergeli 1-mavze 4"
                required
                :aria-invalid="!!branchFieldErrors.address"
                :aria-describedby="branchFieldErrors.address ? 'branch-address-error' : undefined"
              />
              <span
                v-if="branchFieldErrors.address"
                id="branch-address-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.address }}
              </span>
            </label>
          </div>
          <div class="grid gap-3 md:grid-cols-3">
            <label class="field" for="branch-phone">
              <span>Telefon</span>
              <input
                id="branch-phone"
                v-model="branchForm.phone"
                class="mp-input"
                required
                :aria-invalid="!!branchFieldErrors.phone"
                :aria-describedby="branchFieldErrors.phone ? 'branch-phone-error' : undefined"
              />
              <span v-if="branchFieldErrors.phone" id="branch-phone-error" class="mp-field-error">
                {{ branchFieldErrors.phone }}
              </span>
            </label>
            <label class="field" for="branch-latitude">
              <span>Lat</span>
              <input
                id="branch-latitude"
                v-model="branchForm.latitude"
                class="mp-input"
                inputmode="decimal"
                :aria-invalid="!!branchFieldErrors.latitude"
                :aria-describedby="branchFieldErrors.latitude ? 'branch-latitude-error' : undefined"
              />
              <span
                v-if="branchFieldErrors.latitude"
                id="branch-latitude-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.latitude }}
              </span>
            </label>
            <label class="field" for="branch-longitude">
              <span>Lng</span>
              <input
                id="branch-longitude"
                v-model="branchForm.longitude"
                class="mp-input"
                inputmode="decimal"
                :aria-invalid="!!branchFieldErrors.longitude"
                :aria-describedby="
                  branchFieldErrors.longitude ? 'branch-longitude-error' : undefined
                "
              />
              <span
                v-if="branchFieldErrors.longitude"
                id="branch-longitude-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.longitude }}
              </span>
            </label>
          </div>
          <fieldset>
            <legend class="mb-2 text-sm font-extrabold text-ink">Ish vaqti</legend>
            <div class="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
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
          <div class="flex flex-wrap items-center justify-end gap-3">
            <p v-if="branchError" class="text-sm font-bold text-danger">Filial yaratilmadi.</p>
            <button type="submit" class="mp-button mp-button-primary" :disabled="creatingBranch">
              {{ creatingBranch ? 'Yaratilmoqda' : 'Yaratish' }}
            </button>
          </div>
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

      <section v-else class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Filial</th>
                <th>Manzil</th>
                <th>Telefon</th>
                <th>Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="branch in workshop.managedBranches" :key="branch.id">
                <td class="nm">{{ branch.name }}</td>
                <td>{{ branch.address }}</td>
                <td class="num">{{ branch.phone }}</td>
                <td>
                  <span :class="branchPillClass(branch.status)">
                    <span class="pd"></span>{{ branchStatusUz[branch.status] }}
                  </span>
                </td>
                <td class="right">
                  <RouterLink
                    :to="rolePath(`/workshop/branches/${branch.id}`)"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  >
                    Ochish
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>
