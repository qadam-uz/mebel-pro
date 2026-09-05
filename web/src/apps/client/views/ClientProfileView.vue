<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { clientErrorLabel, formatPhone } from '@/shared/app/clientUi'
import { traceLine } from '@/shared/app/errorTrace'
import { useRolePath } from '@/shared/app/paths'
import { formatDate } from '@/shared/formatters'
import Icon from '@/shared/components/AppIcon.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import LocaleSwitcher from '@/shared/components/LocaleSwitcher.vue'
import { useSessions } from '@/shared/composables/useSessions'
import { useAuthStore } from '@/shared/stores/auth'
import { useClientProfileStore, type ClientProfile } from '@/shared/stores/clientProfile'
import { useNotificationsStore } from '@/shared/stores/notifications'

const { t } = useI18n()
const auth = useAuthStore()
const notifications = useNotificationsStore()
const profileStore = useClientProfileStore()
const rolePath = useRolePath()
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

const clientName = ref('')
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const profileLoading = ref(false)
const profileError = ref<string | null>(null)
const profileTraceId = ref<string | null>(null)
const isSaving = ref(false)
const editingClientName = ref(false)

// Send only the edited field (CB-78): the name form PATCHes {name}; the backend
// treats an absent key as unchanged.
async function patchProfile(payload: Partial<ClientProfile>, successMessage: string) {
  error.value = null
  message.value = null
  isSaving.value = true
  try {
    const updated = await profileStore.patch(payload)
    if (auth.me) {
      auth.me = { ...auth.me, name: updated.name, preferred_branch_id: updated.preferred_branch_id }
    }
    message.value = successMessage
    return true
  } catch {
    error.value = 'profile_update_failed'
    return false
  } finally {
    isSaving.value = false
  }
}

async function saveClientName() {
  if (clientName.value.trim().length === 0) {
    error.value = 'invalid_name'
    return
  }
  const ok = await patchProfile({ name: clientName.value }, t('client.profile.updated'))
  if (ok) editingClientName.value = false
}

async function reloadProfile() {
  profileLoading.value = true
  profileError.value = null
  profileTraceId.value = null
  try {
    const [profile] = await Promise.all([profileStore.load(), loadSessions()])
    clientName.value = profile.name
  } catch (errorValue) {
    profileError.value = 'profile_load_failed'
    profileTraceId.value = apiTraceId(errorValue)
  } finally {
    profileLoading.value = false
  }
}

onMounted(reloadProfile)
</script>

