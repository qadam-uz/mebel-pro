<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  type FieldErrors,
  uzPhone,
} from '@/shared/app/adminValidation'
import { copyText } from '@/shared/app/clipboard'
import { useRolePath } from '@/shared/app/paths'
import { initials, permissionLabels, workshopErrorMessage } from '@/shared/app/workshopUi'
import AppTabs from '@/shared/components/AppTabs.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import FormSelect from '@/shared/components/FormSelect.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatDate } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { permissionCatalog, useWorkshopStore } from '@/shared/stores/workshop'

type ProfileField = 'fullName' | 'phone' | 'login' | 'homeBranch'

const route = useRoute()
const rolePath = useRolePath()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const toast = useToast()
const userId = String(route.params.user_id)
const activeTab = ref<'profile' | 'permissions' | 'sessions'>('profile')
const user = computed(() => workshop.selectedUser)
const userTabs = computed<ChoiceOption[]>(() => [
  { value: 'profile', label: 'Profil' },
  { value: 'permissions', label: 'Ruxsatlar' },
  ...(user.value?.is_owner ? [] : [{ value: 'sessions', label: 'Sessiyalar' }]),
])
const reason = ref('')
const blockOpen = ref(false)
const unblockOpen = ref(false)
const resetOpen = ref(false)
const actionError = ref<string | null>(null)
const actionTraceId = ref<string | null>(null)
const acting = ref(false)
const copiedTempPassword = ref(false)
let copiedResetTimer: number | undefined

// Copy the freshly generated temp password to the clipboard. copyText guards
// insecure contexts / older browsers and returns false, in which case the mono
// value stays select-all so the owner can still copy it by hand.
async function copyTempPassword(value: string | null) {
  if (!value) return
  const ok = await copyText(value)
  if (!ok) {
    toast.danger("Nusxalab bo'lmadi. Parolni belgilab, qo'lda nusxalang.")
    return
  }
  toast.success('Parol nusxalandi.')
  copiedTempPassword.value = true
  window.clearTimeout(copiedResetTimer)
  copiedResetTimer = window.setTimeout(() => {
    copiedTempPassword.value = false
  }, 1800)
}
const profileSaving = ref(false)
const profileError = ref<string | null>(null)
const profileTraceId = ref<string | null>(null)
const profileSaved = ref<string | null>(null)
const selected = ref<Set<string>>(new Set())
const profileForm = reactive({
  fullName: '',
  phone: '',
  login: '',
  homeBranchId: '',
})
const profileFieldErrors = reactive<FieldErrors<ProfileField>>({})
const profileFieldOrder: ProfileField[] = ['fullName', 'phone', 'login', 'homeBranch']
const profileFieldIds: Record<ProfileField, string> = {
  fullName: 'user-profile-full-name',
  phone: 'user-profile-phone',
  login: 'user-profile-login',
  homeBranch: 'user-profile-home-branch',
}
const profileBranchOptions = computed<ChoiceOption[]>(() => [
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
    disabled: branch.status !== 'active',
  })),
])
// Staff actions are header buttons. Reset runs directly; block/unblock open a
// modal (block requires a reason via the modal's confirmDisabled).
function openBlock() {
  reason.value = ''
  blockOpen.value = true
}

function openUnblock() {
  unblockOpen.value = true
}
const grants = computed(() =>
  [...selected.value].map((value) => {
    const [permission, branch_id] = value.split('|')
    return { permission, branch_id }
  }),
)

function branchName(id: string | null) {
  if (!id) return '—'
  return workshop.branches.find((branch) => branch.id === id)?.name ?? 'Filial'
}

function grantKey(permission: string, branchId: string) {
  return `${permission}|${branchId}`
}

function toggleGrant(permission: string, branchId: string) {
  const next = new Set(selected.value)
  const key = grantKey(permission, branchId)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  selected.value = next
}

function syncProfileForm() {
  if (!user.value) return
  profileForm.fullName = user.value.full_name
  profileForm.phone = user.value.phone
  profileForm.login = user.value.login
  profileForm.homeBranchId = user.value.home_branch_id
}

