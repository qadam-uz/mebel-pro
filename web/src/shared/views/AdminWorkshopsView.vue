<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  tempPassword,
  uzPhone,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import {
  adminDate,
  dropdownOption,
  workshopStatusLabel,
  workshopStatusTone,
} from '@/shared/app/adminUi'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import AdminModalCloseIcon from '@/shared/components/AdminModalCloseIcon.vue'
import AdminSecretModal from '@/shared/components/AdminSecretModal.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore, type WorkshopSummary } from '@/shared/stores/admin'

type ProvisionField =
  | 'name'
  | 'branchName'
  | 'branchAddress'
  | 'branchPhone'
  | 'ownerLogin'
  | 'tempPassword'

const admin = useAdminStore()
const rolePath = useRolePath()
const toast = useToast()
const creating = ref(false)
const modalOpen = ref(false)
const secretOpen = ref(false)
const provisionPanel = ref<HTMLElement | null>(null)
const provisionTrap = useFocusTrap(provisionPanel, modalOpen, () => (modalOpen.value = false))

// AB-19: block / unblock from the list row, not only the detail view.
const blockTarget = ref<WorkshopSummary | null>(null)
const unblockTarget = ref<WorkshopSummary | null>(null)
const acting = ref(false)
const blockReason = ref('')
const blockFieldErrors = reactive<FieldErrors<'blockReason'>>({})

function askBlock(workshop: WorkshopSummary) {
  blockTarget.value = workshop
  blockReason.value = ''
  clearFieldErrors(blockFieldErrors)
}

async function confirmBlock() {
  clearFieldErrors(blockFieldErrors)
  if (!blockTarget.value) return
  if (!blockReason.value.trim()) {
    blockFieldErrors.blockReason = "Bu maydonni to'ldiring."
    return
  }
  acting.value = true
  try {
    await admin.blockWorkshop(blockTarget.value.id, blockReason.value)
    toast.success('Ustaxona bloklandi')
    blockTarget.value = null
  } catch (error) {
    Object.assign(
      blockFieldErrors,
      fieldErrorsFromApi<'blockReason'>(error, { reason_required: 'blockReason' }),
    )
    toast.danger("Ustaxonani bloklab bo'lmadi")
  } finally {
    acting.value = false
  }
}

async function confirmUnblock() {
  if (!unblockTarget.value) return
  acting.value = true
  try {
    await admin.unblockWorkshop(unblockTarget.value.id)
    toast.success('Ustaxona blokdan chiqarildi')
    unblockTarget.value = null
  } catch {
    toast.danger("Ustaxonani blokdan chiqarib bo'lmadi")
  } finally {
    acting.value = false
  }
}

const secretRows = computed(() => {
  const provision = admin.lastProvision
  if (!provision) return []
  return [
    { label: 'Rahbar login', value: provision.owner.login },
    { label: 'Vaqtinchalik parol', value: provision.temp_password },
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
  branchName: '',
  branchAddress: '',
  branchPhone: '',
  ownerLogin: '',
  tempPassword: '',
})
const provisionFieldErrors = reactive<FieldErrors<ProvisionField>>({})
const provisionFieldIds: Record<ProvisionField, string> = {
  name: 'w-name',
  branchName: 'b-name',
  branchAddress: 'b-address',
  branchPhone: 'b-phone',
  ownerLogin: 'o-login',
  tempPassword: 'o-pass',
}
const provisionFieldOrder: ProvisionField[] = [
  'name',
  'branchName',
  'branchAddress',
  'branchPhone',
  'ownerLogin',
  'tempPassword',
]
const provisionApiFieldMap: Partial<Record<string, ProvisionField>> = {
  workshop_name_required: 'name',
  invalid_phone: 'branchPhone',
  branch_name_required: 'branchName',
  branch_address_required: 'branchAddress',
  owner_login_required: 'ownerLogin',
  weak_password: 'tempPassword',
}
const provisionApiLocMap: Partial<Record<string, ProvisionField>> = {
  'body.workshop.name': 'name',
  'body.branch.name': 'branchName',
  'body.branch.address': 'branchAddress',
  'body.branch.phone': 'branchPhone',
  'body.owner.login': 'ownerLogin',
  'body.temp_password': 'tempPassword',
}
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
    return [workshop.name, workshop.owner_login].join(' ').toLowerCase().includes(needle)
  })
})

function resetForm() {
  form.name = ''
  form.branchName = ''
  form.branchAddress = ''
  form.branchPhone = ''
  form.ownerLogin = ''
  form.tempPassword = ''
  clearFieldErrors(provisionFieldErrors)
  createError.value = null
}

