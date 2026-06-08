<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useFilesStore } from '@/shared/stores/files'
import { useWorkshopStore } from '@/shared/stores/workshop'
import { useRolePath } from '@/shared/app/paths'

const workshop = useWorkshopStore()
const rolePath = useRolePath()
const files = useFilesStore()
const savingSettings = ref(false)
const creatingBranch = ref(false)
const settingsError = ref<string | null>(null)
const branchError = ref<string | null>(null)

const settingsForm = reactive({
  name: '',
  phone: '',
  address: '',
  logoFileId: '',
})
const branchForm = reactive({
  name: '',
  address: '',
  phone: '+998',
  latitude: '41.2995',
  longitude: '69.2401',
})
const hours = reactive([
  { key: 'monday', label: 'Mon', open: true, from: '09:00', to: '18:00' },
  { key: 'tuesday', label: 'Tue', open: true, from: '09:00', to: '18:00' },
  { key: 'wednesday', label: 'Wed', open: true, from: '09:00', to: '18:00' },
  { key: 'thursday', label: 'Thu', open: true, from: '09:00', to: '18:00' },
  { key: 'friday', label: 'Fri', open: true, from: '09:00', to: '18:00' },
  { key: 'saturday', label: 'Sat', open: true, from: '10:00', to: '16:00' },
  { key: 'sunday', label: 'Sun', open: false, from: '10:00', to: '16:00' },
])

function syncSettingsForm() {
  if (!workshop.settings) return
  settingsForm.name = workshop.settings.name
  settingsForm.phone = workshop.settings.phone
  settingsForm.address = workshop.settings.address ?? ''
  settingsForm.logoFileId = workshop.settings.logo_file_id ?? ''
}

function workingHoursPayload() {
  return Object.fromEntries(
    hours.map((day) => [
      day.key,
      day.open ? { open: day.from, close: day.to } : { open: null, close: null },
    ]),
  )
}

async function saveSettings() {
  savingSettings.value = true
  settingsError.value = null
  try {
    await workshop.updateSettings({
      name: settingsForm.name,
      phone: settingsForm.phone,
      address: settingsForm.address || null,
      logo_file_id: settingsForm.logoFileId || null,
    })
    syncSettingsForm()
  } catch {
    settingsError.value = 'settings_save_failed'
  } finally {
    savingSettings.value = false
  }
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
  } catch {
    branchError.value = 'branch_create_failed'
  } finally {
    creatingBranch.value = false
  }
}

async function onLogoFile(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement) || !target.files?.[0]) return
  const uploaded = await files.upload(target.files[0])
  settingsForm.logoFileId = uploaded.id
  target.value = ''
}

