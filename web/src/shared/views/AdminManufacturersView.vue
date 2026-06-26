<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import { dropdownOption, materialStatusLabel, materialStatusTone } from '@/shared/app/adminUi'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import AdminModalCloseIcon from '@/shared/components/AdminModalCloseIcon.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore, type Manufacturer, type MaterialStatus } from '@/shared/stores/admin'

const admin = useAdminStore()
const toast = useToast()
const modalOpen = ref(false)
const statusTarget = ref<{ row: Manufacturer; status: MaterialStatus } | null>(null)
const formPanel = ref<HTMLElement | null>(null)
const formTrap = useFocusTrap(formPanel, modalOpen, () => (modalOpen.value = false))
const saving = ref(false)
const actionId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const saveError = ref<string | null>(null)
const search = ref('')
const statusFilter = ref('all')
const form = reactive({
  name: '',
  country: '',
  note: '',
})
type ManufacturerField = 'name'
const fieldErrors = reactive<FieldErrors<ManufacturerField>>({})
const fieldIds: Record<ManufacturerField, string> = { name: 'mfr-name' }
const fieldOrder: ManufacturerField[] = ['name']

const statusOptions = [
  dropdownOption('all', 'Hammasi', 'barcha holatlar'),
  dropdownOption('active', 'Faol', "yangi material uchun ko'rinadi"),
  dropdownOption('inactive', 'Faol emas', 'yangi tanlovdan yashirilgan'),
]
const countryFilter = ref('all')
const countryOptions = computed(() => [
  dropdownOption('all', 'Davlat', 'barcha davlatlar'),
  ...Array.from(
    new Set(admin.manufacturers.map((row) => row.country).filter((c): c is string => !!c)),
  ).map((country) => dropdownOption(country, country, '')),
])
const filtered = computed(() => {
  const needle = search.value.trim().toLowerCase()
  return admin.manufacturers.filter((manufacturer) => {
    if (statusFilter.value !== 'all' && manufacturer.status !== statusFilter.value) return false
    if (countryFilter.value !== 'all' && manufacturer.country !== countryFilter.value) return false
    if (!needle) return true
    return [manufacturer.name, manufacturer.country ?? '', manufacturer.note ?? '']
      .join(' ')
      .toLowerCase()
      .includes(needle)
  })
})

function materialCount(id: string) {
  return admin.materials.filter((material) => material.manufacturer_id === id).length
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.country = ''
  form.note = ''
  saveError.value = null
  clearFieldErrors(fieldErrors)
  modalOpen.value = true
}

function openEdit(row: Manufacturer) {
  editingId.value = row.id
  form.name = row.name
  form.country = row.country ?? ''
  form.note = row.note ?? ''
  saveError.value = null
  clearFieldErrors(fieldErrors)
  modalOpen.value = true
}

async function save() {
  clearFieldErrors(fieldErrors)
  fieldErrors.name = requiredText(form.name) ?? undefined
  if (fieldErrors.name) {
    focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
    return
  }
  saving.value = true
  saveError.value = null
  try {
    const payload = {
      name: form.name,
      country: form.country || null,
      note: form.note || null,
    }
    if (editingId.value) await admin.updateManufacturer(editingId.value, payload)
    else await admin.createManufacturer(payload)
    modalOpen.value = false
    toast.success(
      editingId.value ? 'Ishlab chiqaruvchi yangilandi' : "Ishlab chiqaruvchi qo'shildi",
    )
  } catch (error) {
    Object.assign(
      fieldErrors,
      fieldErrorsFromApi<ManufacturerField>(error, {
        manufacturer_name_required: 'name',
        manufacturer_name_exists: 'name',
      }),
    )
    if (fieldErrors.name) {
      focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
    } else {
      saveError.value = 'manufacturer_save_failed'
      toast.danger('Ishlab chiqaruvchi saqlanmadi')
    }
  } finally {
    saving.value = false
  }
}

function askStatus(row: Manufacturer, status: MaterialStatus) {
  statusTarget.value = { row, status }
}

async function confirmStatus() {
  const target = statusTarget.value
  if (!target) return
  statusTarget.value = null
  actionId.value = target.row.id
  try {
    await admin.setManufacturerStatus(target.row.id, target.status)
    toast.success(target.status === 'active' ? 'Faollashtirildi' : 'Faol emas qilindi')
  } catch {
    toast.danger('Amal bajarilmadi')
  } finally {
    actionId.value = null
  }
}

