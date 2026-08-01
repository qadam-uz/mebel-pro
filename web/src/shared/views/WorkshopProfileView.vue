<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { clientErrorLabel } from '@/shared/app/clientUi'
import { roleMessageKey, useRoleConfig } from '@/shared/app/roleConfig'
import { permissionLabel, workshopTenantName } from '@/shared/app/workshopUi'
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
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const {
  sessions,
  logoutEverywhereOpen,
  loggingOut,
  loadSessions,
  deviceLabel,
  revokeRow,
  logoutEverywhere,
} = useSessions()

const workshopProfileTab = ref<'profile' | 'password' | 'sessions'>('profile')
const currentPassword = ref('')
const newPassword = ref('')
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const isSaving = ref(false)

const accountLabel = computed(() => auth.displayName)
// The API's own words never reach the screen (QAD-182): `active` is a value in
// a column, «Faol» is what a person reads.
const accountStatusLabel = computed(() => {
  const status = auth.me?.status ?? 'active'
  if (status === 'active') return t('workshopAdmin.staff.statusActive')
  if (status === 'blocked') return t('workshopAdmin.staff.statusBlocked')
  return status
})
const workshopProfileSubtitle = computed(() =>
  t('workshopAdmin.profile.subtitle', {
    name: auth.displayName,
    role: auth.me?.is_owner
      ? t('workshopAdmin.profile.roleOwner')
      : t('workshopAdmin.profile.roleStaff'),
    tenant:
      workshopTenantName(workshop.settings?.name, auth.me?.workshop_name) ??
      t(roleMessageKey(config.role, 'tenant')),
  }),
)
const workshopGrantRows = computed(() => {
  if (auth.me?.principal_type !== 'workshop_user' || auth.me.is_owner) return []
  return auth.me.grants.map((grant) => ({
    key: `${grant.permission}-${grant.branch_id}`,
    permission: grant.permission,
    // One label source, in `workshopUi`. This view used to keep a private copy,
    // which went stale the moment a permission was renamed — `view_dashboard`
    // became `view_orders` (QAD-166) and the Ruxsatlar panel printed the raw code.
    label: permissionLabel(grant.permission),
    branch:
      workshop.branches.find((branch) => branch.id === grant.branch_id)?.name ??
      grant.branch_id.slice(0, 8),
  }))
})

async function savePassword() {
  error.value = null
  message.value = null
  isSaving.value = true
  const wasForced = auth.me?.password_reset_required === true
  try {
    await auth.changePassword(currentPassword.value, newPassword.value)
    currentPassword.value = ''
    newPassword.value = ''
    toast.success(t('workshopAdmin.profile.passwordChanged'))
    // First-run continuation (docs/ref/features/onboarding.md): the forced
    // change was step 1 of the owner's setup — land them on the home checklist.
    if (wasForced && auth.me?.principal_type === 'workshop_user' && auth.me.is_owner) {
      void router.push(config.homePath)
      return
    }
    await loadSessions()
  } catch {
    error.value = auth.lastError ?? 'password_change_failed'
  } finally {
    isSaving.value = false
  }
}

