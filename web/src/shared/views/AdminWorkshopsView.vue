<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import {
  adminDate,
  dropdownOption,
  workshopStatusLabel,
  workshopStatusTone,
} from '@/shared/app/adminUi'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import AdminSecretModal from '@/shared/components/AdminSecretModal.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore } from '@/shared/stores/admin'

const admin = useAdminStore()
const rolePath = useRolePath()
const toast = useToast()
const creating = ref(false)
const modalOpen = ref(false)
const secretOpen = ref(false)
const provisionPanel = ref<HTMLElement | null>(null)
const provisionTrap = useFocusTrap(provisionPanel, modalOpen, () => (modalOpen.value = false))

const secretRows = computed(() => {
  const provision = admin.lastProvision
  if (!provision) return []
  return [
    { label: 'Workshop code', value: provision.workshop.code },
    { label: 'Owner login', value: provision.owner.login },
    { label: 'Temp password', value: provision.temp_password },
  ]
})

function closeSecret() {
  secretOpen.value = false
  admin.clearSecrets()
}

onBeforeUnmount(() => admin.clearSecrets())
const createError = ref<string | null>(null)
const search = ref('')
const statusFilter = ref('all')
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

const statusOptions = [
  dropdownOption('all', 'Hammasi', 'barcha holatlar'),
  dropdownOption('active', 'Faol', 'kirish mumkin'),
  dropdownOption('blocked', 'Bloklangan', 'sessiyalar yopilgan'),
]
const filtered = computed(() => {
  const needle = search.value.trim().toLowerCase()
  return admin.workshops.filter((workshop) => {
    if (statusFilter.value !== 'all' && workshop.status !== statusFilter.value) return false
    if (!needle) return true
    return [workshop.name, workshop.code, workshop.phone, workshop.address ?? '']
      .join(' ')
      .toLowerCase()
      .includes(needle)
  })
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

function codeFromName(value: string) {
  return value
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 16)
}

function resetForm() {
  form.name = ''
  form.code = ''
  form.phone = '+998'
  form.address = ''
  form.branchName = ''
  form.branchAddress = ''
  form.branchPhone = '+998'
  form.latitude = '41.2995'
  form.longitude = '69.2401'
  form.ownerName = ''
  form.ownerLogin = ''
  form.ownerPhone = '+998'
  form.tempPassword = ''
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
    resetForm()
    modalOpen.value = false
    secretOpen.value = true
    toast.success('Ustaxona yaratildi')
    await admin.loadOverview()
  } catch {
    createError.value = 'workshop_create_failed'
    toast.danger('Ustaxona yaratilmadi')
  } finally {
    creating.value = false
  }
}

watch(
  () => form.name,
  (name) => {
    if (!form.code) form.code = codeFromName(name)
    if (!form.branchName) form.branchName = name ? 'Asosiy filial' : ''
  },
)

