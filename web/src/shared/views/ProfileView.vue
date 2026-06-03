<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/shared/api/client'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { formatDate } from '@/shared/formatters'
import { useAuthStore, type SessionResponse } from '@/shared/stores/auth'

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

const canChangePassword = computed(() => auth.me?.principal_type !== 'client')
const accountLabel = computed(() => auth.displayName)
const selectedBranchLabel = computed(() => {
  const option = branchOptions.value.find((row) => row.branch_id === preferredBranchId.value)
  return option ? `${option.workshop_name} · ${option.branch_name}` : 'No branch selected'
})
const scopeLabel = computed(() => {
  if (auth.me?.principal_type === 'workshop_user') {
    return auth.me.is_owner ? 'Workshop owner' : `${auth.me.grants.length} branch grants`
  }
  if (auth.me?.principal_type === 'platform_user') return 'Platform operations'
  return auth.me?.preferred_branch_id ? 'Preferred branch selected' : 'No preferred branch'
})

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
  message.value = 'Profile updated.'
}

async function savePassword() {
  error.value = null
  message.value = null
  isSaving.value = true
  try {
    await auth.changePassword(currentPassword.value, newPassword.value)
    currentPassword.value = ''
    newPassword.value = ''
    message.value = 'Password updated.'
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

onMounted(async () => {
  await loadSessions()
  await loadClientProfile()
})
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="font-serif text-3xl font-semibold text-ink">{{ config.roleLabel }} profile</h1>
      <p class="mt-2 max-w-2xl text-base text-ink-soft">
        Account identity, password state, and active sessions.
      </p>
    </div>

    <div
      v-if="auth.me?.password_reset_required"
      class="rounded-md border border-warning bg-warning-soft px-4 py-3 text-warning"
    >
      <div class="font-extrabold">Password change required</div>
      <p class="mt-1 text-sm">Update the temporary password before opening workspace routes.</p>
    </div>

    <div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold">Account</h2>
        <dl class="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Name</dt>
            <dd class="mt-1 text-base font-bold text-ink">{{ accountLabel }}</dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Role</dt>
            <dd class="mt-1 text-base font-bold text-ink">{{ config.roleLabel }}</dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Phone</dt>
            <dd class="mt-1 font-mono text-sm text-ink-soft">{{ auth.me?.phone ?? '—' }}</dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Scope</dt>
            <dd class="mt-1 text-base font-bold text-ink">{{ scopeLabel }}</dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Status</dt>
            <dd class="mt-1">
              <span class="mp-chip bg-success-soft text-success">
                <span class="mp-dot" aria-hidden="true"></span>
                {{ auth.me?.status ?? 'active' }}
              </span>
            </dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Session</dt>
            <dd class="mt-1 font-mono text-sm text-ink-soft">{{ auth.me?.session_id }}</dd>
          </div>
        </dl>
      </section>

      <aside class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold">Session actions</h2>
        <div class="mt-4 space-y-3">
          <button type="button" class="mp-button mp-button-outline w-full" @click="logoutCurrent">
            Log out
          </button>
          <button
            type="button"
            class="mp-button mp-button-outline w-full"
            @click="logoutEverywhere"
          >
            Log out everywhere
          </button>
        </div>
      </aside>
    </div>

    <section v-if="canChangePassword" class="mp-surface p-5">
      <h2 class="font-serif text-xl font-semibold">Password</h2>
      <form class="mt-5 grid gap-4 md:grid-cols-[1fr_1fr_auto]" @submit.prevent="savePassword">
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Current password</span>
          <input
            v-model="currentPassword"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">New password</span>
          <input
            v-model="newPassword"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="password"
            autocomplete="new-password"
            required
          />
        </label>
        <button type="submit" class="mp-button mp-button-primary self-end" :disabled="isSaving">
          {{ isSaving ? 'Saving' : 'Save' }}
        </button>
      </form>
      <p v-if="message" class="mt-3 text-sm font-bold text-success">{{ message }}</p>
      <p v-if="error" class="mt-3 text-sm font-bold text-danger">{{ error }}</p>
    </section>

    <section v-else class="mp-surface p-5">
      <h2 class="font-serif text-xl font-semibold">Client profile</h2>
      <form class="mt-5 grid gap-4 md:grid-cols-[1fr_1fr_auto]" @submit.prevent="saveClientProfile">
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Name</span>
          <input
            v-model="clientName"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="text"
            autocomplete="name"
            required
          />
        </label>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Preferred branch</span>
          <div class="flex gap-2">
            <input
              class="min-h-11 w-full rounded-md border border-hairline-strong bg-sunk px-3 text-base text-ink"
              :value="selectedBranchLabel"
              readonly
            />
            <button
              type="button"
              class="mp-button mp-button-outline"
              @click="preferredBranchId = null"
            >
              Clear
            </button>
          </div>
        </label>
        <button type="submit" class="mp-button mp-button-primary self-end">Save</button>
      </form>
      <div class="mt-4 flex flex-wrap gap-2">
        <button
          v-for="option in branchOptions"
          :key="option.branch_id"
          type="button"
          class="mp-button min-h-9 px-3 text-xs"
          :class="
            option.branch_id === preferredBranchId ? 'mp-button-primary' : 'mp-button-outline'
          "
          @click="preferredBranchId = option.branch_id"
        >
          {{ option.workshop_name }} · {{ option.branch_name }}
        </button>
      </div>
    </section>

    <section class="mp-surface overflow-hidden">
      <div class="border-b border-hairline px-5 py-4">
        <h2 class="font-serif text-xl font-semibold">Sessions</h2>
      </div>
      <div class="divide-y divide-hairline">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="grid gap-2 px-5 py-4 sm:grid-cols-[1fr_auto]"
        >
          <div>
            <div class="font-mono text-sm text-ink">{{ session.id }}</div>
            <div class="mt-1 text-sm text-ink-soft">
              Created {{ formatDate(session.created_at) }} · last used
              {{ formatDate(session.last_used_at) }}
            </div>
          </div>
          <span
            class="mp-chip self-start"
            :class="session.is_current ? 'bg-success-soft text-success' : 'bg-sunk text-ink-muted'"
          >
            <span class="mp-dot" aria-hidden="true"></span>
            {{ session.is_current ? 'current' : 'active' }}
          </span>
        </div>
      </div>
    </section>
  </section>
</template>
