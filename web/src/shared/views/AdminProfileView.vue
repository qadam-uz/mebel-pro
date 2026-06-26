<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  tempPassword,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import { adminDateTime } from '@/shared/app/adminUi'
import AppTabs from '@/shared/components/AppTabs.vue'
import { useToast } from '@/shared/composables/useToast'
import type { SessionResponse } from '@/shared/stores/auth'
import { useAuthStore } from '@/shared/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()
// A reset-required operator is pinned here by the router guard; open the password
// tab straight away so the one thing they can do is in front of them.
const tab = ref<'profile' | 'password' | 'sessions'>(
  auth.me?.password_reset_required ? 'password' : 'profile',
)
const sessions = ref<SessionResponse[]>([])
const sessionsError = ref(false)
const revokingId = ref<string | null>(null)
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const saving = ref(false)
const loggingOut = ref(false)
type PasswordField = 'current' | 'next' | 'confirm'
const fieldErrors = reactive<FieldErrors<PasswordField>>({})
const fieldIds: Record<PasswordField, string> = {
  current: 'admin-current-password',
  next: 'admin-new-password',
  confirm: 'admin-confirm-password',
}
const fieldOrder: PasswordField[] = ['current', 'next', 'confirm']
const tabOptions = [
  { value: 'profile', label: 'Profil' },
  { value: 'password', label: 'Parol' },
  { value: 'sessions', label: 'Sessiyalar' },
]

const profileRows = computed(() => [
  ['Ism', auth.displayName],
  ['Login', auth.me?.login ?? '-'],
  ['Telefon', auth.me?.phone ?? '-'],
  ['Ruxsat doirasi', 'Platforma admini'],
  ['Holat', auth.me?.status === 'blocked' ? 'Bloklangan' : 'Faol'],
  ['Sessiya', auth.me?.session_id ?? '-'],
])

// AB-38: confirm-password match + a lightweight strength meter.
const passwordMismatch = computed(
  () => confirmPassword.value.length > 0 && newPassword.value !== confirmPassword.value,
)
const passwordStrength = computed(() => {
  const value = newPassword.value
  let score = 0
  if (value.length >= 8) score += 1
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1
  if (/\d/.test(value)) score += 1
  if (/[^A-Za-z0-9]/.test(value)) score += 1
  return score
})
const passwordStrengthLabel = computed(
  () => ['Juda zaif', 'Zaif', "O'rtacha", 'Yaxshi', 'Kuchli'][passwordStrength.value] ?? '',
)

function deviceLabel(session: SessionResponse) {
  const browser = session.device_info.browser
  const os = session.device_info.os
  return [browser, os].filter((part) => typeof part === 'string' && part).join(' · ') || 'Brauzer'
}

async function loadSessions() {
  sessionsError.value = false
  try {
    sessions.value = await auth.fetchSessions()
  } catch {
    sessionsError.value = true
  }
}

async function revoke(id: string) {
  revokingId.value = id
  try {
    await auth.revokeSession(id)
    sessions.value = sessions.value.filter((session) => session.id !== id)
    toast.success('Sessiya yopildi')
  } catch {
    toast.danger("Sessiyani yopib bo'lmadi")
  } finally {
    revokingId.value = null
  }
}

async function changePassword() {
  clearFieldErrors(fieldErrors)
  fieldErrors.current = requiredText(currentPassword.value, 'Joriy parolni kiriting.') ?? undefined
  fieldErrors.next =
    requiredText(newPassword.value, 'Yangi parolni kiriting.') ??
    tempPassword(newPassword.value) ??
    undefined
  fieldErrors.confirm =
    requiredText(confirmPassword.value, 'Tasdiqlash parolini kiriting.') ??
    (passwordMismatch.value ? 'Parollar mos kelmadi.' : undefined)
  if (fieldOrder.some((field) => fieldErrors[field])) {
    focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
    return
  }
  saving.value = true
  message.value = null
  error.value = null
  try {
    await auth.changePassword(currentPassword.value, newPassword.value)
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    message.value = "Parol o'zgartirildi."
  } catch (changeError) {
    const fields = fieldErrorsFromApi<PasswordField>(changeError, {
      invalid_current_password: 'current',
      weak_password: 'next',
    })
    if (Object.keys(fields).length > 0) {
      Object.assign(fieldErrors, fields)
      focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
    } else {
      error.value = "Parolni o'zgartirib bo'lmadi."
    }
  } finally {
    saving.value = false
  }
}

async function logoutCurrent() {
  loggingOut.value = true
  try {
    await auth.logoutCurrent()
    await router.replace('/auth/login')
  } catch {
    loggingOut.value = false
    toast.danger("Chiqib bo'lmadi")
  }
}

async function logoutEverywhere() {
  loggingOut.value = true
  try {
    await auth.logoutEverywhere()
    await router.replace('/auth/login')
  } catch {
    loggingOut.value = false
    toast.danger("Chiqib bo'lmadi")
  }
}