onMounted(async () => {
  // The topbar account menu deep-links here (QAD-182); a forced password change
  // still wins, because that is the only thing the user can act on.
  if (route.query.tab === 'sessions') workshopProfileTab.value = 'sessions'
  if (auth.me?.password_reset_required) workshopProfileTab.value = 'password'
  // Branch context, not the workshop settings row: this page is open to every
  // staff member and `/workshop/settings` is owner-only, so the old call 403'd
  // for all ten non-owner principals. The name now rides on `me`; the context
  // is what turns each grant's branch id into a branch name (QAD-168).
  await Promise.all([loadSessions(), workshop.loadBranchContext().catch(() => undefined)])
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>{{ $t('workshopAdmin.profile.title') }}</h1>
        <p class="sub">{{ workshopProfileSubtitle }}</p>
      </div>
    </div>

    <div v-if="auth.me?.password_reset_required" class="client-banner warn">
      <span class="font-extrabold">!</span>
      <span class="min-w-0">
        <b>{{ $t('workshopAdmin.profile.passwordRequiredTitle') }}</b>
        <span class="block">{{ $t('workshopAdmin.profile.passwordRequiredBody') }}</span>
      </span>
    </div>

    <div class="client-tabs" role="tablist" :aria-label="$t('workshopAdmin.profile.tabsLabel')">
      <button
        type="button"
        class="client-tab"
        :class="{ active: workshopProfileTab === 'profile' }"
        @click="workshopProfileTab = 'profile'"
      >
        {{ $t('workshopAdmin.profile.tabProfile') }}
      </button>
      <button
        type="button"
        class="client-tab"
        :class="{ active: workshopProfileTab === 'password' }"
        @click="workshopProfileTab = 'password'"
      >
        {{ $t('workshopAdmin.profile.tabPassword') }}
      </button>
      <button
        type="button"
        class="client-tab"
        :class="{ active: workshopProfileTab === 'sessions' }"
        @click="workshopProfileTab = 'sessions'"
      >
        {{ $t('workshopAdmin.profile.tabSessions') }}
      </button>
    </div>

    <section v-if="workshopProfileTab === 'profile'" class="grid max-w-[680px] gap-4">
      <div class="card">
        <div class="card-h">
          <h2>{{ $t('workshopAdmin.profile.infoTitle') }}</h2>
        </div>
        <div class="card-b">
          <div class="row-item">
            <div>
              <div class="nm">{{ $t('workshopAdmin.profile.fullName') }}</div>
            </div>
            <div class="meta">{{ accountLabel }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">{{ $t('workshopAdmin.profile.login') }}</div>
            </div>
            <div class="meta">{{ auth.me?.login ?? '—' }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">{{ $t('workshopAdmin.profile.phone') }}</div>
            </div>
            <div class="meta">{{ auth.me?.phone ?? '—' }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">{{ $t('workshopAdmin.profile.ownerRow') }}</div>
            </div>
            <div class="meta">
              <span
                class="mp-chip"
                :class="
                  auth.me?.is_owner ? 'bg-success-soft text-success' : 'bg-sunk text-ink-muted'
                "
              >
                <span class="mp-dot" aria-hidden="true"></span>
                {{
                  auth.me?.is_owner
                    ? $t('workshopAdmin.profile.ownerYes')
                    : $t('workshopAdmin.profile.ownerNo')
                }}
              </span>
            </div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">{{ $t('workshopAdmin.profile.statusRow') }}</div>
            </div>
            <div class="meta">{{ accountStatusLabel }}</div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-h">
          <h2>{{ $t('workshopAdmin.profile.grantsTitle') }}</h2>
        </div>
        <div class="card-b">
          <div v-if="auth.me?.is_owner" class="client-banner warn mb-0">
            <span class="font-extrabold">i</span>
            <span>{{ $t('workshopAdmin.profile.ownerGrantsNote') }}</span>
          </div>
          <p v-else-if="workshopGrantRows.length === 0" class="text-sm text-ink-soft">
            {{ $t('workshopAdmin.profile.noGrants') }}
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
        <h2>{{ $t('workshopAdmin.profile.passwordTitle') }}</h2>
      </div>
      <form class="card-b grid gap-4" @submit.prevent="savePassword">
        <div class="client-banner warn mb-0">
          <span class="font-extrabold">i</span>
          <span>{{ $t('workshopAdmin.profile.passwordNote') }}</span>
        </div>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">
            {{ $t('workshopAdmin.profile.currentPassword') }}
          </span>
          <input
            v-model="currentPassword"
            class="mp-input"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">
            {{ $t('workshopAdmin.profile.newPassword') }}
          </span>
          <input
            v-model="newPassword"
            class="mp-input"
            type="password"
            autocomplete="new-password"
            minlength="8"
            required
          />
          <span class="mt-1 block text-xs text-ink-muted">
            {{ $t('workshopAdmin.profile.passwordHint') }}
          </span>
        </label>
        <div class="flex justify-end">
          <button type="submit" class="mp-button mp-button-primary" :disabled="isSaving">
            {{
              isSaving
                ? $t('workshopAdmin.action.saving')
                : $t('workshopAdmin.profile.changeSubmit')
            }}
          </button>
        </div>
        <p v-if="message" class="text-sm font-bold text-success">{{ message }}</p>
        <p v-if="error" class="text-sm font-bold text-danger">{{ clientErrorLabel(error) }}</p>
      </form>
    </section>

    <section v-else class="card max-w-[680px]">
      <div class="card-h">
        <h2>{{ $t('workshopAdmin.profile.sessionsTitle') }}</h2>
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
          @click="logoutEverywhereOpen = true"
        >
          {{ $t('workshopAdmin.profile.revokeAll') }}
        </button>
      </div>
      <div class="card-b">
        <div v-if="sessions.length === 0" class="client-empty">
          <h3>{{ $t('workshopAdmin.profile.sessionsEmptyTitle') }}</h3>
          <p>{{ $t('workshopAdmin.profile.sessionsEmptyBody') }}</p>
        </div>
        <div v-else class="divide-y divide-hairline">
          <div v-for="session in sessions" :key="session.id" class="row-item">
            <div>
              <div class="nm">
                {{ deviceLabel(session) }}
                <span v-if="session.is_current" class="mp-chip bg-success-soft text-success ml-2">
                  <span class="mp-dot" aria-hidden="true"></span>
                  {{ $t('workshopAdmin.profile.currentSession') }}
                </span>
              </div>
              <small class="text-ink-muted">
                {{
                  $t('workshopAdmin.profile.sessionMeta', {
                    last: formatDate(session.last_used_at),
                    created: formatDate(session.created_at),
                  })
                }}
              </small>
            </div>
            <button
              v-if="!session.is_current"
              type="button"
              class="mp-button mp-button-outline min-h-8 px-3 text-xs text-danger"
              @click="revokeRow(session.id)"
            >
              {{ $t('workshopAdmin.action.close') }}
            </button>
            <div v-else class="meta">—</div>
          </div>
        </div>
      </div>
    </section>

    <ConfirmDialog
      :open="logoutEverywhereOpen"
      :title="$t('workshopAdmin.profile.logoutAllTitle')"
      :message="$t('workshopAdmin.profile.logoutAllMessage')"
      :confirm-label="$t('workshopAdmin.profile.logoutAllConfirm')"
      :cancel-label="$t('workshopAdmin.action.cancelFull')"
      :busy-label="$t('workshopAdmin.profile.logoutAllBusy')"
      danger
      :busy="loggingOut"
      @cancel="logoutEverywhereOpen = false"
      @confirm="logoutEverywhere"
    />
  </section>
</template>