onMounted(async () => {
  await Promise.all([admin.loadWorkshops(), admin.loadOverview()])
})
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Ustaxonalar</h1>
        <p class="sub">Tenantlarni provisioning qilish, bloklash va holatini kuzatish.</p>
      </div>
      <button type="button" class="admin-primary-action" @click="modalOpen = true">
        Yangi ustaxona
      </button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span class="sr-only">Ustaxona nomi yoki kod</span>
        <input v-model="search" placeholder="Ustaxona nomi yoki kod" />
      </label>
      <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" />
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadWorkshops">
        Yangilash
      </button>
    </div>

    <section v-if="admin.loading" class="admin-card p-5" aria-live="polite">
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="admin.error"
      :code="admin.error"
      :trace-id="admin.traceId"
      title="Ustaxonalar yuklanmadi"
      @retry="admin.loadWorkshops"
    />

    <section v-else-if="filtered.length === 0" class="admin-empty">
      <h3>Ustaxona topilmadi</h3>
      <p>Filtrni o'zgartiring yoki yangi ustaxona provisioning qiling.</p>
    </section>

    <section v-else class="admin-card">
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Ustaxona</th>
              <th>Egasi</th>
              <th>Telefon</th>
              <th>Yaratildi</th>
              <th>Holat</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="workshop in filtered" :key="workshop.id">
              <td class="nm">
                {{ workshop.name }}
                <small>{{ workshop.code }} . {{ workshop.address ?? 'manzil kiritilmagan' }}</small>
              </td>
              <td class="admin-mono text-ink-muted">{{ workshop.owner_user_id.slice(0, 8) }}</td>
              <td class="admin-mono text-ink-muted">{{ workshop.phone }}</td>
              <td class="admin-mono text-ink-muted">{{ adminDate(workshop.created_at) }}</td>
              <td>
                <span class="admin-pill" :class="workshopStatusTone(workshop.status)">
                  {{ workshopStatusLabel(workshop.status) }}
                </span>
              </td>
              <td class="admin-right">
                <RouterLink
                  :to="rolePath(`/admin/workshops/${workshop.id}`)"
                  class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                >
                  Tafsilotlar
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <template v-if="modalOpen">
      <div class="admin-modal-scrim" aria-hidden="true" @click="modalOpen = false"></div>
      <section
        ref="provisionPanel"
        class="admin-modal wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-workshop-title"
        tabindex="-1"
        @keydown="provisionTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="new-workshop-title">Yangi ustaxona + egasi . atomik yaratish</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="modalOpen = false"
          >
            x
          </button>
        </div>
        <form @submit.prevent="createWorkshop">
          <div class="admin-modal-b">
            <div class="admin-form-grid three">
              <label class="admin-field admin-full" for="w-name">
                <span>Ustaxona nomi</span>
                <input id="w-name" v-model="form.name" autocomplete="organization" required />
              </label>
              <label class="admin-field" for="w-code">
                <span>Workshop code</span>
                <input id="w-code" v-model="form.code" autocomplete="off" required />
              </label>
              <label class="admin-field" for="w-phone">
                <span>Telefon</span>
                <input
                  id="w-phone"
                  v-model="form.phone"
                  autocomplete="tel"
                  inputmode="tel"
                  required
                />
              </label>
              <label class="admin-field" for="w-address">
                <span>Manzil</span>
                <input id="w-address" v-model="form.address" autocomplete="street-address" />
              </label>
              <label class="admin-field" for="b-name">
                <span>Birinchi filial</span>
                <input id="b-name" v-model="form.branchName" required />
              </label>
              <label class="admin-field" for="b-phone">
                <span>Filial telefoni</span>
                <input
                  id="b-phone"
                  v-model="form.branchPhone"
                  autocomplete="tel"
                  inputmode="tel"
                  required
                />
              </label>
              <label class="admin-field" for="b-address">
                <span>Filial manzili</span>
                <input id="b-address" v-model="form.branchAddress" required />
              </label>
              <label class="admin-field" for="b-lat">
                <span>Latitude</span>
                <input id="b-lat" v-model="form.latitude" inputmode="decimal" required />
              </label>
              <label class="admin-field" for="b-lon">
                <span>Longitude</span>
                <input id="b-lon" v-model="form.longitude" inputmode="decimal" required />
              </label>
              <label class="admin-field" for="o-name">
                <span>Owner ism</span>
                <input id="o-name" v-model="form.ownerName" autocomplete="name" required />
              </label>
              <label class="admin-field" for="o-phone">
                <span>Owner telefon</span>
                <input
                  id="o-phone"
                  v-model="form.ownerPhone"
                  autocomplete="tel"
                  inputmode="tel"
                  required
                />
              </label>
              <label class="admin-field" for="o-login">
                <span>Owner login</span>
                <input id="o-login" v-model="form.ownerLogin" autocomplete="username" required />
              </label>
              <label class="admin-field admin-full" for="o-pass">
                <span>Temp password</span>
                <input
                  id="o-pass"
                  v-model="form.tempPassword"
                  autocomplete="new-password"
                  placeholder="Bo'sh qoldirilsa avtomatik yaratiladi"
                />
              </label>
            </div>
            <p
              v-if="createError"
              class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Ustaxona yaratilmadi. Maydonlarni tekshiring.
            </p>
          </div>
          <div class="admin-modal-f">
            <button type="button" class="mp-button mp-button-outline" @click="modalOpen = false">
              Bekor
            </button>
            <button type="submit" class="mp-button mp-button-primary" :disabled="creating">
              {{ creating ? 'Yaratilmoqda' : 'Yaratish' }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <AdminSecretModal
      :open="secretOpen && !!admin.lastProvision"
      title="Ustaxona yaratildi — bir martalik maxfiy ma'lumot"
      intro="Workshop code va owner login bilan birga vaqtinchalik parolni egasiga yetkazing."
      :rows="secretRows"
      @close="closeSecret"
    />
  </section>
</template>
