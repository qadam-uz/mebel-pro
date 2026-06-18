<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/shared/api/client'
import { formatPhone } from '@/shared/app/clientUi'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { formatDate } from '@/shared/formatters'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useAuthStore, type SessionResponse } from '@/shared/stores/auth'
import { useOrdersStore } from '@/shared/stores/orders'
import { useWorkshopStore } from '@/shared/stores/workshop'

interface ClientProfile {
  id: string
  phone: string
  name: string
  preferred_branch_id: string | null
  status: 'active' | 'blocked'
}

interface ClientBranchOption {
  branch_id: string
  workshop_name: string
  branch_name: string
  status: 'active' | 'temporarily_closed'
  closed_reason: string | null
}

const config = useRoleConfig()
const auth = useAuthStore()
const orders = useOrdersStore()
const workshop = useWorkshopStore()
const router = useRouter()

const sessions = ref<SessionResponse[]>([])
const currentPassword = ref('')
const newPassword = ref('')
const clientName = ref('')
const preferredBranchId = ref<string | null>(null)
const branchOptions = ref<ClientBranchOption[]>([])
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const isSaving = ref(false)
const editingClientName = ref(false)
const logoutCurrentOpen = ref(false)
const logoutEverywhereOpen = ref(false)
const workshopProfileTab = ref<'profile' | 'password' | 'sessions'>('profile')

const accountLabel = computed(() => auth.displayName)
const branchChoiceOptions = computed<ChoiceOption[]>(() =>
  branchOptions.value.map((option) => ({
    value: option.branch_id,
    label: `${option.workshop_name} · ${option.branch_name}`,
    meta:
      option.status === 'temporarily_closed'
        ? (option.closed_reason ?? 'vaqtincha yopiq')
        : undefined,
    disabled: option.status === 'temporarily_closed',
  })),
)
const scopeLabel = computed(() => {
  if (auth.me?.principal_type === 'workshop_user') {
    return auth.me.is_owner ? 'Egasi · barcha ruxsatlar' : `${auth.me.grants.length} ruxsat`
  }
  if (auth.me?.principal_type === 'platform_user') return 'Platforma operatori'
  return auth.me?.preferred_branch_id ? 'Afzal filial tanlangan' : 'Afzal filial tanlanmagan'
})
const workshopProfileSubtitle = computed(() => {
  const role = auth.me?.is_owner ? 'Egasi' : 'Xodim'
  const tenant = workshop.settings?.name?.trim() || config.tenantLabel
  return `${auth.displayName} · ${role} · ${tenant}`
})
const workshopGrantRows = computed(() => {
  if (auth.me?.principal_type !== 'workshop_user' || auth.me.is_owner) return []
  return auth.me.grants.map((grant) => ({
    key: `${grant.permission}-${grant.branch_id}`,
    permission: grant.permission,
    label: workshopPermissionLabel(grant.permission),
    branch:
      workshop.branches.find((branch) => branch.id === grant.branch_id)?.name ??
      grant.branch_id.slice(0, 8),
  }))
})

function goBack() {
  // Reached via a deep link / refresh, history may have no in-app entry to return to.
  if (window.history.state?.back) router.back()
  else router.push(config.homePath)
}

async function loadSessions() {
  sessions.value = await auth.fetchSessions()
}

async function loadClientProfile() {
  if (auth.me?.principal_type !== 'client') return
  const profile = await api.get<ClientProfile>('/client/profile', { accessToken: auth.accessToken })
  branchOptions.value = await api.get<ClientBranchOption[]>('/client/branch-options', {
    accessToken: auth.accessToken,
  })
  clientName.value = profile.name
  preferredBranchId.value = profile.preferred_branch_id
}

async function saveClientProfile() {
  error.value = null
  message.value = null
  isSaving.value = true
  try {
    const updated = await api.patch<ClientProfile>(
      '/client/profile',
      {
        name: clientName.value,
        preferred_branch_id: preferredBranchId.value,
      },
      { accessToken: auth.accessToken },
    )
    if (auth.me) {
      auth.me = {
        ...auth.me,
        name: updated.name,
        preferred_branch_id: updated.preferred_branch_id,
      }
    }
    message.value = 'Profil yangilandi.'
    editingClientName.value = false
  } catch {
    error.value = 'profile_update_failed'
  } finally {
    isSaving.value = false
  }
}

