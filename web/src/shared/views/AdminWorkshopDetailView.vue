<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import {
  adminDate,
  adminErrorMessage,
  branchStatusLabel,
  workshopStatusLabel,
  workshopStatusTone,
} from '@/shared/app/adminUi'
import { apiErrorCode } from '@/shared/api/client'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import AdminModalCloseIcon from '@/shared/components/AdminModalCloseIcon.vue'
import AdminSecretModal from '@/shared/components/AdminSecretModal.vue'
import AppTabs from '@/shared/components/AppTabs.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore } from '@/shared/stores/admin'

const route = useRoute()
const admin = useAdminStore()
const rolePath = useRolePath()
const toast = useToast()
const workshopId = String(route.params.workshop_id)
const tab = ref<'profile' | 'branches' | 'users'>('profile')
const blockModalOpen = ref(false)
const blockPanel = ref<HTMLElement | null>(null)
const blockTrap = useFocusTrap(blockPanel, blockModalOpen, () => (blockModalOpen.value = false))
const reason = ref('')
const acting = ref(false)
const actionError = ref<string | null>(null)
const blockFieldErrors = reactive<FieldErrors<'reason'>>({})
const tabOptions = [
  { value: 'profile', label: 'Profil' },
  { value: 'branches', label: 'Filiallar' },
  { value: 'users', label: 'Xodimlar' },
]

const canBlock = computed(() => admin.detail?.workshop.status === 'active')
const canUnblock = computed(() => admin.detail?.workshop.status === 'blocked')

async function block() {
  clearFieldErrors(blockFieldErrors)
  if (!canBlock.value || !admin.detail) return
  if (!reason.value.trim()) {
    blockFieldErrors.reason = "Bu maydonni to'ldiring."
    focusFirstFieldError(blockFieldErrors, ['reason'], { reason: 'block-reason' })
    return
  }
  acting.value = true
  actionError.value = null
  try {
    await admin.blockWorkshop(admin.detail.workshop.id, reason.value)
    blockModalOpen.value = false
    reason.value = ''
    toast.success('Ustaxona bloklandi')
  } catch (error) {
    Object.assign(
      blockFieldErrors,
      fieldErrorsFromApi<'reason'>(error, { reason_required: 'reason' }),
    )
    if (blockFieldErrors.reason) {
      focusFirstFieldError(blockFieldErrors, ['reason'], { reason: 'block-reason' })
    } else {
      actionError.value = 'workshop_block_failed'
      toast.danger(adminErrorMessage(apiErrorCode(error), "Ustaxonani bloklab bo'lmadi."))
    }
  } finally {
    acting.value = false
  }
}

async function unblock() {
  if (!canUnblock.value || !admin.detail) return
  acting.value = true
  actionError.value = null
  try {
    await admin.unblockWorkshop(admin.detail.workshop.id)
    toast.success('Ustaxona blokdan chiqarildi')
  } catch (error) {
    actionError.value = 'workshop_unblock_failed'
    toast.danger(adminErrorMessage(apiErrorCode(error), "Ustaxonani blokdan chiqarib bo'lmadi."))
  } finally {
    acting.value = false
  }
}

function openBlockModal() {
  clearFieldErrors(blockFieldErrors)
  blockModalOpen.value = true
}

// Operator-side recovery for a locked-out owner: confirm → one-time temp
// password reveal (AB-03 — the secret never outlives the modal / session).
const resetConfirmOpen = ref(false)
const resetting = ref(false)
const secretOpen = ref(false)

const secretRows = computed(() => {
  const secret = admin.lastOwnerSecret
  if (!secret) return []
  return [
    { label: 'Login', value: secret.owner.login },
    { label: 'Vaqtinchalik parol', value: secret.temp_password },
  ]
})

async function confirmOwnerReset() {
  if (!admin.detail) return
  resetting.value = true
  try {
    await admin.resetWorkshopOwnerPassword(admin.detail.workshop.id)
    resetConfirmOpen.value = false
    secretOpen.value = true
  } catch (error) {
    resetConfirmOpen.value = false
    toast.danger(adminErrorMessage(apiErrorCode(error), "Rahbarning parolini tiklab bo'lmadi."))
  } finally {
    resetting.value = false
  }
}

function closeSecret() {
  secretOpen.value = false
  admin.clearSecrets()
}

onBeforeUnmount(() => admin.clearSecrets())

