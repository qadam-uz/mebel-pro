<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { adminDateTime, platformUserStatusTone } from '@/shared/app/adminUi'
import AdminSecretModal from '@/shared/components/AdminSecretModal.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore, type PlatformUser } from '@/shared/stores/admin'
import { useAuthStore } from '@/shared/stores/auth'

const admin = useAdminStore()
const auth = useAuthStore()
const toast = useToast()
const modalOpen = ref(false)
const blockModalOpen = ref(false)
const secretOpen = ref(false)
const resetTarget = ref<PlatformUser | null>(null)
const formPanel = ref<HTMLElement | null>(null)
const blockPanel = ref<HTMLElement | null>(null)
const formTrap = useFocusTrap(formPanel, modalOpen, () => (modalOpen.value = false))
const blockTrap = useFocusTrap(blockPanel, blockModalOpen, () => (blockModalOpen.value = false))
const saving = ref(false)
const actionId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const editingId = ref<string | null>(null)
const blockTarget = ref<PlatformUser | null>(null)
const blockReason = ref('')
const query = ref('')

const secretRows = computed(() => {
  const secret = admin.lastPlatformUserSecret
  if (!secret) return []
  return [
    { label: 'Operator', value: secret.user.login },
    { label: 'Temp password', value: secret.temp_password },
  ]
})

function closeSecret() {
  secretOpen.value = false
  admin.clearSecrets()
}

onBeforeUnmount(() => admin.clearSecrets())
const form = reactive({
  fullName: '',
  login: '',
  phone: '+998',
  tempPassword: '',
})

const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) return admin.platformUsers
  return admin.platformUsers.filter((user) =>
    [user.full_name, user.login, user.phone, user.status].join(' ').toLowerCase().includes(needle),
  )
})

function openCreate() {
  editingId.value = null
  form.fullName = ''
  form.login = ''
  form.phone = '+998'
  form.tempPassword = ''
  actionError.value = null
  modalOpen.value = true
}

function openEdit(user: PlatformUser) {
  editingId.value = user.id
  form.fullName = user.full_name
  form.login = user.login
  form.phone = user.phone
  form.tempPassword = ''
  actionError.value = null
  modalOpen.value = true
}

async function saveUser() {
  saving.value = true
  actionError.value = null
  try {
    if (editingId.value) {
      await admin.updatePlatformUser(editingId.value, {
        full_name: form.fullName,
        phone: form.phone,
      })
      modalOpen.value = false
      toast.success('Operator yangilandi')
    } else {
      await admin.createPlatformUser({
        full_name: form.fullName,
        login: form.login,
        phone: form.phone,
        temp_password: form.tempPassword || null,
      })
      modalOpen.value = false
      secretOpen.value = true
      toast.success('Operator yaratildi')
    }
  } catch {
    actionError.value = 'platform_user_save_failed'
    toast.danger('Operator amali bajarilmadi')
  } finally {
    saving.value = false
  }
}

function askReset(user: PlatformUser) {
  resetTarget.value = user
}

async function confirmReset() {
  const target = resetTarget.value
  if (!target) return
  actionId.value = target.id
  actionError.value = null
  try {
    await admin.resetPlatformUserPassword(target.id)
    resetTarget.value = null
    secretOpen.value = true
    toast.success('Yangi vaqtinchalik parol yaratildi')
  } catch {
    actionError.value = 'platform_user_reset_failed'
    toast.danger("Parolni qaytarib bo'lmadi")
  } finally {
    actionId.value = null
  }
}

function askBlock(user: PlatformUser) {
  blockTarget.value = user
  blockReason.value = ''
  blockModalOpen.value = true
}

async function confirmBlock() {
  if (!blockTarget.value || !blockReason.value.trim()) return
  actionId.value = blockTarget.value.id
  actionError.value = null
  try {
    await admin.blockPlatformUser(blockTarget.value.id, blockReason.value)
    blockModalOpen.value = false
    blockTarget.value = null
    toast.success('Operator bloklandi')
  } catch {
    actionError.value = 'platform_user_block_failed'
    toast.danger("Operatorni bloklab bo'lmadi")
  } finally {
    actionId.value = null
  }
}

async function unblock(id: string) {
  actionId.value = id
  actionError.value = null
  try {
    await admin.unblockPlatformUser(id)
    toast.success('Operator blokdan chiqarildi')
  } catch {
    actionError.value = 'platform_user_unblock_failed'
    toast.danger("Operatorni blokdan chiqarib bo'lmadi")
  } finally {
    actionId.value = null
  }
}

