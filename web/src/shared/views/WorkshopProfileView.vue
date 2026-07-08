<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { clientErrorLabel } from '@/shared/app/clientUi'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { formatDate } from '@/shared/formatters'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useToast } from '@/shared/composables/useToast'
import { useSessions } from '@/shared/composables/useSessions'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

const config = useRoleConfig()
const auth = useAuthStore()
const toast = useToast()
const workshop = useWorkshopStore()
const {
  sessions,
  logoutCurrentOpen,
  logoutEverywhereOpen,
  loadSessions,
  deviceLabel,
  revokeRow,
  logoutCurrent,
  logoutEverywhere,
} = useSessions()

const workshopProfileTab = ref<'profile' | 'password' | 'sessions'>('profile')
const currentPassword = ref('')
const newPassword = ref('')
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const isSaving = ref(false)

const accountLabel = computed(() => auth.displayName)
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

async function savePassword() {
  error.value = null
  message.value = null
  isSaving.value = true
  try {
    await auth.changePassword(currentPassword.value, newPassword.value)
    currentPassword.value = ''
    newPassword.value = ''
    toast.success("Parol o'zgartirildi.")
    await loadSessions()
  } catch {
    error.value = auth.lastError ?? 'password_change_failed'
  } finally {
    isSaving.value = false
  }
}

onMounted(async () => {
  if (auth.me?.password_reset_required) workshopProfileTab.value = 'password'
  await Promise.all([loadSessions(), workshop.loadSettings()])
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Mening profilim</h1>
        <p class="sub">{{ workshopProfileSubtitle }}</p>
      </div>
      <button
        type="button"
        class="mp-button mp-button-outline text-danger"
        @click="logoutCurrentOpen = true"
      >
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
        <p v-if="error" class="text-sm font-bold text-danger">{{ clientErrorLabel(error) }}</p>
      </form>
    </section>

    <section v-else class="card max-w-[680px]">
      <div class="card-h">
        <h2>Faol sessiyalar</h2>
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
          @click="logoutEverywhereOpen = true"
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
            <button
              v-if="!session.is_current"
              type="button"
              class="mp-button mp-button-outline min-h-8 px-3 text-xs text-danger"
              @click="revokeRow(session.id)"
            >
              Yopish
            </button>
            <div v-else class="meta">—</div>
          </div>
        </div>
      </div>
    </section>

    <ConfirmDialog
      :open="logoutCurrentOpen"
      title="Chiqib ketish"
      message="Ustaxona kabinetidan chiqasiz."
      confirm-label="Chiqish"
      cancel-label="Bekor qilish"
      danger
      @cancel="logoutCurrentOpen = false"
      @confirm="logoutCurrent"
    />
    <ConfirmDialog
      :open="logoutEverywhereOpen"
      title="Hammasi chiqsin"
      message="Barcha qurilmalardan chiqasiz."
      confirm-label="Hammasini chiqarish"
      cancel-label="Bekor qilish"
      danger
      @cancel="logoutEverywhereOpen = false"
      @confirm="logoutEverywhere"
    />
  </section>
</template>
