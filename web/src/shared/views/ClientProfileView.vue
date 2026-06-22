<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { apiTraceId } from '@/shared/api/client'
import { clientErrorLabel, formatPhone } from '@/shared/app/clientUi'
import { formatDate } from '@/shared/formatters'
import Icon from '@/shared/components/AppIcon.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useSessions } from '@/shared/composables/useSessions'
import { useAuthStore } from '@/shared/stores/auth'
import { useClientProfileStore, type ClientProfile } from '@/shared/stores/clientProfile'
import { useOrdersStore } from '@/shared/stores/orders'

const auth = useAuthStore()
const orders = useOrdersStore()
const profileStore = useClientProfileStore()
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
  const ok = await patchProfile({ name: clientName.value }, 'Profil yangilandi.')
  if (ok) editingClientName.value = false
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
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            @click="logoutCurrentOpen = true"
          >
            Chiqib ketish
          </button>
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
                  class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                  :disabled="isSaving"
                >
                  Saqlash
                </button>
              </form>
              <template v-else>
                <span class="font-bold text-ink">{{ auth.displayName }}</span>
                <button
                  type="button"
                  class="mp-action-icon-button"
                  aria-label="Ismni o'zgartirish"
                  title="Ismni o'zgartirish"
                  @click="editingClientName = true"
                >
                  <Icon name="pencil" class="size-[18px]" />
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
            class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
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
              <div class="flex min-w-0 items-center gap-3">
                <span
                  class="grid size-9 shrink-0 place-items-center rounded-lg bg-sunk text-ink-soft"
                  :class="session.is_current ? 'bg-accent-soft text-accent' : ''"
                  aria-hidden="true"
                >
                  <Icon name="monitor" />
                </span>
                <div class="min-w-0">
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
              </div>
              <button
                v-if="!session.is_current"
                type="button"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
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
