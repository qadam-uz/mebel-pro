<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { apiErrorCode } from '@/shared/api/client'
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
  adminDateTime,
  platformUserStatusLabel,
  platformUserStatusTone,
} from '@/shared/app/adminUi'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import AdminModalCloseIcon from '@/shared/components/AdminModalCloseIcon.vue'
import AdminRefreshButton from '@/shared/components/AdminRefreshButton.vue'
import AdminSecretModal from '@/shared/components/AdminSecretModal.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore, type PlatformUser } from '@/shared/stores/admin'
import { useAuthStore } from '@/shared/stores/auth'

const admin = useAdminStore()
const auth = useAuthStore()
const toast = useToast()
const modalOpen = ref(false)
const blockModalOpen = ref(false)
const secretOpen = ref(false)
const resetTarget = ref<PlatformUser | null>(null)
const formPanel = ref<HTMLElement | null>(null)
const blockPanel = ref<HTMLElement | null>(null)
const formTrap = useFocusTrap(formPanel, modalOpen, () => (modalOpen.value = false))
const blockTrap = useFocusTrap(blockPanel, blockModalOpen, () => (blockModalOpen.value = false))
const saving = ref(false)
const actionId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const editingId = ref<string | null>(null)
const blockTarget = ref<PlatformUser | null>(null)
const blockReason = ref('')
const query = ref('')

const activeOperatorCount = computed(
  () => admin.platformUsers.filter((user) => user.status === 'active').length,
)

// AB-18: the server refuses to block the operator themselves or the last active
// operator; reflect both in the UI (disabled with a reason) instead of letting
// the click 400 into a generic failure.
function blockDisabledReason(user: PlatformUser): string | null {
  if (user.id === auth.me?.principal_id) return "O'zini bloklab bo'lmaydi"
  if (user.status === 'active' && activeOperatorCount.value <= 1)
    return "Oxirgi faol operatorni bloklab bo'lmaydi"
  return null
}

function isCurrentOperator(user: PlatformUser): boolean {
  return user.id === auth.me?.principal_id
}

const secretRows = computed(() => {
  const secret = admin.lastPlatformUserSecret
  if (!secret) return []
  return [
    { label: 'Operator', value: secret.user.login },
    { label: 'Vaqtinchalik parol', value: secret.temp_password },
  ]
})

function closeSecret() {
  secretOpen.value = false
  admin.clearSecrets()
}

onBeforeUnmount(() => admin.clearSecrets())
const form = reactive({
  fullName: '',
  login: '',
  phone: '+998',
  tempPassword: '',
})
type OperatorField = 'fullName' | 'phone' | 'login' | 'tempPassword'
const fieldErrors = reactive<FieldErrors<OperatorField>>({})
const fieldIds: Record<OperatorField, string> = {
  fullName: 'op-name',
  phone: 'op-phone',
  login: 'op-login',
  tempPassword: 'op-pass',
}
const fieldOrder: OperatorField[] = ['fullName', 'phone', 'login', 'tempPassword']
const blockFieldErrors = reactive<FieldErrors<'blockReason'>>({})

const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) return admin.platformUsers
  return admin.platformUsers.filter((user) =>
    [user.full_name, user.login, user.phone, user.status].join(' ').toLowerCase().includes(needle),
  )
})

function openCreate() {
  editingId.value = null
  form.fullName = ''
  form.login = ''
  form.phone = '+998'
  form.tempPassword = ''
  actionError.value = null
  clearFieldErrors(fieldErrors)
  modalOpen.value = true
}

function openEdit(user: PlatformUser) {
  editingId.value = user.id
  form.fullName = user.full_name
  form.login = user.login
  form.phone = user.phone
  form.tempPassword = ''
  actionError.value = null
  clearFieldErrors(fieldErrors)
  modalOpen.value = true
}

function validateUserForm() {
  clearFieldErrors(fieldErrors)
  const set = (field: OperatorField, error: string | null) => {
    if (error) fieldErrors[field] = error
  }
  set('fullName', requiredText(form.fullName))
  set('phone', requiredText(form.phone) ?? uzPhone(form.phone))
  if (!editingId.value) {
    set('login', requiredText(form.login))
    set('tempPassword', tempPassword(form.tempPassword))
  }
  const hasErrors = fieldOrder.some((field) => Boolean(fieldErrors[field]))
  if (hasErrors) focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
  return !hasErrors
}