onMounted(async () => {
  await Promise.all([admin.loadManufacturers(), admin.loadMaterials()])
})
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Ishlab chiqaruvchilar</h1>
      </div>
      <button type="button" class="admin-primary-action" @click="openCreate">
        + Yangi ishlab chiqaruvchi
      </button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span>Qidiruv</span>
        <input v-model="search" placeholder="Ishlab chiqaruvchi nomi" />
      </label>
      <FormSelect
        v-model="statusFilter"
        class="admin-filter-select"
        label="Holat"
        :options="statusOptions"
      />
      <FormSelect
        v-model="countryFilter"
        class="admin-filter-select"
        label="Davlat"
        :options="countryOptions"
      />
    </div>

    <section v-if="admin.manufacturersLoading" class="admin-card p-5" aria-live="polite">
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="admin.manufacturersError"
      :code="admin.manufacturersError"
      :trace-id="admin.manufacturersTraceId"
      title="Ishlab chiqaruvchilar yuklanmadi"
      @retry="admin.loadManufacturers()"
    />

    <section v-else-if="filtered.length === 0" class="admin-empty">
      <h3>Ishlab chiqaruvchi yo'q</h3>
      <p>Material yaratishdan oldin ishlab chiqaruvchi qo'shing.</p>
    </section>

    <section v-else class="admin-card">
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Ishlab chiqaruvchi</th>
              <th>Davlat</th>
              <th class="admin-right">Materiallar</th>
              <th>Holat</th>
              <th>Izoh</th>
              <th><span class="sr-only">Amallar</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="manufacturer in filtered" :key="manufacturer.id">
              <td class="nm">
                {{ manufacturer.name }}
                <small>{{ manufacturer.id.slice(0, 8) }}</small>
              </td>
              <td>{{ manufacturer.country ?? '-' }}</td>
              <td class="admin-right admin-mono">{{ materialCount(manufacturer.id) }}</td>
              <td>
                <span class="admin-pill" :class="materialStatusTone(manufacturer.status)">
                  {{ materialStatusLabel(manufacturer.status) }}
                </span>
              </td>
              <td class="max-w-[280px] truncate text-ink-muted">{{ manufacturer.note ?? '-' }}</td>
              <td class="admin-right">
                <div class="flex justify-end gap-2">
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :aria-label="`${manufacturer.name} ishlab chiqaruvchisini tahrirlash`"
                    @click="openEdit(manufacturer)"
                  >
                    Tahrirlash
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :disabled="actionId === manufacturer.id"
                    :aria-label="
                      manufacturer.status === 'active'
                        ? `${manufacturer.name} ishlab chiqaruvchisini faol emas qilish`
                        : `${manufacturer.name} ishlab chiqaruvchisini faollashtirish`
                    "
                    @click="
                      askStatus(
                        manufacturer,
                        manufacturer.status === 'active' ? 'inactive' : 'active',
                      )
                    "
                  >
                    {{ manufacturer.status === 'active' ? 'Faol emas qilish' : 'Faollashtirish' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <template v-if="modalOpen">
      <div class="admin-modal-scrim" aria-hidden="true" @click="modalOpen = false"></div>
      <section
        ref="formPanel"
        class="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="manufacturer-title"
        tabindex="-1"
        @keydown="formTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="manufacturer-title">
            {{ editingId ? 'Ishlab chiqaruvchini tahrirlash' : 'Yangi ishlab chiqaruvchi' }}
          </h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="modalOpen = false"
          >
            <AdminModalCloseIcon />
          </button>
        </div>
        <form novalidate @submit.prevent="save">
          <div class="admin-modal-b">
            <div class="admin-form-grid">
              <label class="admin-field admin-full" for="mfr-name">
                <span>Nomi</span>
                <input
                  id="mfr-name"
                  v-model="form.name"
                  placeholder="Egger"
                  required
                  :aria-invalid="!!fieldErrors.name"
                  aria-describedby="mfr-name-error"
                />
                <span
                  v-if="fieldErrors.name"
                  id="mfr-name-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ fieldErrors.name }}
                </span>
              </label>
              <label class="admin-field" for="mfr-country">
                <span>Davlat</span>
                <input id="mfr-country" v-model="form.country" placeholder="Avstriya" />
              </label>
              <label class="admin-field admin-full" for="mfr-note">
                <span>Izoh</span>
                <textarea
                  id="mfr-note"
                  v-model="form.note"
                  placeholder="LDSP . asosiy brand"
                ></textarea>
              </label>
            </div>
            <p
              v-if="saveError"
              class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Ishlab chiqaruvchi saqlanmadi.
            </p>
          </div>
          <div class="admin-modal-f">
            <button type="button" class="mp-button mp-button-outline" @click="modalOpen = false">
              Bekor
            </button>
            <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
              {{ saving ? 'Saqlanmoqda' : 'Saqlash' }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <ConfirmDialog
      :open="statusTarget !== null"
      :title="statusTarget?.status === 'inactive' ? 'Faol emas qilish' : 'Faollashtirish'"
      :message="
        statusTarget?.status === 'inactive'
          ? `${statusTarget?.row.name} faol emas qilinadi — uning materiallari yangi tanlovlardan yashiriladi; mavjud buyurtmalarga ta'sir qilmaydi.`
          : `${statusTarget?.row.name} faollashtiriladi va yangi material tanlovida ko'rinadi.`
      "
      confirm-label="Tasdiqlash"
      cancel-label="Bekor qilish"
      :danger="statusTarget?.status === 'inactive'"
      :busy="actionId === statusTarget?.row.id"
      @confirm="confirmStatus"
      @cancel="statusTarget = null"
    />
  </section>
</template>