onMounted(async () => {
  await Promise.all([workshop.loadSettings(), workshop.loadManagedBranches()])
  syncSettingsForm()
})
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="font-serif text-3xl font-semibold text-ink">Branches</h1>
      <p class="mt-2 text-base text-ink-soft">
        Set workshop profile details and manage the branch surfaces clients can see.
      </p>
    </div>

    <div class="grid gap-5 xl:grid-cols-[minmax(320px,0.72fr)_minmax(0,1.28fr)]">
      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Workshop profile</h2>
          <p class="mt-1 text-sm text-ink-soft">Name, contact details, and public logo.</p>
        </div>
        <form class="grid gap-3 p-5" @submit.prevent="saveSettings">
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="settings-name">Name</label>
            <input
              id="settings-name"
              v-model="settingsForm.name"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="settings-phone">Phone</label>
            <input
              id="settings-phone"
              v-model="settingsForm.phone"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="settings-address">
              Address
            </label>
            <input
              id="settings-address"
              v-model="settingsForm.address"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="settings-logo">Logo</label>
            <input
              id="settings-logo"
              type="file"
              accept="image/*"
              class="block min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 py-2 text-sm"
              @change="onLogoFile"
            />
            <p v-if="settingsForm.logoFileId" class="mt-1 font-mono text-[11px] text-ink-muted">
              logo {{ settingsForm.logoFileId.slice(0, 8) }}
            </p>
          </div>
          <button class="mp-button mp-button-primary" type="submit" :disabled="savingSettings">
            {{ savingSettings ? 'Saving' : 'Save profile' }}
          </button>
          <p
            v-if="settingsError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            Workshop settings could not be saved.
          </p>
        </form>
      </section>

      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Create branch</h2>
          <p class="mt-1 text-sm text-ink-soft">A pricing row is created with every new branch.</p>
        </div>
        <form class="grid gap-3 p-5 lg:grid-cols-4" @submit.prevent="createBranch">
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-name">Name</label>
            <input
              id="branch-name"
              v-model="branchForm.name"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-phone">Phone</label>
            <input
              id="branch-phone"
              v-model="branchForm.phone"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-latitude">
              Latitude
            </label>
            <input
              id="branch-latitude"
              v-model="branchForm.latitude"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              inputmode="decimal"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-longitude">
              Longitude
            </label>
            <input
              id="branch-longitude"
              v-model="branchForm.longitude"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              inputmode="decimal"
              required
            />
          </div>
          <div class="lg:col-span-4">
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-address">
              Address
            </label>
            <input
              id="branch-address"
              v-model="branchForm.address"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>

          <fieldset class="lg:col-span-4">
            <legend class="mb-2 text-sm font-bold text-ink">Working hours</legend>
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
                    class="min-h-10 rounded-md border border-hairline-strong px-2 text-sm"
                    type="time"
                    :disabled="!day.open"
                    :aria-label="`${day.label} opens`"
                  />
                  <input
                    v-model="day.to"
                    class="min-h-10 rounded-md border border-hairline-strong px-2 text-sm"
                    type="time"
                    :disabled="!day.open"
                    :aria-label="`${day.label} closes`"
                  />
                </div>
              </div>
            </div>
          </fieldset>

          <button
            class="mp-button mp-button-primary lg:col-span-4"
            type="submit"
            :disabled="creatingBranch"
          >
            {{ creatingBranch ? 'Creating' : 'Create branch' }}
          </button>
          <p
            v-if="branchError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger lg:col-span-4"
          >
            Branch could not be created.
          </p>
        </form>
      </section>
    </div>

    <section class="mp-surface overflow-hidden">
      <div class="border-b border-hairline px-5 py-4">
        <h2 class="font-serif text-xl font-semibold text-ink">Branch registry</h2>
      </div>
      <div
        v-if="workshop.setupLoading"
        class="px-5 py-6 text-sm font-bold text-ink-soft"
        aria-live="polite"
      >
        Loading branches
      </div>
      <div v-else-if="workshop.setupError" class="px-5 py-6 text-sm font-bold text-danger">
        Branches could not be loaded. trace {{ workshop.setupTraceId ?? 'unavailable' }}
      </div>
      <div
        v-else-if="workshop.managedBranches.length === 0"
        class="px-5 py-6 text-sm text-ink-soft"
      >
        No branches yet.
      </div>
      <div v-else class="divide-y divide-hairline">
        <RouterLink
          v-for="branch in workshop.managedBranches"
          :key="branch.id"
          :to="rolePath(`/workshop/branches/${branch.id}`)"
          class="grid gap-3 px-5 py-4 no-underline md:grid-cols-[1fr_auto]"
        >
          <span class="min-w-0">
            <span class="block truncate text-base font-extrabold text-ink">{{ branch.name }}</span>
            <span class="block truncate text-sm text-ink-soft">
              {{ branch.address }} · {{ branch.phone }}
            </span>
          </span>
          <span
            class="mp-chip"
            :class="{
              'bg-success-soft text-success': branch.status === 'active',
              'bg-warning-soft text-warning': branch.status === 'temporarily_closed',
              'bg-danger-soft text-danger': branch.status === 'inactive',
            }"
          >
            <span class="mp-dot" aria-hidden="true"></span>
            {{ branch.status }}
          </span>
        </RouterLink>
      </div>
    </section>
  </section>
</template>