onMounted(() => admin.loadWorkshop(workshopId))
</script>

<template>
  <section v-if="admin.loading" class="admin-card p-5" aria-live="polite">
    <div class="admin-skeleton-line w-3/5"></div>
    <div class="admin-skeleton-line w-4/5"></div>
    <div class="admin-skeleton-line w-2/5"></div>
  </section>

  <div v-else-if="admin.error">
    <RouterLink :to="rolePath('/admin/workshops')" class="admin-back">← Ustaxonalar</RouterLink>
    <AdminErrorState
      :code="admin.error"
      :trace-id="admin.traceId"
      title="Ustaxona yuklanmadi"
      @retry="admin.loadWorkshop(workshopId)"
    />
  </div>

  <section v-else-if="admin.detail">
    <RouterLink :to="rolePath('/admin/workshops')" class="admin-back">← Ustaxonalar</RouterLink>

    <div class="admin-page-head">
      <div>
        <h1>{{ admin.detail.workshop.name }}</h1>
        <p class="date">{{ adminDate(admin.detail.workshop.created_at) }}</p>
      </div>
      <div class="admin-page-tools">
        <span class="admin-pill" :class="workshopStatusTone(admin.detail.workshop.status)">
          {{ workshopStatusLabel(admin.detail.workshop.status) }}
        </span>
        <button
          v-if="admin.detail.workshop.status === 'active'"
          type="button"
          class="mp-button mp-button-outline text-danger"
          :aria-label="`${admin.detail.workshop.name} ustaxonasini bloklash`"
          @click="openBlockModal"
        >
          Ustaxonani bloklash
        </button>
        <button
          v-else
          type="button"
          class="mp-button mp-button-primary"
          :disabled="acting"
          :aria-label="`${admin.detail.workshop.name} ustaxonasini blokdan chiqarish`"
          @click="unblock"
        >
          Blokdan chiqarish
        </button>
      </div>
    </div>

    <div
      v-if="admin.detail.workshop.status === 'blocked'"
      class="mb-4 rounded-md bg-danger-soft px-4 py-3 text-sm text-danger"
      role="alert"
    >
      <p class="font-bold">
        Bu ustaxona bloklangan — ochiq buyurtmalar muzlatilgan, xodimlar kira olmaydi. Blokdan
        chiqarilganda sessiyalar avtomatik tiklanmaydi.
      </p>
      <p v-if="admin.detail.block_reason" class="mt-1">
        <span class="font-bold">Sabab:</span> {{ admin.detail.block_reason }}
      </p>
    </div>

    <p
      v-if="actionError"
      class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
      role="alert"
    >
      Amal bajarilmadi.
    </p>

    <AppTabs
      v-model="tab"
      :tabs="tabOptions"
      id-prefix="ws"
      label="Ustaxona tafsilotlari"
      variant="admin"
    />

    <section
      v-if="tab === 'profile'"
      id="ws-profile-panel"
      role="tabpanel"
      aria-labelledby="ws-profile-tab"
      class="admin-card max-w-[720px]"
    >
      <div class="admin-card-h">
        <h2>Ustaxona profili</h2>
      </div>
      <div class="admin-card-b">
        <dl class="grid gap-4 sm:grid-cols-2">
          <div>
            <dt class="text-[12.5px] font-semibold text-ink-muted">Nomi</dt>
            <dd class="mt-1 text-base font-bold text-ink">{{ admin.detail.workshop.name }}</dd>
          </div>
          <div>
            <dt class="text-[12.5px] font-semibold text-ink-muted">Rahbar</dt>
            <dd class="mt-1 flex flex-wrap items-center gap-3 text-base font-bold text-ink">
              <span class="text-sm">{{ admin.detail.owner.login }}</span>
              <button
                type="button"
                class="mp-button mp-button-outline min-h-8 px-2.5 text-xs"
                :aria-label="`${admin.detail.owner.login} rahbarining parolini tiklash`"
                @click="resetConfirmOpen = true"
              >
                Parolni tiklash
              </button>
            </dd>
          </div>
          <div>
            <dt class="text-[12.5px] font-semibold text-ink-muted">Yaratildi</dt>
            <dd class="mt-1 text-sm text-ink">
              {{ adminDate(admin.detail.workshop.created_at) }}
            </dd>
          </div>
          <div>
            <dt class="text-[12.5px] font-semibold text-ink-muted">Holat</dt>
            <dd class="mt-1">
              <span class="admin-pill" :class="workshopStatusTone(admin.detail.workshop.status)">
                {{ workshopStatusLabel(admin.detail.workshop.status) }}
              </span>
            </dd>
          </div>
        </dl>
      </div>
    </section>

    <section
      v-else-if="tab === 'branches'"
      id="ws-branches-panel"
      role="tabpanel"
      aria-labelledby="ws-branches-tab"
      class="admin-card"
    >
      <div class="admin-card-h">
        <h2>Filiallar (faqat o'qish)</h2>
      </div>
      <div class="admin-card-b flush">
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead>
              <tr>
                <!-- Middle segment of every order number this branch prints
                     (#26-1-0003) — what support needs to trace a document. -->
                <th>Raqam</th>
                <th>Filial</th>
                <th>Telefon</th>
                <th>Manzil</th>
                <th>Holat</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="branch in admin.detail.branches" :key="branch.id">
                <td class="admin-mono text-ink-muted">{{ branch.branch_no }}</td>
                <td class="nm">
                  {{ branch.name }}
                  <small>{{ branch.id.slice(0, 8) }}</small>
                </td>
                <td class="admin-mono text-ink-muted">{{ branch.phone }}</td>
                <td>{{ branch.address }}</td>
                <td>
                  <span
                    class="admin-pill"
                    :class="
                      branch.status === 'active' ? 'admin-pill-success' : 'admin-pill-warning'
                    "
                  >
                    {{ branchStatusLabel(branch.status) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section
      v-else
      id="ws-users-panel"
      role="tabpanel"
      aria-labelledby="ws-users-tab"
      class="admin-card"
    >
      <div class="admin-card-h">
        <h2>Xodimlar (faqat o'qish)</h2>
      </div>
      <div class="admin-card-b">
        <article class="admin-row-item">
          <span class="admin-pill admin-pill-success">Rahbar</span>
          <span>
            <b>{{ admin.detail.owner.login }}</b>
          </span>
          <span class="admin-mono text-ink-muted">{{ admin.detail.owner.id.slice(0, 8) }}</span>
        </article>
      </div>
    </section>

    <template v-if="blockModalOpen">
      <div class="admin-modal-scrim" aria-hidden="true" @click="blockModalOpen = false"></div>
      <section
        ref="blockPanel"
        class="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="block-title"
        tabindex="-1"
        @keydown="blockTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="block-title">Ustaxonani bloklash</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="blockModalOpen = false"
          >
            <AdminModalCloseIcon />
          </button>
        </div>
        <form novalidate @submit.prevent="block">
          <div class="admin-modal-b">
            <p class="mb-4 text-sm text-ink-soft">
              Xodimlar sessiyalari darhol bekor qilinadi, ochiq buyurtmalar muzlaydi. Mijozlarga
              ta'sir qilmaydi. Blokdan chiqarilganda sessiyalar avtomatik tiklanmaydi.
            </p>
            <label class="admin-field" for="block-reason">
              <span>Sabab</span>
              <textarea
                id="block-reason"
                v-model="reason"
                required
                :aria-invalid="!!blockFieldErrors.reason"
                aria-describedby="block-reason-error"
              ></textarea>
              <span
                v-if="blockFieldErrors.reason"
                id="block-reason-error"
                class="admin-field-error"
                role="alert"
              >
                {{ blockFieldErrors.reason }}
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
              :disabled="!canBlock || acting"
            >
              {{ acting ? 'Bloklanmoqda' : 'Bloklash' }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <ConfirmDialog
      :open="resetConfirmOpen"
      title="Rahbarning parolini tiklash"
      :message="`${admin.detail.owner.login} uchun yangi vaqtinchalik parol yaratiladi va uning barcha sessiyalari darhol bekor qilinadi.`"
      confirm-label="Parolni tiklash"
      busy-label="Tiklanmoqda"
      cancel-label="Bekor qilish"
      :busy="resetting"
      danger
      @confirm="confirmOwnerReset"
      @cancel="resetConfirmOpen = false"
    />

    <AdminSecretModal
      :open="secretOpen && !!admin.lastOwnerSecret"
      title="Vaqtinchalik parol — bir martalik maxfiy ma'lumot"
      intro="Login va vaqtinchalik parolni ustaxona rahbariga yetkazing. Rahbar birinchi kirishda uni almashtiradi."
      :rows="secretRows"
      @close="closeSecret"
    />
  </section>
</template>