onMounted(admin.loadPlatformUsers)
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Platforma operatorlari</h1>
        <p class="sub">Platforma scope bir xil; permission modeli yo'q.</p>
      </div>
      <button type="button" class="admin-primary-action" @click="openCreate">Yangi operator</button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span class="sr-only">Operator qidiruv</span>
        <input v-model="query" placeholder="Ism, login yoki telefon" />
      </label>
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadPlatformUsers">
        Yangilash
      </button>
    </div>

    <section v-if="admin.opsLoading" class="admin-card p-5">
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <section v-else-if="admin.opsError" class="admin-error">
      <h3>Operatorlar yuklanmadi</h3>
      <p>
        Platform users endpoint javob bermadi.
        <span v-if="admin.opsTraceId" class="admin-mono">trace {{ admin.opsTraceId }}</span>
      </p>
    </section>

    <section v-else-if="filtered.length === 0" class="admin-empty">
      <h3>Operator topilmadi</h3>
      <p>Filtrni tozalang yoki yangi operator yarating.</p>
    </section>

    <section v-else class="admin-card">
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Operator</th>
              <th>Login</th>
              <th>Telefon</th>
              <th>Oxirgi kirish</th>
              <th>Holat</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in filtered" :key="user.id">
              <td class="nm">
                {{ user.full_name }}
                <small>{{ user.id.slice(0, 8) }}</small>
              </td>
              <td class="admin-mono text-ink-muted">{{ user.login }}</td>
              <td class="admin-mono text-ink-muted">{{ user.phone }}</td>
              <td class="admin-mono text-ink-muted">{{ adminDateTime(user.last_login_at) }}</td>
              <td>
                <span class="admin-pill" :class="platformUserStatusTone(user.status)">
                  {{ user.status }}
                </span>
              </td>
              <td class="admin-right">
                <div class="flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    @click="openEdit(user)"
                  >
                    Tahrirlash
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :disabled="actionId === user.id"
                    @click="askReset(user)"
                  >
                    Parol qaytarish
                  </button>
                  <button
                    v-if="user.status === 'active'"
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs text-danger"
                    :disabled="user.id === auth.me?.principal_id"
                    @click="askBlock(user)"
                  >
                    {{
                      user.id === auth.me?.principal_id ? "O'zini bloklab bo'lmaydi" : 'Bloklash'
                    }}
                  </button>
                  <button
                    v-else
                    type="button"
                    class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                    :disabled="actionId === user.id"
                    @click="unblock(user.id)"
                  >
                    Blokdan chiqarish
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p
      v-if="actionError"
      class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
    >
      Operator amali bajarilmadi.
    </p>

    <AdminSecretModal
      :open="secretOpen && !!admin.lastPlatformUserSecret"
      title="Vaqtinchalik parol — bir martalik maxfiy ma'lumot"
      intro="Login va vaqtinchalik parolni operatorga yetkazing. Operator birinchi kirishda uni almashtiradi."
      :rows="secretRows"
      @close="closeSecret"
    />

    <ConfirmDialog
      :open="resetTarget !== null"
      title="Parolni qaytarish"
      :message="`${resetTarget?.full_name ?? ''} uchun yangi vaqtinchalik parol yaratiladi va uning barcha sessiyalari darhol bekor qilinadi.`"
      confirm-label="Parolni qaytarish"
      busy-label="Qaytarilmoqda"
      cancel-label="Bekor qilish"
      :busy="actionId === resetTarget?.id"
      danger
      @confirm="confirmReset"
      @cancel="resetTarget = null"
    />

    <template v-if="modalOpen">
      <div class="admin-modal-scrim" aria-hidden="true" @click="modalOpen = false"></div>
      <section
        ref="formPanel"
        class="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="operator-title"
        tabindex="-1"
        @keydown="formTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="operator-title">{{ editingId ? 'Operator tahrirlash' : 'Yangi operator' }}</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="modalOpen = false"
          >
            x
          </button>
        </div>
        <form @submit.prevent="saveUser">
          <div class="admin-modal-b">
            <div class="admin-form-grid">
              <label class="admin-field admin-full" for="op-name">
                <span>Ism</span>
                <input id="op-name" v-model="form.fullName" autocomplete="name" required />
              </label>
              <label class="admin-field" for="op-phone">
                <span>Telefon</span>
                <input
                  id="op-phone"
                  v-model="form.phone"
                  autocomplete="tel"
                  inputmode="tel"
                  required
                />
              </label>
              <label class="admin-field" for="op-login">
                <span>Login</span>
                <input
                  id="op-login"
                  v-model="form.login"
                  autocomplete="username"
                  :disabled="!!editingId"
                  required
                />
              </label>
              <label v-if="!editingId" class="admin-field admin-full" for="op-pass">
                <span>Temp password</span>
                <input
                  id="op-pass"
                  v-model="form.tempPassword"
                  autocomplete="new-password"
                  placeholder="Bo'sh qoldirilsa avtomatik yaratiladi"
                />
              </label>
            </div>
          </div>
          <div class="admin-modal-f">
            <button type="button" class="mp-button mp-button-outline" @click="modalOpen = false">
              Bekor
            </button>
            <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
              {{ saving ? 'Saqlanmoqda' : 'Saqlash' }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <template v-if="blockModalOpen && blockTarget">
      <div class="admin-modal-scrim" aria-hidden="true" @click="blockModalOpen = false"></div>
      <section
        ref="blockPanel"
        class="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="block-user-title"
        tabindex="-1"
        @keydown="blockTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="block-user-title">Operatorni bloklash</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="blockModalOpen = false"
          >
            x
          </button>
        </div>
        <form @submit.prevent="confirmBlock">
          <div class="admin-modal-b">
            <p class="mb-4 text-sm text-ink-soft">
              {{ blockTarget.full_name }} sessiyalari darhol bekor qilinadi. Oxirgi faol operator
              bloklanmaydi.
            </p>
            <label class="admin-field" for="op-block-reason">
              <span>Majburiy sabab</span>
              <textarea id="op-block-reason" v-model="blockReason" required></textarea>
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
              class="mp-button mp-button-primary"
              :disabled="!blockReason.trim() || actionId === blockTarget.id"
            >
              Bloklash
            </button>
          </div>
        </form>
      </section>
    </template>
  </section>
</template>