onMounted(loadSessions)
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Profilim</h1>
      </div>
      <button
        type="button"
        class="mp-button mp-button-outline"
        :disabled="loggingOut"
        @click="logoutCurrent"
      >
        Chiqib ketish
      </button>
    </div>

    <AppTabs
      v-model="tab"
      :tabs="tabOptions"
      id-prefix="pf"
      label="Profil bo'limlari"
      variant="admin"
    />

    <section
      v-if="tab === 'profile'"
      id="pf-profile-panel"
      role="tabpanel"
      aria-labelledby="pf-profile-tab"
      class="admin-card max-w-[640px]"
    >
      <div class="admin-card-h">
        <h2>Profil</h2>
      </div>
      <div class="admin-card-b">
        <dl class="grid gap-4 sm:grid-cols-2">
          <div v-for="[label, value] in profileRows" :key="label">
            <dt class="text-xs font-extrabold uppercase text-ink-muted">{{ label }}</dt>
            <dd class="mt-1 break-all text-base font-bold text-ink">{{ value }}</dd>
          </div>
        </dl>
      </div>
    </section>

    <section
      v-else-if="tab === 'password'"
      id="pf-password-panel"
      role="tabpanel"
      aria-labelledby="pf-password-tab"
      class="admin-card max-w-[520px]"
    >
      <div class="admin-card-h">
        <h2>Parolni o'zgartirish</h2>
      </div>
      <form class="admin-card-b grid gap-4" novalidate @submit.prevent="changePassword">
        <label class="admin-field" for="admin-current-password">
          <span class="admin-field-label">Joriy parol</span>
          <input
            id="admin-current-password"
            v-model="currentPassword"
            type="password"
            autocomplete="current-password"
            required
            :aria-invalid="!!fieldErrors.current"
            aria-describedby="admin-current-password-error"
          />
          <span
            v-if="fieldErrors.current"
            id="admin-current-password-error"
            class="admin-field-error"
            role="alert"
          >
            {{ fieldErrors.current }}
          </span>
        </label>
        <label class="admin-field" for="admin-new-password">
          <span class="admin-field-label">Yangi parol</span>
          <input
            id="admin-new-password"
            v-model="newPassword"
            type="password"
            autocomplete="new-password"
            minlength="8"
            required
            :aria-invalid="!!fieldErrors.next"
            aria-describedby="admin-new-password-error"
          />
          <span
            v-if="newPassword"
            class="mt-1 text-xs font-bold"
            :class="passwordStrength >= 3 ? 'text-success' : 'text-ink-muted'"
          >
            Kuchi: {{ passwordStrengthLabel }}
          </span>
          <span
            v-if="fieldErrors.next"
            id="admin-new-password-error"
            class="admin-field-error"
            role="alert"
          >
            {{ fieldErrors.next }}
          </span>
        </label>
        <label class="admin-field" for="admin-confirm-password">
          <span class="admin-field-label">Tasdiqlash</span>
          <input
            id="admin-confirm-password"
            v-model="confirmPassword"
            type="password"
            autocomplete="new-password"
            required
            :aria-invalid="!!fieldErrors.confirm || passwordMismatch"
            aria-describedby="admin-confirm-password-error"
          />
          <span
            v-if="fieldErrors.confirm || passwordMismatch"
            id="admin-confirm-password-error"
            class="admin-field-error"
            role="alert"
          >
            {{ fieldErrors.confirm ?? 'Parollar mos kelmadi.' }}
          </span>
        </label>
        <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
          {{ saving ? 'Saqlanmoqda' : "O'zgartirish" }}
        </button>
        <p v-if="message" class="text-sm font-bold text-success" role="status">{{ message }}</p>
        <p v-if="error" class="text-sm font-bold text-danger" role="alert">{{ error }}</p>
      </form>
    </section>

    <section
      v-else
      id="pf-sessions-panel"
      role="tabpanel"
      aria-labelledby="pf-sessions-tab"
      class="admin-card max-w-[720px]"
    >
      <div class="admin-card-h">
        <h2>Faol sessiyalar</h2>
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
          :disabled="loggingOut"
          @click="logoutEverywhere"
        >
          Hammasi yopilsin
        </button>
      </div>
      <div class="admin-card-b">
        <p
          v-if="sessionsError"
          class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          role="alert"
        >
          Sessiyalarni yuklab bo'lmadi.
          <button type="button" class="ml-2 underline" @click="loadSessions">Qayta urinish</button>
        </p>
        <div v-else-if="sessions.length === 0" class="admin-empty">
          <h3>Sessiya topilmadi</h3>
          <p>Joriy sessiya keyingi yangilashda ko'rinadi.</p>
        </div>
        <div v-else class="admin-row-list">
          <article v-for="session in sessions" :key="session.id" class="admin-row-item">
            <span
              class="admin-pill"
              :class="session.is_current ? 'admin-pill-success' : 'admin-pill-muted'"
            >
              {{ session.is_current ? 'joriy' : 'faol' }}
            </span>
            <span>
              <b>{{ deviceLabel(session) }}</b>
              <small class="block text-ink-muted">
                Oxirgi: {{ adminDateTime(session.last_used_at) }}
              </small>
            </span>
            <button
              v-if="!session.is_current"
              type="button"
              class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
              :disabled="revokingId === session.id"
              @click="revoke(session.id)"
            >
              Yopish
            </button>
            <span v-else class="admin-mono text-ink-muted">{{ session.id.slice(0, 8) }}</span>
          </article>
        </div>
      </div>
    </section>
  </section>
</template>
