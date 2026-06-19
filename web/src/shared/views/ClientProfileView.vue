<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { clientErrorLabel, formatPhone } from '@/shared/app/clientUi'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { formatDate } from '@/shared/formatters'
import Icon from '@/shared/components/AppIcon.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useSessions } from '@/shared/composables/useSessions'
import { useAuthStore } from '@/shared/stores/auth'
import { useClientProfileStore, type ClientProfile } from '@/shared/stores/clientProfile'
import { useOrdersStore } from '@/shared/stores/orders'

const config = useRoleConfig()
const auth = useAuthStore()
const orders = useOrdersStore()
const profileStore = useClientProfileStore()
const router = useRouter()
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
const preferredBranchId = ref<string | null>(null)
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const profileLoading = ref(false)
const profileError = ref<string | null>(null)
const profileTraceId = ref<string | null>(null)
const isSaving = ref(false)
const editingClientName = ref(false)

// temporarily_closed branches stay SELECTABLE (CB-77); the meta flags why it's closed.
const branchChoiceOptions = computed<ChoiceOption[]>(() =>
  profileStore.branchOptions.map((option) => ({
    value: option.branch_id,
    label: `${option.workshop_name} · ${option.branch_name}`,
    meta:
      option.status === 'temporarily_closed'
        ? (option.closed_reason ?? 'vaqtincha yopiq')
        : undefined,
  })),
)
// The saved preferred branch no longer appears in branch-options → surface a
// stale-preference state instead of a silent placeholder (CB-77).
const preferredBranchMissing = computed(
  () =>
    !!preferredBranchId.value &&
    !profileStore.branchOptions.some((option) => option.branch_id === preferredBranchId.value),
)

function goBack() {
  if (window.history.state?.back) router.back()
  else router.push(config.homePath)
}

// Send only the edited field (CB-78): name form PATCHes {name}, branch row PATCHes
// {preferred_branch_id}; the backend treats an absent key as unchanged.
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
  const ok = await patchProfile({ name: clientName.value }, 'Profil yangilandi.')
  if (ok) editingClientName.value = false
}

async function savePreferredBranch() {
  await patchProfile({ preferred_branch_id: preferredBranchId.value }, 'Afzal filial saqlandi.')
}

async function reloadProfile() {
  profileLoading.value = true
  profileError.value = null
  profileTraceId.value = null
  try {
    const [profile] = await Promise.all([
      profileStore.load(),
      loadSessions(),
      orders.loadClientOrders(),
    ])
    clientName.value = profile.name
    preferredBranchId.value = profile.preferred_branch_id
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
      <h3>Profilni yuklab bo'lmadi</h3>
      <p>Ulanishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.</p>
      <p class="client-trace">trace_id: {{ profileTraceId ?? 'unavailable' }}</p>
      <button type="button" class="mp-button mp-button-outline mt-4" @click="reloadProfile">
        Qayta urinish
      </button>
    </div>

    <div v-else class="grid max-w-[760px] gap-5">
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
              <SearchCombobox
                v-model="preferredBranchId"
                class="w-full sm:max-w-md"
                label="Tanlangan"
                :options="branchChoiceOptions"
                placeholder="Filialni qidiring"
              />
              <p v-if="preferredBranchMissing" class="text-sm font-bold text-warning sm:text-right">
                Avvalgi filial endi mavjud emas — boshqasini tanlang yoki tozalang.
              </p>
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
                  @click="savePreferredBranch"
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
          <p v-if="error" class="mt-3 text-sm font-bold text-danger">
            {{ clientErrorLabel(error) }}
          </p>
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
              <button
                v-if="!session.is_current"
                type="button"
                class="mp-button mp-button-outline min-h-8 px-3 text-xs text-danger"
                @click="revokeRow(session.id)"
              >
                Yopish
              </button>
              <span v-else class="font-mono text-xs text-ink-muted">—</span>
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
</template>