function validateProvisionForm() {
  clearFieldErrors(provisionFieldErrors)
  const set = (field: ProvisionField, error: string | null) => {
    if (error) provisionFieldErrors[field] = error
  }
  set('name', requiredText(form.name))
  set('branchName', requiredText(form.branchName))
  set('branchAddress', requiredText(form.branchAddress))
  set('branchPhone', requiredText(form.branchPhone) ?? uzPhone(form.branchPhone))
  set('ownerLogin', requiredText(form.ownerLogin))
  set('tempPassword', tempPassword(form.tempPassword))
  const hasErrors = provisionFieldOrder.some((field) => Boolean(provisionFieldErrors[field]))
  if (hasErrors) {
    focusFirstFieldError(provisionFieldErrors, provisionFieldOrder, provisionFieldIds)
  }
  return !hasErrors
}

async function createWorkshop() {
  createError.value = null
  if (!validateProvisionForm()) return
  creating.value = true
  try {
    await admin.provision({
      workshop: {
        name: form.name,
      },
      branch: {
        name: form.branchName,
        address: form.branchAddress,
        phone: form.branchPhone,
      },
      owner: {
        login: form.ownerLogin,
      },
      temp_password: form.tempPassword || undefined,
    })
    resetForm()
    modalOpen.value = false
    secretOpen.value = true
    toast.success("Ustaxona qo'shildi")
    await admin.loadOverview()
  } catch (error) {
    const fields = fieldErrorsFromApi<ProvisionField>(
      error,
      provisionApiFieldMap,
      provisionApiLocMap,
    )
    if (Object.keys(fields).length > 0) {
      Object.assign(provisionFieldErrors, fields)
      focusFirstFieldError(provisionFieldErrors, provisionFieldOrder, provisionFieldIds)
    } else {
      createError.value = 'workshop_create_failed'
      toast.danger("Ustaxona qo'shilmadi")
    }
  } finally {
    creating.value = false
  }
}

