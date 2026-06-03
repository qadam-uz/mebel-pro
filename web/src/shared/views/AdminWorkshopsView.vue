<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useAdminStore } from '@/shared/stores/admin'

const admin = useAdminStore()
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
      <form class="mt-5 grid gap-3 md:grid-cols-3" @submit.prevent="createWorkshop">
        <input
          v-model="form.name"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Workshop name"
          required
        />
        <input
          v-model="form.code"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Code"
        />
        <input
          v-model="form.phone"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Workshop phone"
          required
        />
        <input
          v-model="form.address"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Workshop address"
        />
        <input
          v-model="form.branchName"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="First branch"
          required
        />
        <input
          v-model="form.branchAddress"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Branch address"
          required
        />
        <input
          v-model="form.branchPhone"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Branch phone"
          required
        />
        <input
          v-model="form.latitude"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Latitude"
          required
        />
        <input
          v-model="form.longitude"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Longitude"
          required
        />
        <input
          v-model="form.ownerName"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Owner name"
          required
        />
        <input
          v-model="form.ownerLogin"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Owner login"
          required
        />
        <input
          v-model="form.ownerPhone"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Owner phone"
          required
        />
        <input
          v-model="form.tempPassword"
          class="min-h-11 rounded-md border border-hairline-strong px-3"
          placeholder="Temp password"
        />
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
          :to="`/admin/workshops/${workshop.id}`"
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