<template>
  <section>
    <div v-if="profileLoading" class="grid max-w-[760px] gap-5" aria-live="polite">
      <div class="client-card p-5">
        <div class="client-skeleton h-4 w-1/4"></div>
        <div class="client-skeleton mt-3 h-10 w-2/3"></div>
        <div class="client-skeleton mt-4 h-10 w-1/2"></div>
      </div>
      <div class="client-card p-5"><div class="client-skeleton h-20 w-full"></div></div>
    </div>

    <div v-else-if="profileError" class="client-error">
      <div class="client-error-icon"><Icon name="alert" /></div>
      <h3>{{ $t('client.profile.loadFailedTitle') }}</h3>
      <p>{{ $t('client.profile.loadFailedBody') }}</p>
      <p class="client-trace">{{ traceLine(profileTraceId) }}</p>
      <button type="button" class="mp-button mp-button-outline mt-4" @click="reloadProfile">
        {{ $t('client.common.retry') }}
      </button>
    </div>

    <div v-else class="grid max-w-[760px] gap-3 md:gap-5">
      <!-- §5.3: the phone header's 56px row has no width for the locale
           switcher or the bell's twin, so both live here. The desktop header
           keeps them too — the duplication is deliberate. -->
      <!-- The switcher renders its own «Til» label, so the card adds none. -->
      <section class="client-card p-3.5 md:p-5">
        <LocaleSwitcher variant="segmented" />
      </section>

      <RouterLink
        :to="rolePath('/c/notifications')"
        class="client-card client-card-link flex items-center gap-3 p-3.5 no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 md:p-5"
      >
        <span
          class="grid size-[38px] shrink-0 place-items-center rounded-[11px] bg-sunk text-ink-soft"
          aria-hidden="true"
        >
          <Icon name="inbox" class="size-5" />
        </span>
        <span class="flex-1 text-[15px] font-semibold text-ink">
          {{ $t('client.profile.notifications') }}
        </span>
        <span
          v-if="notifications.unread > 0"
          class="grid h-[22px] min-w-[22px] place-items-center rounded-full bg-accent px-1.5 text-[12.5px] font-semibold text-on-accent"
        >
          {{ notifications.unread > 9 ? '9+' : notifications.unread }}
        </span>
        <Icon name="chevron-right" class="size-[18px] shrink-0 text-ink-muted" />
      </RouterLink>

      <section class="client-card">
        <div class="client-card-h">
          <!-- §2, one title per screen: on phones the compact header already
               says «Profil», so the card's own heading is read but not shown.
               The head row stays — it carries «Chiqib ketish». -->
          <h2 class="max-md:sr-only">{{ $t('client.profile.title') }}</h2>
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            @click="logoutCurrentOpen = true"
          >
            {{ $t('client.profile.logout') }}
          </button>
        </div>
        <div class="client-card-b">
          <div class="client-row-item">
            <div>
              <div class="client-row-name">{{ $t('client.common.name') }}</div>
              <div class="text-sm text-ink-muted">{{ $t('client.profile.nameHint') }}</div>
            </div>
            <div class="flex items-center gap-2">
              <form
                v-if="editingClientName"
                class="flex items-center gap-2"
                @submit.prevent="saveClientName"
              >
                <input
                  v-model="clientName"
                  class="mp-input min-w-52"
                  autocomplete="name"
                  required
                />
                <button
                  type="submit"
                  class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                  :disabled="isSaving"
                >
                  {{ $t('client.common.save') }}
                </button>
              </form>
              <template v-else>
                <span class="font-bold text-ink">{{ auth.displayName }}</span>
                <button
                  type="button"
                  class="mp-action-icon-button"
                  :aria-label="$t('client.profile.editName')"
                  :title="$t('client.profile.editName')"
                  @click="editingClientName = true"
                >
                  <Icon name="pencil" class="size-[18px]" />
                </button>
              </template>
            </div>
          </div>

          <div class="client-row-item">
            <div>
              <div class="client-row-name">{{ $t('client.common.phone') }}</div>
              <div class="text-sm text-ink-muted">{{ $t('client.profile.phoneHint') }}</div>
            </div>
            <div class="text-sm text-ink">{{ formatPhone(auth.me?.phone) }}</div>
          </div>

          <p v-if="message" class="mt-3 text-sm font-bold text-success">{{ message }}</p>
          <p v-if="error" class="mt-3 text-sm font-bold text-danger">
            {{ clientErrorLabel(error) }}
          </p>
        </div>
      </section>

      <section class="client-card">
        <div class="client-card-h">
          <h2>{{ $t('client.profile.sessions') }}</h2>
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
            @click="logoutEverywhereOpen = true"
          >
            {{ $t('client.profile.logoutEverywhere') }}
          </button>
        </div>
        <div class="client-card-b">
          <div v-if="sessions.length === 0" class="text-sm text-ink-muted">
            {{ $t('client.profile.sessionsEmpty') }}
          </div>
          <template v-else>
            <div v-for="session in sessions" :key="session.id" class="client-row-item">
              <div class="flex min-w-0 items-center gap-3">
                <span
                  class="grid size-9 shrink-0 place-items-center rounded-lg bg-sunk text-ink-soft"
                  :class="session.is_current ? 'bg-accent-soft text-accent-strong' : ''"
                  aria-hidden="true"
                >
                  <Icon name="monitor" />
                </span>
                <div class="min-w-0">
                  <div class="client-row-name">
                    {{ deviceLabel(session) }}
                    <span v-if="session.is_current" class="client-pill client-pill-ready ml-2">{{
                      $t('client.profile.currentSession')
                    }}</span>
                  </div>
                  <div class="text-sm text-ink-muted">
                    {{ formatDate(session.last_used_at) }} · {{ session.id.slice(0, 8) }}
                  </div>
                </div>
              </div>
              <button
                v-if="!session.is_current"
                type="button"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
                @click="revokeRow(session.id)"
              >
                {{ $t('client.profile.revokeSession') }}
              </button>
              <span v-else class="text-xs text-ink-muted">—</span>
            </div>
          </template>
        </div>
      </section>
    </div>

    <ConfirmDialog
      :open="logoutCurrentOpen"
      :title="$t('client.profile.logout')"
      :message="$t('client.profile.logoutMessage')"
      :confirm-label="$t('client.profile.logoutConfirm')"
      :cancel-label="$t('client.common.cancel')"
      danger
      @cancel="logoutCurrentOpen = false"
      @confirm="logoutCurrent"
    />
    <ConfirmDialog
      :open="logoutEverywhereOpen"
      :title="$t('client.profile.logoutEverywhereTitle')"
      :message="$t('client.profile.logoutEverywhereMessage')"
      :confirm-label="$t('client.profile.logoutEverywhere')"
      :cancel-label="$t('client.common.cancel')"
      danger
      @cancel="logoutEverywhereOpen = false"
      @confirm="logoutEverywhere"
    />
  </section>
</template>