async function saveUser() {
  if (!validateUserForm()) return
  saving.value = true
  actionError.value = null
  try {
    if (editingId.value) {
      await admin.updatePlatformUser(editingId.value, {
        full_name: form.fullName,
        phone: form.phone,
      })
      modalOpen.value = false
      toast.success('Operator yangilandi')
    } else {
      await admin.createPlatformUser({
        full_name: form.fullName,
        login: form.login,
        phone: form.phone,
        temp_password: form.tempPassword || null,
      })
      modalOpen.value = false
      secretOpen.value = true
      toast.success('Operator yaratildi')
    }
  } catch (error) {
    const fields = fieldErrorsFromApi<OperatorField>(error, {
      full_name_required: 'fullName',
      invalid_phone: 'phone',
      login_required: 'login',
      login_exists: 'login',
      weak_password: 'tempPassword',
    })
    if (Object.keys(fields).length > 0) {
      Object.assign(fieldErrors, fields)
      focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
    } else {
      actionError.value = 'platform_user_save_failed'
      toast.danger('Operator amali bajarilmadi')
    }
  } finally {
    saving.value = false
  }
}

function askReset(user: PlatformUser) {
  resetTarget.value = user
}

async function confirmReset() {
  const target = resetTarget.value
  if (!target) return
  actionId.value = target.id
  actionError.value = null
  try {
    await admin.resetPlatformUserPassword(target.id)
    resetTarget.value = null
    secretOpen.value = true
    toast.success('Yangi vaqtinchalik parol yaratildi')
  } catch {
    actionError.value = 'platform_user_reset_failed'
    toast.danger("Parolni qaytarib bo'lmadi")
  } finally {
    actionId.value = null
  }
}

function askBlock(user: PlatformUser) {
  blockTarget.value = user
  blockReason.value = ''
  clearFieldErrors(blockFieldErrors)
  blockModalOpen.value = true
}

async function confirmBlock() {
  clearFieldErrors(blockFieldErrors)
  if (!blockTarget.value) return
  if (!blockReason.value.trim()) {
    blockFieldErrors.blockReason = 'Majburiy maydon.'
    focusFirstFieldError(blockFieldErrors, ['blockReason'], { blockReason: 'op-block-reason' })
    return
  }
  actionId.value = blockTarget.value.id
  actionError.value = null
  try {
    await admin.blockPlatformUser(blockTarget.value.id, blockReason.value)
    blockModalOpen.value = false
    blockTarget.value = null
    toast.success('Operator bloklandi')
  } catch (blockErr) {
    Object.assign(
      blockFieldErrors,
      fieldErrorsFromApi<'blockReason'>(blockErr, { reason_required: 'blockReason' }),
    )
    if (blockFieldErrors.blockReason) {
      focusFirstFieldError(blockFieldErrors, ['blockReason'], { blockReason: 'op-block-reason' })
    } else {
      actionError.value = 'platform_user_block_failed'
      toast.danger(
        apiErrorCode(blockErr) === 'last_platform_operator'
          ? "Oxirgi faol operatorni bloklab bo'lmaydi"
          : "Operatorni bloklab bo'lmadi",
      )
    }
  } finally {
    actionId.value = null
  }
}

async function unblock(id: string) {
  actionId.value = id
  actionError.value = null
  try {
    await admin.unblockPlatformUser(id)
    toast.success('Operator blokdan chiqarildi')
  } catch {
    actionError.value = 'platform_user_unblock_failed'
    toast.danger("Operatorni blokdan chiqarib bo'lmadi")
  } finally {
    actionId.value = null
  }
}