watch(
  () => form.name,
  (name) => {
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
      </div>
      <button type="button" class="admin-primary-action" @click="modalOpen = true">
        + Yangi ustaxona
      </button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span>Qidirish</span>
        <input v-model="search" placeholder="Ustaxona nomi yoki rahbari" />
      </label>
      <FormSelect
        v-model="statusFilter"
        class="admin-filter-select"
        label="Holat"
        :options="statusOptions"
      />
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
      <p>Filtrni o'zgartiring yoki yangi ustaxona yarating.</p>
    </section>

    <section v-else class="admin-card">
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Ustaxona</th>
              <th>Rahbar</th>
              <th>Filiallar</th>
              <th>Yaratildi</th>
              <th>Holat</th>
              <th><span class="sr-only">Amallar</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="workshop in filtered" :key="workshop.id">
              <td class="nm">
                {{ workshop.name }}
              </td>
              <td class="admin-mono text-ink-muted">{{ workshop.owner_login }}</td>
              <td class="admin-mono text-ink-muted">{{ workshop.branch_count }}</td>
              <td class="admin-mono text-ink-muted">{{ adminDate(workshop.created_at) }}</td>
              <td>
                <span class="admin-pill" :class="workshopStatusTone(workshop.status)">
                  {{ workshopStatusLabel(workshop.status) }}
                </span>
              </td>
              <td class="admin-right">
                <div class="flex flex-wrap justify-end gap-2">
                  <RouterLink
                    :to="rolePath(`/admin/workshops/${workshop.id}`)"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :aria-label="`${workshop.name} tafsilotlarini ochish`"
                  >
                    Tafsilotlar
                  </RouterLink>
                  <button
                    v-if="workshop.status === 'active'"
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
                    :aria-label="`${workshop.name} ustaxonasini bloklash`"
                    @click="askBlock(workshop)"
                  >
                    Bloklash
                  </button>
                  <button
                    v-else
                    type="button"
                    class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                    :aria-label="`${workshop.name} ustaxonasini blokdan chiqarish`"
                    @click="unblockTarget = workshop"
                  >
                    Blokdan chiqarish
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
        ref="provisionPanel"
        class="admin-modal wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-workshop-title"
        tabindex="-1"
        @keydown="provisionTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="new-workshop-title">Yangi ustaxona va rahbari</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="modalOpen = false"
          >
            <AdminModalCloseIcon />
          </button>
        </div>
        <form novalidate @submit.prevent="createWorkshop">
          <div class="admin-modal-b">
            <div class="admin-form-grid three">
              <label class="admin-field admin-full" for="w-name">
                <span>Ustaxona nomi</span>
                <input
                  id="w-name"
                  v-model="form.name"
                  autocomplete="organization"
                  required
                  :aria-invalid="!!provisionFieldErrors.name"
                  aria-describedby="w-name-error"
                />
                <span
                  v-if="provisionFieldErrors.name"
                  id="w-name-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ provisionFieldErrors.name }}
                </span>
              </label>
              <label class="admin-field" for="b-name">
                <span>Birinchi filial</span>
                <input
                  id="b-name"
                  v-model="form.branchName"
                  required
                  :aria-invalid="!!provisionFieldErrors.branchName"
                  aria-describedby="b-name-error"
                />
                <span
                  v-if="provisionFieldErrors.branchName"
                  id="b-name-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ provisionFieldErrors.branchName }}
                </span>
              </label>
              <label class="admin-field" for="b-phone">
                <span>Filial telefoni</span>
                <PhoneInput
                  id="b-phone"
                  v-model="form.branchPhone"
                  required
                  :aria-invalid="!!provisionFieldErrors.branchPhone"
                  aria-describedby="b-phone-error"
                />
                <span
                  v-if="provisionFieldErrors.branchPhone"
                  id="b-phone-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ provisionFieldErrors.branchPhone }}
                </span>
              </label>
              <label class="admin-field" for="b-address">
                <span>Filial manzili</span>
                <input
                  id="b-address"
                  v-model="form.branchAddress"
                  required
                  :aria-invalid="!!provisionFieldErrors.branchAddress"
                  aria-describedby="b-address-error"
                />
                <span
                  v-if="provisionFieldErrors.branchAddress"
                  id="b-address-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ provisionFieldErrors.branchAddress }}
                </span>
              </label>
              <label class="admin-field" for="o-login">
                <span>Rahbar login</span>
                <input
                  id="o-login"
                  v-model="form.ownerLogin"
                  autocomplete="username"
                  required
                  :aria-invalid="!!provisionFieldErrors.ownerLogin"
                  aria-describedby="o-login-error"
                />
                <span
                  v-if="provisionFieldErrors.ownerLogin"
                  id="o-login-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ provisionFieldErrors.ownerLogin }}
                </span>
              </label>
              <label class="admin-field admin-full" for="o-pass">
                <span>Vaqtinchalik parol</span>
                <input
                  id="o-pass"
                  v-model="form.tempPassword"
                  autocomplete="new-password"
                  placeholder="Bo'sh qoldirilsa avtomatik yaratiladi"
                  :aria-invalid="!!provisionFieldErrors.tempPassword"
                  aria-describedby="o-pass-error"
                />
                <span
                  v-if="provisionFieldErrors.tempPassword"
                  id="o-pass-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ provisionFieldErrors.tempPassword }}
                </span>
              </label>
            </div>
            <p
              v-if="createError"
              class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Ustaxona qo'shilmadi. Maydonlarni tekshiring.
            </p>
          </div>
          <div class="admin-modal-f">
            <button type="button" class="mp-button mp-button-outline" @click="modalOpen = false">
              Bekor
            </button>
            <button type="submit" class="mp-button mp-button-primary" :disabled="creating">
              {{ creating ? "Qo'shilmoqda" : "Qo'shish" }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <ConfirmDialog
      :open="blockTarget !== null"
      title="Ustaxonani bloklash"
      :message="`${blockTarget?.name ?? ''} xodimlarining sessiyalari darhol bekor qilinadi, ochiq buyurtmalar muzlaydi. Blokdan chiqarilganda sessiyalar tiklanmaydi.`"
      confirm-label="Bloklash"
      busy-label="Bloklanmoqda"
      cancel-label="Bekor qilish"
      danger
      :busy="acting"
      :confirm-disabled="!blockReason.trim()"
      @confirm="confirmBlock"
      @cancel="blockTarget = null"
    >
      <label class="admin-field" for="workshop-block-reason">
        <span>Sabab</span>
        <textarea
          id="workshop-block-reason"
          v-model="blockReason"
          required
          :aria-invalid="!!blockFieldErrors.blockReason"
          aria-describedby="workshop-block-reason-error"
        ></textarea>
        <span
          v-if="blockFieldErrors.blockReason"
          id="workshop-block-reason-error"
          class="admin-field-error"
          role="alert"
        >
          {{ blockFieldErrors.blockReason }}
        </span>
      </label>
    </ConfirmDialog>

    <ConfirmDialog
      :open="unblockTarget !== null"
      title="Blokdan chiqarish"
      :message="`${unblockTarget?.name ?? ''} blokdan chiqariladi. Foydalanuvchilar qaytadan kirishi kerak (sessiyalar avtomatik tiklanmaydi).`"
      confirm-label="Blokdan chiqarish"
      busy-label="Bajarilmoqda"
      cancel-label="Bekor qilish"
      :busy="acting"
      @confirm="confirmUnblock"
      @cancel="unblockTarget = null"
    />

    <AdminSecretModal
      :open="secretOpen && !!admin.lastProvision"
      title="Ustaxona qo'shildi — bir martalik maxfiy ma'lumot"
      intro="Rahbar login va vaqtinchalik parolni ustaxona rahbariga yetkazing."
      :rows="secretRows"
      @close="closeSecret"
    />
  </section>
</template>