async function savePassword() {
  error.value = null
  message.value = null
  isSaving.value = true
  try {
    await auth.changePassword(currentPassword.value, newPassword.value)
    currentPassword.value = ''
    newPassword.value = ''
    message.value = "Parol o'zgartirildi."
    await loadSessions()
  } catch {
    error.value = auth.lastError ?? 'password_change_failed'
  } finally {
    isSaving.value = false
  }
}

async function logoutCurrent() {
  await auth.logoutCurrent()
  await router.replace(config.loginPath)
}

async function logoutEverywhere() {
  await auth.logoutEverywhere()
  await router.replace(config.loginPath)
}

function deviceLabel(session: SessionResponse) {
  const browser =
    typeof session.device_info.browser === 'string' && session.device_info.browser.trim()
      ? session.device_info.browser
      : 'Browser'
  const os =
    typeof session.device_info.os === 'string' && session.device_info.os.trim()
      ? session.device_info.os
      : 'Qurilma'
  return `${browser} · ${os}`
}

function workshopPermissionLabel(permission: string) {
  const labels: Record<string, string> = {
    view_dashboard: 'Dashboard',
    manage_orders: 'Buyurtmalarni boshqarish',
    process_production: 'Ishlab chiqarish',
    manage_inventory: 'Ombor',
    manage_catalog: 'Katalog',
    manage_finance: 'Moliya yozuvlari',
    view_finance_reports: 'Moliya hisobotlari',
  }
  return labels[permission] ?? permission
}

onMounted(async () => {
  if (auth.me?.principal_type === 'workshop_user' && auth.me.password_reset_required) {
    workshopProfileTab.value = 'password'
  }
  await Promise.all([
    loadSessions(),
    loadClientProfile(),
    auth.me?.principal_type === 'client' ? orders.loadClientOrders() : Promise.resolve(),
    auth.me?.principal_type === 'workshop_user' ? workshop.loadSettings() : Promise.resolve(),
  ])
})
</script>