function validateProfileForm() {
  clearFieldErrors(profileFieldErrors)
  profileFieldErrors.fullName = requiredText(profileForm.fullName) ?? undefined
  profileFieldErrors.phone =
    requiredText(profileForm.phone) ?? uzPhone(profileForm.phone) ?? undefined
  profileFieldErrors.login = requiredText(profileForm.login) ?? undefined
  profileFieldErrors.homeBranch = requiredText(profileForm.homeBranchId) ?? undefined
  const hasErrors = profileFieldOrder.some((field) => Boolean(profileFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(profileFieldErrors, profileFieldOrder, profileFieldIds)
  return !hasErrors
}

async function load() {
  if (!auth.me?.is_owner) return
  // A transient branch-context failure must not skip loadUser and make an existing
  // staffer look deleted; loadUser surfaces its own error state instead.
  await workshop.loadBranchContext().catch(() => undefined)
  await workshop.loadUser(userId)
  selected.value = new Set(
    user.value?.grants.map((grant) => grantKey(grant.permission, grant.branch_id)) ?? [],
  )
  syncProfileForm()
}

async function saveProfile() {
  if (!user.value || user.value.is_owner) return
  if (!validateProfileForm()) return
  profileSaving.value = true
  profileError.value = null
  profileTraceId.value = null
  profileSaved.value = null
  try {
    await workshop.updateUser(userId, {
      full_name: profileForm.fullName,
      phone: profileForm.phone,
      login: profileForm.login,
      home_branch_id: profileForm.homeBranchId,
    })
    syncProfileForm()
    profileSaved.value = 'Profil saqlandi.'
    toast.success('Profil saqlandi.')
  } catch (caught) {
    Object.assign(
      profileFieldErrors,
      fieldErrorsFromApi<ProfileField>(
        caught,
        {
          full_name_required: 'fullName',
          invalid_phone: 'phone',
          login_required: 'login',
          home_branch_required: 'homeBranch',
          branch_not_found: 'homeBranch',
          login_exists: 'login',
        },
        {
          full_name: 'fullName',
          phone: 'phone',
          login: 'login',
          home_branch_id: 'homeBranch',
        },
      ),
    )
    if (profileFieldOrder.some((field) => Boolean(profileFieldErrors[field]))) {
      focusFirstFieldError(profileFieldErrors, profileFieldOrder, profileFieldIds)
    }
    profileError.value = workshopErrorMessage(workshop.actionError ?? 'user_save_failed')
    profileTraceId.value = workshop.actionTraceId
  } finally {
    profileSaving.value = false
  }
}

async function saveGrants() {
  actionError.value = null
  actionTraceId.value = null
  acting.value = true
  try {
    await workshop.replaceGrants(userId, grants.value)
    await load()
    toast.success('Ruxsatlar saqlandi.')
  } catch {
    actionError.value = workshopErrorMessage(workshop.actionError ?? 'grants_save_failed')
    actionTraceId.value = workshop.actionTraceId
  } finally {
    acting.value = false
  }
}

async function resetPassword() {
  actionError.value = null
  actionTraceId.value = null
  acting.value = true
  try {
    await workshop.resetPassword(userId)
    resetOpen.value = false
    toast.success('Vaqtinchalik parol yaratildi.')
  } catch {
    resetOpen.value = false
    actionError.value = workshopErrorMessage(workshop.actionError ?? 'password_reset_failed')
    actionTraceId.value = workshop.actionTraceId
  } finally {
    acting.value = false
  }
}

async function block() {
  if (!user.value || user.value.is_owner || !reason.value.trim()) return
  actionError.value = null
  actionTraceId.value = null
  acting.value = true
  try {
    await workshop.blockUser(userId, reason.value)
    reason.value = ''
    blockOpen.value = false
    toast.success('Xodim bloklandi.')
  } catch {
    blockOpen.value = false
    actionError.value = workshopErrorMessage(workshop.actionError ?? 'user_block_failed')
    actionTraceId.value = workshop.actionTraceId
  } finally {
    acting.value = false
  }
}

async function unblock() {
  if (!user.value || user.value.is_owner) return
  actionError.value = null
  actionTraceId.value = null
  acting.value = true
  try {
    await workshop.unblockUser(userId)
    unblockOpen.value = false
    toast.success('Xodim faollashtirildi.')
  } catch {
    unblockOpen.value = false
    actionError.value = workshopErrorMessage(workshop.actionError ?? 'user_unblock_failed')
    actionTraceId.value = workshop.actionTraceId
  } finally {
    acting.value = false
  }
}

async function revokeAllSessions() {
  actionError.value = null
  actionTraceId.value = null
  acting.value = true
  try {
    await workshop.revokeUserSessions(userId)
    toast.success('Sessiyalar yopildi.')
  } catch {
    actionError.value = workshopErrorMessage(workshop.actionError ?? 'sessions_revoke_failed')
    actionTraceId.value = workshop.actionTraceId
  } finally {
    acting.value = false
  }
}

async function revokeSession(sessionId: string) {
  actionError.value = null
  actionTraceId.value = null
  acting.value = true
  try {
    await workshop.revokeUserSession(userId, sessionId)
    toast.success('Sessiya yopildi.')
  } catch {
    actionError.value = workshopErrorMessage(workshop.actionError ?? 'session_revoke_failed')
    actionTraceId.value = workshop.actionTraceId
  } finally {
    acting.value = false
  }
}

watch(user, () => {
  syncProfileForm()
  if (user.value?.is_owner && activeTab.value === 'sessions') activeTab.value = 'profile'
})
onMounted(load)
onBeforeUnmount(() => window.clearTimeout(copiedResetTimer))
</script>

<template>
  <section>
    <RouterLink :to="rolePath('/workshop/settings/users')" class="back">← Xodimlar</RouterLink>

    <section v-if="!auth.me?.is_owner" class="st-empty">
      <h3>Bu bo'lim faqat ustaxona egasi uchun</h3>
      <p>Ruxsatlar va sessiyalarni egasi boshqaradi.</p>
    </section>

    <section v-else-if="workshop.loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="workshop.error" class="st-error">
      <h3>Xodimni yuklab bo'lmadi</h3>
      <p>trace_id: {{ workshop.traceId ?? 'unavailable' }}</p>
    </section>

    <section v-else-if="!user" class="st-empty">
      <h3>Xodim topilmadi</h3>
    </section>

    <template v-else>
      <div class="page-head mt-2">
        <div>
          <div class="flex items-center gap-4">
            <span
              class="grid size-14 place-items-center rounded-full bg-accent font-serif text-xl font-bold text-white"
            >
              {{ initials(user.full_name, 'U') }}
            </span>
            <div>
              <h1>
                {{ user.full_name }}
                <span v-if="user.is_owner" class="pill p-cut ml-2 align-middle">Egasi</span>
                <span
                  v-else
                  class="ml-2 align-middle"
                  :class="user.status === 'active' ? 'pill p-ok' : 'pill p-bad'"
                >
                  <span class="pd"></span>{{ user.status === 'active' ? 'Faol' : 'Bloklangan' }}
                </span>
              </h1>
              <p class="sub">
                {{ user.login }} · {{ user.phone }} · {{ branchName(user.home_branch_id) }}
              </p>
            </div>
          </div>
        </div>
        <div v-if="!user.is_owner" class="tools">
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            :disabled="acting"
            @click="resetOpen = true"
          >
            Parolni tiklash
          </button>
          <button
            v-if="user.status === 'active'"
            type="button"
            class="mp-button bg-danger text-white min-h-9 px-3 text-xs"
            :disabled="acting"
            @click="openBlock"
          >
            Bloklash
          </button>
          <button
            v-else
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            :disabled="acting"
            @click="openUnblock"
          >
            Faollashtirish
          </button>
        </div>
      </div>

      <div v-if="workshop.lastTempPassword" class="banner info mt-3" role="status">
        <div class="grow">
          <b>Yangi vaqtinchalik parol</b>
          <div class="mt-1.5 flex flex-wrap items-center gap-2">
            <span
              class="select-all rounded bg-white px-2.5 py-1 font-mono text-base font-bold text-ink"
            >
              {{ workshop.lastTempPassword }}
            </span>
            <button
              type="button"
              class="mp-button mp-button-outline min-h-9 px-3 text-xs"
              @click="copyTempPassword(workshop.lastTempPassword)"
            >
              {{ copiedTempPassword ? 'Nusxalandi' : 'Nusxalash' }}
            </button>
          </div>
          <p class="mt-1.5 text-xs">
            Bu parol faqat 1 marta ko'rsatiladi — xodimga yetkazib qo'ying.
          </p>
        </div>
      </div>

      <div v-if="!user.is_owner && user.status === 'blocked'" class="banner warn mt-3">
        <div class="grow">
          Bu xodim bloklangan. Faollashtirish uchun amallar menyusidan foydalaning.
        </div>
      </div>
      <div v-else-if="user.is_owner" class="banner info mt-3">
        <div class="grow">Egasi bloklanmaydi va barcha ruxsatlarga ega.</div>
      </div>

      <AppTabs
        v-model="activeTab"
        id-prefix="workshop-user"
        label="Xodim bo'limlari"
        :tabs="userTabs"
      />

      <section
        v-if="activeTab === 'profile'"
        id="workshop-user-profile-panel"
        class="grid max-w-[640px] gap-5"
        role="tabpanel"
        aria-labelledby="workshop-user-profile-tab"
        tabindex="0"
      >
        <div class="card">
          <div class="card-h"><h2>Profil</h2></div>
          <div class="card-b">
            <form v-if="!user.is_owner" class="grid gap-3" novalidate @submit.prevent="saveProfile">
              <label class="field" for="user-profile-full-name">
                <span>F.I.O</span>
                <input
                  id="user-profile-full-name"
                  v-model="profileForm.fullName"
                  class="mp-input"
                  autocomplete="name"
                  required
                  :aria-invalid="!!profileFieldErrors.fullName"
                  :aria-describedby="
                    profileFieldErrors.fullName ? 'user-profile-full-name-error' : undefined
                  "
                />
                <span
                  v-if="profileFieldErrors.fullName"
                  id="user-profile-full-name-error"
                  class="mp-field-error"
                >
                  {{ profileFieldErrors.fullName }}
                </span>
              </label>
              <label class="field" for="user-profile-phone">
                <span>Telefon</span>
                <PhoneInput
                  id="user-profile-phone"
                  v-model="profileForm.phone"
                  required
                  :aria-invalid="!!profileFieldErrors.phone"
                  :aria-describedby="
                    profileFieldErrors.phone ? 'user-profile-phone-error' : undefined
                  "
                />
                <span
                  v-if="profileFieldErrors.phone"
                  id="user-profile-phone-error"
                  class="mp-field-error"
                >
                  {{ profileFieldErrors.phone }}
                </span>
              </label>
              <label class="field" for="user-profile-login">
                <span>Login</span>
                <input
                  id="user-profile-login"
                  v-model="profileForm.login"
                  class="mp-input"
                  autocomplete="username"
                  required
                  :aria-invalid="!!profileFieldErrors.login"
                  :aria-describedby="
                    profileFieldErrors.login ? 'user-profile-login-error' : undefined
                  "
                />
                <span
                  v-if="profileFieldErrors.login"
                  id="user-profile-login-error"
                  class="mp-field-error"
                >
                  {{ profileFieldErrors.login }}
                </span>
              </label>
              <FormSelect
                id="user-profile-home-branch"
                v-model="profileForm.homeBranchId"
                label="Asosiy filial"
                :options="profileBranchOptions"
                :error="profileFieldErrors.homeBranch"
                required
              />
              <button class="mp-button mp-button-primary" type="submit" :disabled="profileSaving">
                {{ profileSaving ? 'Saqlanmoqda' : 'Saqlash' }}
              </button>
              <p
                v-if="profileSaved"
                class="rounded-md bg-success-soft px-3 py-2 text-sm font-bold text-success"
              >
                {{ profileSaved }}
              </p>
              <p
                v-if="profileError"
                class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
              >
                {{ profileError }} · trace_id: {{ profileTraceId ?? 'unavailable' }}
              </p>
            </form>
            <div v-else>
              <div class="row-item">
                <div><div class="nm">F.I.O</div></div>
                <div class="meta">{{ user.full_name }}</div>
              </div>
              <div class="row-item">
                <div><div class="nm">Telefon</div></div>
                <div class="meta">{{ user.phone }}</div>
              </div>
              <div class="row-item">
                <div><div class="nm">Login</div></div>
                <div class="meta">{{ user.login }}</div>
              </div>
              <div class="row-item">
                <div><div class="nm">Asosiy filial</div></div>
                <div class="meta">{{ branchName(user.home_branch_id) }}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        v-else-if="activeTab === 'permissions'"
        id="workshop-user-permissions-panel"
        class="card"
        role="tabpanel"
        aria-labelledby="workshop-user-permissions-tab"
        tabindex="0"
      >
        <div class="card-h">
          <h2>Ruxsatlar matritsasi</h2>
          <button
            v-if="!user.is_owner"
            type="button"
            class="mp-button mp-button-primary min-h-9 px-3 text-xs"
            :disabled="acting"
            @click="saveGrants"
          >
            Saqlash
          </button>
        </div>
        <div class="card-b">
          <div v-if="user.is_owner" class="banner info">
            <div class="grow">Egasi avtomatik tarzda barcha filialda barcha ruxsatga ega.</div>
          </div>
          <div class="table-wrap">
            <table class="matrix">
              <thead>
                <tr>
                  <th class="permission">Ruxsat</th>
                  <th v-for="branch in workshop.branches" :key="branch.id">{{ branch.name }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="permission in permissionCatalog" :key="permission">
                  <td class="permission">
                    {{ permissionLabels[permission] ?? permission }}
                    <small class="block font-mono text-[10.5px] font-normal text-ink-muted">{{
                      permission
                    }}</small>
                  </td>
                  <td v-for="branch in workshop.branches" :key="branch.id">
                    <input
                      type="checkbox"
                      class="size-4 accent-accent"
                      :aria-label="`${permissionLabels[permission] ?? permission} — ${branch.name}`"
                      :checked="user.is_owner || selected.has(grantKey(permission, branch.id))"
                      :disabled="user.is_owner"
                      @change="toggleGrant(permission, branch.id)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section
        v-else
        id="workshop-user-sessions-panel"
        class="card"
        role="tabpanel"
        aria-labelledby="workshop-user-sessions-tab"
        tabindex="0"
      >
        <div class="card-h">
          <h2>Faol sessiyalar</h2>
          <button
            type="button"
            class="mp-button bg-danger text-white min-h-9 px-3 text-xs"
            :disabled="acting || workshop.sessions.length === 0"
            @click="revokeAllSessions"
          >
            Hammasi yopilsin
          </button>
        </div>
        <div class="card-b">
          <div v-if="workshop.sessions.length === 0" class="st-empty !border-0 !py-8">
            <h3>Faol sessiya yo'q</h3>
          </div>
          <div v-for="session in workshop.sessions" v-else :key="session.id" class="row-item">
            <div>
              <div class="nm">
                {{ session.device_info?.browser ?? 'Qurilma' }}
                <span v-if="session.is_current" class="pill p-ok ml-1">Joriy</span>
              </div>
              <small class="text-ink-muted">
                Yaratildi {{ formatDate(session.created_at) }} · oxirgi
                {{ formatDate(session.last_used_at) }}
              </small>
            </div>
            <div class="meta">
              <button
                type="button"
                class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                :disabled="acting"
                @click="revokeSession(session.id)"
              >
                Yopish
              </button>
            </div>
          </div>
        </div>
      </section>

      <div v-if="actionError" class="banner danger mt-4">
        <div class="grow">{{ actionError }} · trace_id: {{ actionTraceId ?? 'unavailable' }}</div>
      </div>

      <ConfirmDialog
        :open="blockOpen"
        title="Xodimni bloklash"
        message="Bloklangan xodim tizimga kira olmaydi va barcha sessiyalari yopiladi."
        confirm-label="Bloklash"
        cancel-label="Bekor qilish"
        busy-label="Bloklanmoqda"
        danger
        :busy="acting"
        :confirm-disabled="!reason.trim()"
        @cancel="blockOpen = false"
        @confirm="block"
      >
        <label class="field" for="block-reason">
          <span>Bloklash sababi</span>
          <input
            id="block-reason"
            v-model="reason"
            class="mp-input"
            required
            placeholder="Masalan: ishdan bo'shadi"
          />
        </label>
      </ConfirmDialog>

      <ConfirmDialog
        :open="unblockOpen"
        title="Xodimni faollashtirish"
        message="Xodim yana tizimga kira oladi."
        confirm-label="Faollashtirish"
        cancel-label="Bekor qilish"
        busy-label="Faollashtirilmoqda"
        :busy="acting"
        @cancel="unblockOpen = false"
        @confirm="unblock"
      />

      <ConfirmDialog
        :open="resetOpen"
        title="Parolni tiklash"
        :message="`${user.full_name} uchun yangi vaqtinchalik parol yaratiladi va uning barcha sessiyalari darhol bekor qilinadi.`"
        confirm-label="Parolni tiklash"
        cancel-label="Bekor qilish"
        busy-label="Tiklanmoqda"
        danger
        :busy="acting"
        @cancel="resetOpen = false"
        @confirm="resetPassword"
      />
    </template>
  </section>
</template>
