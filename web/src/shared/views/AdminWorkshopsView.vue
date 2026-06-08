<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { useAdminStore } from '@/shared/stores/admin'

const admin = useAdminStore()
const rolePath = useRolePath()
const creating = ref(false)
const createError = ref<string | null>(null)
const form = reactive({
  name: '',
  code: '',
  phone: '+998',
  address: '',
  branchName: '',
  branchAddress: '',
  branchPhone: '+998',
  latitude: '41.2995',
  longitude: '69.2401',
  ownerName: '',
  ownerLogin: '',
  ownerPhone: '+998',
  tempPassword: '',
})

function defaultWorkingHours() {
  return {
    monday: { open: '09:00', close: '18:00' },
    tuesday: { open: '09:00', close: '18:00' },
    wednesday: { open: '09:00', close: '18:00' },
    thursday: { open: '09:00', close: '18:00' },
    friday: { open: '09:00', close: '18:00' },
    saturday: { open: '10:00', close: '16:00' },
    sunday: { open: null, close: null },
  }
}

async function createWorkshop() {
  creating.value = true
  createError.value = null
  try {
    await admin.provision({
      workshop: {
        name: form.name,
        code: form.code || null,
        phone: form.phone,
        address: form.address || null,
      },
      branch: {
        name: form.branchName,
        address: form.branchAddress,
        phone: form.branchPhone,
        latitude: form.latitude,
        longitude: form.longitude,
        working_hours: defaultWorkingHours(),
      },
      owner: {
        full_name: form.ownerName,
        login: form.ownerLogin,
        phone: form.ownerPhone,
      },
      temp_password: form.tempPassword || undefined,
    })
    form.name = ''
    form.code = ''
    form.phone = '+998'
    form.address = ''
    form.branchName = ''
    form.branchAddress = ''
    form.branchPhone = '+998'
    form.ownerName = ''
    form.ownerLogin = ''
    form.ownerPhone = '+998'
    form.tempPassword = ''
  } catch {
    createError.value = 'workshop_create_failed'
  } finally {
    creating.value = false
  }
}

onMounted(admin.loadWorkshops)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Workshops</h1>
        <p class="mt-2 text-base text-ink-soft">Provision tenants and control access.</p>
      </div>
    </div>

    <section class="mp-surface p-5">
      <h2 class="font-serif text-xl font-semibold">Provision workshop</h2>
      <form class="mt-5 grid gap-4 md:grid-cols-3" @submit.prevent="createWorkshop">
        <label class="block text-sm font-bold text-ink" for="provision-workshop-name">
          Workshop name
          <input
            id="provision-workshop-name"
            v-model="form.name"
            class="mp-input mt-1"
            autocomplete="organization"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-workshop-code">
          Code
          <input
            id="provision-workshop-code"
            v-model="form.code"
            class="mp-input mt-1"
            autocomplete="off"
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-workshop-phone">
          Workshop phone
          <input
            id="provision-workshop-phone"
            v-model="form.phone"
            class="mp-input mt-1"
            autocomplete="tel"
            inputmode="tel"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-workshop-address">
          Workshop address
          <input
            id="provision-workshop-address"
            v-model="form.address"
            class="mp-input mt-1"
            autocomplete="street-address"
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-branch-name">
          First branch
          <input
            id="provision-branch-name"
            v-model="form.branchName"
            class="mp-input mt-1"
            autocomplete="organization-title"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-branch-address">
          Branch address
          <input
            id="provision-branch-address"
            v-model="form.branchAddress"
            class="mp-input mt-1"
            autocomplete="street-address"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-branch-phone">
          Branch phone
          <input
            id="provision-branch-phone"
            v-model="form.branchPhone"
            class="mp-input mt-1"
            autocomplete="tel"
            inputmode="tel"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-branch-latitude">
          Latitude
          <input
            id="provision-branch-latitude"
            v-model="form.latitude"
            class="mp-input mt-1"
            inputmode="decimal"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-branch-longitude">
          Longitude
          <input
            id="provision-branch-longitude"
            v-model="form.longitude"
            class="mp-input mt-1"
            inputmode="decimal"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-owner-name">
          Owner name
          <input
            id="provision-owner-name"
            v-model="form.ownerName"
            class="mp-input mt-1"
            autocomplete="name"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-owner-login">
          Owner login
          <input
            id="provision-owner-login"
            v-model="form.ownerLogin"
            class="mp-input mt-1"
            autocomplete="username"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="provision-owner-phone">
          Owner phone
          <input
            id="provision-owner-phone"
            v-model="form.ownerPhone"
            class="mp-input mt-1"
            autocomplete="tel"
            inputmode="tel"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink md:col-span-3" for="provision-temp-password">
          Temp password
          <input
            id="provision-temp-password"
            v-model="form.tempPassword"
            class="mp-input mt-1"
            autocomplete="new-password"
          />
        </label>
        <button
          class="mp-button mp-button-primary md:col-span-3"
          type="submit"
          :disabled="creating"
        >
          {{ creating ? 'Creating' : 'Create workshop' }}
        </button>
      </form>
      <div v-if="admin.lastProvision" class="mt-4 rounded-md bg-success-soft p-4 text-success">
        <div class="font-extrabold">Created {{ admin.lastProvision.workshop.code }}</div>
        <p class="mt-1 font-mono text-sm">
          owner {{ admin.lastProvision.owner.login }} · temp
          {{ admin.lastProvision.temp_password }}
        </p>
      </div>
      <p v-if="createError" class="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
        Workshop could not be created.
      </p>
    </section>

    <section class="mp-surface overflow-hidden">
      <div class="border-b border-hairline px-5 py-4">
        <h2 class="font-serif text-xl font-semibold">Workshop registry</h2>
      </div>
      <div v-if="admin.loading" class="px-5 py-6 text-sm font-bold text-ink-soft">
        Loading workshops
      </div>
      <div v-else-if="admin.error" class="px-5 py-6 text-sm font-bold text-danger">
        Workshop registry could not be loaded.
      </div>
      <div v-else-if="admin.workshops.length === 0" class="px-5 py-6 text-sm text-ink-soft">
        No workshops yet.
      </div>
      <div v-else class="divide-y divide-hairline">
        <RouterLink
          v-for="workshop in admin.workshops"
          :key="workshop.id"
          :to="rolePath(`/admin/workshops/${workshop.id}`)"
          class="grid gap-2 px-5 py-4 no-underline sm:grid-cols-[1fr_auto]"
        >
          <span>
            <span class="block font-bold text-ink">{{ workshop.name }}</span>
            <span class="block font-mono text-xs text-ink-muted">{{ workshop.code }}</span>
          </span>
          <span
            class="mp-chip"
            :class="
              workshop.status === 'active'
                ? 'bg-success-soft text-success'
                : 'bg-danger-soft text-danger'
            "
          >
            <span class="mp-dot" aria-hidden="true"></span>
            {{ workshop.status }}
          </span>
        </RouterLink>
      </div>
    </section>
  </section>
</template>