<template>
  <section v-if="auth.me?.principal_type === 'client'">
    <button type="button" class="client-back" @click="goBack">← Orqaga</button>

    <div class="client-page-head">
      <div>
        <h1>Profil</h1>
        <p class="sub">Profilingiz va faol sessiyalar.</p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="logoutCurrentOpen = true">
        Chiqib ketish
      </button>
    </div>

    <div class="grid max-w-[760px] gap-5">
      <section class="client-card">
        <div class="client-card-h">
          <h2>Profil</h2>
        </div>
        <div class="client-card-b">
          <div class="client-row-item">
            <div>
              <div class="client-row-name">Ism</div>
              <div class="text-sm text-ink-muted">
                Ustaxona buyurtmangiz bo'yicha sizga shunday murojaat qiladi
              </div>
            </div>
            <div class="flex items-center gap-2">
              <form
                v-if="editingClientName"
                class="flex items-center gap-2"
                @submit.prevent="saveClientProfile"
              >
                <input
                  v-model="clientName"
                  class="mp-input min-w-52"
                  autocomplete="name"
                  required
                />
                <button
                  type="submit"
                  class="mp-button mp-button-primary min-h-8 px-3 text-xs"
                  :disabled="isSaving"
                >
                  Saqlash
                </button>
              </form>
              <template v-else>
                <span class="font-bold text-ink">{{ auth.displayName }}</span>
                <button
                  type="button"
                  class="mp-button mp-button-outline min-h-8 px-3 text-xs"
                  @click="editingClientName = true"
                >
                  O'zgartirish
                </button>
              </template>
            </div>
          </div>

          <div class="client-row-item">
            <div>
              <div class="client-row-name">Telefon</div>
              <div class="text-sm text-ink-muted">
                Kirish uchun ishlatiladi · o'zgartirib bo'lmaydi
              </div>
            </div>
            <div class="font-mono text-sm text-ink">{{ formatPhone(auth.me?.phone) }}</div>
          </div>

          <div class="client-row-item">
            <div>
              <div class="client-row-name">Afzal filial</div>
              <div class="text-sm text-ink-muted">
                Yangi chizma shu filial konteksti bilan boshlanadi
              </div>
            </div>
            <div class="grid w-full max-w-md gap-2 sm:justify-items-end">
              <FormSelect
                v-model="preferredBranchId"
                class="w-full sm:max-w-md"
                label="Tanlangan"
                :options="branchChoiceOptions"
                placeholder="Tanlanmagan"
              />
              <div class="flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  class="mp-button mp-button-outline min-h-8 px-3 text-xs"
                  @click="preferredBranchId = null"
                >
                  Tozalash
                </button>
                <button
                  type="button"
                  class="mp-button mp-button-primary min-h-8 px-3 text-xs"
                  :disabled="isSaving"
                  @click="saveClientProfile"
                >
                  Saqlash
                </button>
              </div>
            </div>
          </div>

          <div class="client-row-item">
            <div>
              <div class="client-row-name">Buyurtmalar soni</div>
            </div>
            <div class="font-mono text-sm text-ink">{{ orders.clientOrders.length }} ta</div>
          </div>

          <p v-if="message" class="mt-3 text-sm font-bold text-success">{{ message }}</p>
          <p v-if="error" class="mt-3 text-sm font-bold text-danger">{{ error }}</p>
        </div>
      </section>

      <section class="client-card">
        <div class="client-card-h">
          <h2>Faol sessiyalar</h2>
          <button
            type="button"
            class="mp-button mp-button-outline min-h-8 px-3 text-xs text-danger"
            @click="logoutEverywhereOpen = true"
          >
            Hammasini chiqarish
          </button>
        </div>
        <div class="client-card-b">
          <div v-if="sessions.length === 0" class="text-sm text-ink-muted">
            Faol sessiya topilmadi.
          </div>
          <template v-else>
            <div v-for="session in sessions" :key="session.id" class="client-row-item">
              <div>
                <div class="client-row-name">
                  {{ deviceLabel(session) }}
                  <span v-if="session.is_current" class="client-pill client-pill-ready ml-2"
                    >Joriy</span
                  >
                </div>
                <div class="text-sm text-ink-muted">
                  {{ formatDate(session.last_used_at) }} · {{ session.id.slice(0, 8) }}
                </div>
              </div>
              <div class="font-mono text-xs text-ink-muted">
                {{ session.is_current ? '—' : 'active' }}
              </div>
            </div>
          </template>
        </div>
      </section>
    </div>

    <ConfirmDialog
      :open="logoutCurrentOpen"
      title="Chiqib ketish"
      message="Mijoz kabinetidan chiqasiz."
      confirm-label="Chiqish"
      danger
      @cancel="logoutCurrentOpen = false"
      @confirm="logoutCurrent"
    />
    <ConfirmDialog
      :open="logoutEverywhereOpen"
      title="Hammasi chiqsin"
      message="Barcha qurilmalardan chiqasiz."
      confirm-label="Hammasini chiqarish"
      danger
      @cancel="logoutEverywhereOpen = false"
      @confirm="logoutEverywhere"
    />
  </section>

  <section v-else>
    <div class="page-head">
      <div>
        <h1>Mening profilim</h1>
        <p class="sub">{{ workshopProfileSubtitle }}</p>
      </div>
      <button type="button" class="mp-button mp-button-outline text-danger" @click="logoutCurrent">
        Chiqib ketish
      </button>
    </div>

    <div v-if="auth.me?.password_reset_required" class="client-banner warn">
      <span class="font-extrabold">!</span>
      <span class="min-w-0">
        <b>Parolni o'zgartirish kerak</b>
        <span class="block"
          >Workspace yuzalarini ochishdan oldin vaqtinchalik parolni almashtiring.</span
        >
      </span>
    </div>

    <div class="client-tabs" role="tablist" aria-label="Profil bo'limlari">
      <button
        type="button"
        class="client-tab"
        :class="{ active: workshopProfileTab === 'profile' }"
        @click="workshopProfileTab = 'profile'"
      >
        Profil
      </button>
      <button
        type="button"
        class="client-tab"
        :class="{ active: workshopProfileTab === 'password' }"
        @click="workshopProfileTab = 'password'"
      >
        Parolni o'zgartirish
      </button>
      <button
        type="button"
        class="client-tab"
        :class="{ active: workshopProfileTab === 'sessions' }"
        @click="workshopProfileTab = 'sessions'"
      >
        Sessiyalar
      </button>
    </div>

    <section v-if="workshopProfileTab === 'profile'" class="grid max-w-[680px] gap-4">
      <div class="card">
        <div class="card-h">
          <h2>Ma'lumotlar</h2>
        </div>
        <div class="card-b">
          <div class="row-item">
            <div>
              <div class="nm">F.I.O</div>
            </div>
            <div class="meta">{{ accountLabel }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">Login</div>
            </div>
            <div class="meta">{{ auth.me?.login ?? '—' }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">Telefon</div>
            </div>
            <div class="meta">{{ auth.me?.phone ?? '—' }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">Egasi</div>
            </div>
            <div class="meta">
              <span
                class="mp-chip"
                :class="
                  auth.me?.is_owner ? 'bg-success-soft text-success' : 'bg-sunk text-ink-muted'
                "
              >
                <span class="mp-dot" aria-hidden="true"></span>
                {{ auth.me?.is_owner ? 'Ha · barcha ruxsatlar' : "Yo'q" }}
              </span>
            </div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">Scope</div>
            </div>
            <div class="meta">{{ scopeLabel }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">Status</div>
            </div>
            <div class="meta">{{ auth.me?.status ?? 'active' }}</div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-h">
          <h2>Ruxsatlar</h2>
        </div>
        <div class="card-b">
          <div v-if="auth.me?.is_owner" class="client-banner warn mb-0">
            <span class="font-extrabold">i</span>
            <span>Egasi sifatida barcha filialda barcha ruxsatga avtomatik egasiz.</span>
          </div>
          <p v-else-if="workshopGrantRows.length === 0" class="text-sm text-ink-soft">
            Sizga hali hech qanday ruxsat berilmagan — ustaxona egasiga murojaat qiling.
          </p>
          <div v-else class="divide-y divide-hairline">
            <div
              v-for="grant in workshopGrantRows"
              :key="grant.key"
              class="row-item"
              style="border-bottom: 0"
            >
              <div>
                <div class="nm">{{ grant.label }}</div>
                <small class="font-mono text-[11px] text-ink-muted">{{ grant.permission }}</small>
              </div>
              <div class="meta">{{ grant.branch }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section v-else-if="workshopProfileTab === 'password'" class="card max-w-[520px]">
      <div class="card-h">
        <h2>Parolni o'zgartirish</h2>
      </div>
      <form class="card-b grid gap-4" @submit.prevent="savePassword">
        <div class="client-banner warn mb-0">
          <span class="font-extrabold">i</span>
          <span>Parol o'zgartirilgandan keyin barcha boshqa sessiyalar yopiladi.</span>
        </div>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Joriy parol</span>
          <input
            v-model="currentPassword"
            class="mp-input"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Yangi parol</span>
          <input
            v-model="newPassword"
            class="mp-input"
            type="password"
            autocomplete="new-password"
            minlength="8"
            required
          />
          <span class="mt-1 block text-xs text-ink-muted"
            >Kamida 8 belgi · katta + kichik + raqam</span
          >
        </label>
        <div class="flex justify-end">
          <button type="submit" class="mp-button mp-button-primary" :disabled="isSaving">
            {{ isSaving ? 'Saqlanmoqda' : "O'zgartirish" }}
          </button>
        </div>
        <p v-if="message" class="text-sm font-bold text-success">{{ message }}</p>
        <p v-if="error" class="text-sm font-bold text-danger">{{ error }}</p>
      </form>
    </section>

    <section v-else class="card max-w-[680px]">
      <div class="card-h">
        <h2>Faol sessiyalar</h2>
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
          @click="logoutEverywhere"
        >
          Hammasi yopilsin
        </button>
      </div>
      <div class="card-b">
        <div v-if="sessions.length === 0" class="client-empty">
          <h3>Sessiya topilmadi</h3>
          <p>Joriy sessiya keyingi yangilashda ko'rinadi.</p>
        </div>
        <div v-else class="divide-y divide-hairline">
          <div v-for="session in sessions" :key="session.id" class="row-item">
            <div>
              <div class="nm">
                {{ deviceLabel(session) }}
                <span v-if="session.is_current" class="mp-chip bg-success-soft text-success ml-2">
                  <span class="mp-dot" aria-hidden="true"></span>
                  Joriy
                </span>
              </div>
              <small class="text-ink-muted">
                Oxirgi: {{ formatDate(session.last_used_at) }} · yaratildi
                {{ formatDate(session.created_at) }}
              </small>
            </div>
            <div class="meta">{{ session.is_current ? '—' : session.id.slice(0, 8) }}</div>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>