onMounted(admin.loadPlatformUsers)
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Platforma operatorlari</h1>
        <p class="sub">Platforma doirasi bir xil; alohida ruxsat modeli yo'q.</p>
      </div>
      <button type="button" class="admin-primary-action" @click="openCreate">
        + Yangi operator
      </button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span>Qidiruv</span>
        <input v-model="query" placeholder="Ism, login yoki telefon" />
      </label>
      <AdminRefreshButton :loading="admin.opsLoading" @click="admin.loadPlatformUsers" />
    </div>

    <section v-if="admin.opsLoading" class="admin-card p-5" aria-live="polite">
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="admin.opsError"
      :code="admin.opsError"
      :trace-id="admin.opsTraceId"
      title="Operatorlar yuklanmadi"
      @retry="admin.loadPlatformUsers"
    />

    <section v-else-if="filtered.length === 0" class="admin-empty">
      <h3>Operator topilmadi</h3>
      <p>Filtrni tozalang yoki yangi operator yarating.</p>
    </section>

    <section v-else class="admin-card">
      <div class="admin-table-wrap">
        <table class="admin-table wide">
          <thead>
            <tr>
              <th>Operator</th>
              <th>Login</th>
              <th>Telefon</th>
              <th>Oxirgi kirish</th>
              <th>Holat</th>
              <th><span class="sr-only">Amallar</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in filtered" :key="user.id">
              <td class="nm">
                {{ user.full_name }}
                <span v-if="isCurrentOperator(user)" class="admin-pill admin-pill-info ml-2">
                  Joriy
                </span>
                <small>{{ user.id.slice(0, 8) }}</small>
              </td>
              <td class="admin-mono text-ink-muted">{{ user.login }}</td>
              <td class="admin-mono text-ink-muted">{{ user.phone }}</td>
              <td class="admin-mono text-ink-muted">{{ adminDateTime(user.last_login_at) }}</td>
              <td>
                <span class="admin-pill" :class="platformUserStatusTone(user.status)">
                  {{ platformUserStatusLabel(user.status) }}
                </span>
              </td>
              <td class="admin-right">
                <div class="flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :aria-label="`${user.full_name} operatorini tahrirlash`"
                    @click="openEdit(user)"
                  >
                    Tahrirlash
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :disabled="actionId === user.id"
                    :aria-label="`${user.full_name} operatori parolini qaytarish`"
                    @click="askReset(user)"
                  >
                    Parol qaytarish
                  </button>
                  <button
                    v-if="user.status === 'active'"
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
                    :disabled="blockDisabledReason(user) !== null || actionId === user.id"
                    :title="blockDisabledReason(user) ?? undefined"
                    :aria-label="
                      blockDisabledReason(user) ?? `${user.full_name} operatorini bloklash`
                    "
                    @click="askBlock(user)"
                  >
                    {{ blockDisabledReason(user) ?? 'Bloklash' }}
                  </button>
                  <button
                    v-else
                    type="button"
                    class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                    :disabled="actionId === user.id"
                    :aria-label="`${user.full_name} operatorini blokdan chiqarish`"
                    @click="unblock(user.id)"
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

    <p
      v-if="actionError"
      class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
      role="alert"
    >
      Operator amali bajarilmadi.
    </p>

    <AdminSecretModal
      :open="secretOpen && !!admin.lastPlatformUserSecret"
      title="Vaqtinchalik parol — bir martalik maxfiy ma'lumot"
      intro="Login va vaqtinchalik parolni operatorga yetkazing. Operator birinchi kirishda uni almashtiradi."
      :rows="secretRows"
      @close="closeSecret"
    />

    <ConfirmDialog
      :open="resetTarget !== null"
      title="Parolni qaytarish"
      :message="`${resetTarget?.full_name ?? ''} uchun yangi vaqtinchalik parol yaratiladi va uning barcha sessiyalari darhol bekor qilinadi.`"
      confirm-label="Parolni qaytarish"
      busy-label="Qaytarilmoqda"
      cancel-label="Bekor qilish"
      :busy="actionId === resetTarget?.id"
      danger
      @confirm="confirmReset"
      @cancel="resetTarget = null"
    />

    <template v-if="modalOpen">
      <div class="admin-modal-scrim" aria-hidden="true" @click="modalOpen = false"></div>
      <section
        ref="formPanel"
        class="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="operator-title"
        tabindex="-1"
        @keydown="formTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="operator-title">{{ editingId ? 'Operator tahrirlash' : 'Yangi operator' }}</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="modalOpen = false"
          >
            <AdminModalCloseIcon />
          </button>
        </div>
        <form novalidate @submit.prevent="saveUser">
          <div class="admin-modal-b">
            <div class="admin-form-grid">
              <label class="admin-field admin-full" for="op-name">
                <span>Ism</span>
                <input
                  id="op-name"
                  v-model="form.fullName"
                  autocomplete="name"
                  required
                  :aria-invalid="!!fieldErrors.fullName"
                  aria-describedby="op-name-error"
                />
                <span
                  v-if="fieldErrors.fullName"
                  id="op-name-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ fieldErrors.fullName }}
                </span>
              </label>
              <label class="admin-field" for="op-phone">
                <span>Telefon</span>
                <input
                  id="op-phone"
                  v-model="form.phone"
                  autocomplete="tel"
                  inputmode="tel"
                  required
                  :aria-invalid="!!fieldErrors.phone"
                  aria-describedby="op-phone-error"
                />
                <span
                  v-if="fieldErrors.phone"
                  id="op-phone-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ fieldErrors.phone }}
                </span>
              </label>
              <label class="admin-field" for="op-login">
                <span>Login</span>
                <input
                  id="op-login"
                  v-model="form.login"
                  autocomplete="username"
                  :disabled="!!editingId"
                  required
                  :aria-invalid="!!fieldErrors.login"
                  aria-describedby="op-login-error"
                />
                <span
                  v-if="fieldErrors.login"
                  id="op-login-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ fieldErrors.login }}
                </span>
              </label>
              <label v-if="!editingId" class="admin-field admin-full" for="op-pass">
                <span>Vaqtinchalik parol</span>
                <input
                  id="op-pass"
                  v-model="form.tempPassword"
                  autocomplete="new-password"
                  placeholder="Bo'sh qoldirilsa avtomatik yaratiladi"
                  :aria-invalid="!!fieldErrors.tempPassword"
                  aria-describedby="op-pass-error"
                />
                <span
                  v-if="fieldErrors.tempPassword"
                  id="op-pass-error"
                  class="admin-field-error"
                  role="alert"
                >
                  {{ fieldErrors.tempPassword }}
                </span>
              </label>
            </div>
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

    <template v-if="blockModalOpen && blockTarget">
      <div class="admin-modal-scrim" aria-hidden="true" @click="blockModalOpen = false"></div>
      <section
        ref="blockPanel"
        class="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="block-user-title"
        tabindex="-1"
        @keydown="blockTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="block-user-title">Operatorni bloklash</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="blockModalOpen = false"
          >
            <AdminModalCloseIcon />
          </button>
        </div>
        <form novalidate @submit.prevent="confirmBlock">
          <div class="admin-modal-b">
            <p class="mb-4 text-sm text-ink-soft">
              {{ blockTarget.full_name }} sessiyalari darhol bekor qilinadi. Blokdan chiqarilganda
              sessiyalar avtomatik tiklanmaydi — operator qaytadan kiradi.
            </p>
            <label class="admin-field" for="op-block-reason">
              <span>Majburiy sabab</span>
              <textarea
                id="op-block-reason"
                v-model="blockReason"
                required
                :aria-invalid="!!blockFieldErrors.blockReason"
                aria-describedby="op-block-reason-error"
              ></textarea>
              <span
                v-if="blockFieldErrors.blockReason"
                id="op-block-reason-error"
                class="admin-field-error"
                role="alert"
              >
                {{ blockFieldErrors.blockReason }}
              </span>
            </label>
          </div>
          <div class="admin-modal-f">
            <button
              type="button"
              class="mp-button mp-button-outline"
              @click="blockModalOpen = false"
            >
              Bekor
            </button>
            <button
              type="submit"
              class="mp-button bg-danger text-white"
              :disabled="actionId === blockTarget.id"
            >
              Bloklash
            </button>
          </div>
        </form>
      </section>
    </template>
  </section>
</template>
