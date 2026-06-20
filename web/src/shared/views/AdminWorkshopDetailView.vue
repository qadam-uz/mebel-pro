<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import {
  adminDate,
  branchStatusLabel,
  workshopStatusLabel,
  workshopStatusTone,
} from '@/shared/app/adminUi'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
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

const canBlock = computed(
  () => admin.detail?.workshop.status === 'active' && reason.value.trim().length > 0,
)
const canUnblock = computed(() => admin.detail?.workshop.status === 'blocked')

async function block() {
  if (!canBlock.value || !admin.detail) return
  acting.value = true
  actionError.value = null
  try {
    await admin.blockWorkshop(admin.detail.workshop.id, reason.value)
    blockModalOpen.value = false
    reason.value = ''
    toast.success('Ustaxona bloklandi')
  } catch {
    actionError.value = 'workshop_block_failed'
    toast.danger("Ustaxonani bloklab bo'lmadi")
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
  } catch {
    actionError.value = 'workshop_unblock_failed'
    toast.danger("Ustaxonani blokdan chiqarib bo'lmadi")
  } finally {
    acting.value = false
  }
}

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
        <p class="date">
          {{ admin.detail.workshop.code }} . {{ admin.detail.workshop.phone }} .
          {{ adminDate(admin.detail.workshop.created_at) }}
        </p>
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
          @click="blockModalOpen = true"
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

    <div class="admin-tabs" role="tablist" aria-label="Ustaxona tafsilotlari">
      <button
        id="ws-tab-profile"
        type="button"
        role="tab"
        :aria-selected="tab === 'profile'"
        aria-controls="ws-panel-profile"
        class="admin-tab"
        :class="{ on: tab === 'profile' }"
        @click="tab = 'profile'"
      >
        Profil
      </button>
      <button
        id="ws-tab-branches"
        type="button"
        role="tab"
        :aria-selected="tab === 'branches'"
        aria-controls="ws-panel-branches"
        class="admin-tab"
        :class="{ on: tab === 'branches' }"
        @click="tab = 'branches'"
      >
        Filiallar
      </button>
      <button
        id="ws-tab-users"
        type="button"
        role="tab"
        :aria-selected="tab === 'users'"
        aria-controls="ws-panel-users"
        class="admin-tab"
        :class="{ on: tab === 'users' }"
        @click="tab = 'users'"
      >
        Xodimlar
      </button>
    </div>

    <section
      v-if="tab === 'profile'"
      id="ws-panel-profile"
      role="tabpanel"
      aria-labelledby="ws-tab-profile"
      class="admin-card max-w-[720px]"
    >
      <div class="admin-card-h">
        <h2>Ustaxona profili</h2>
        <span class="sub">faqat ko'rish . operator tahrirlamaydi</span>
      </div>
      <div class="admin-card-b">
        <p class="mb-4 rounded-md border border-hairline bg-sunk px-3 py-2 text-xs text-ink-soft">
          Operator faqat provisioning, bloklash va blokdan chiqarish amallarini bajaradi — ustaxona
          profili va egasi ma'lumotlari ustaxona egasining mas'uliyatida.
        </p>
        <dl class="grid gap-4 sm:grid-cols-2">
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Nomi</dt>
            <dd class="mt-1 text-base font-bold text-ink">{{ admin.detail.workshop.name }}</dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Kod</dt>
            <dd class="mt-1 font-mono text-sm text-ink">{{ admin.detail.workshop.code }}</dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Telefon</dt>
            <dd class="mt-1 font-mono text-sm text-ink">{{ admin.detail.workshop.phone }}</dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Manzil</dt>
            <dd class="mt-1 text-base font-bold text-ink">
              {{ admin.detail.workshop.address ?? '-' }}
            </dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Ega</dt>
            <dd class="mt-1 text-base font-bold text-ink">
              {{ admin.detail.owner.full_name }}
              <span class="block font-mono text-xs text-ink-muted">
                {{ admin.detail.owner.login }} . {{ admin.detail.owner.phone }}
              </span>
            </dd>
          </div>
          <div>
            <dt class="text-xs font-extrabold uppercase text-ink-muted">Holat</dt>
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
      id="ws-panel-branches"
      role="tabpanel"
      aria-labelledby="ws-tab-branches"
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
                <th>Filial</th>
                <th>Telefon</th>
                <th>Manzil</th>
                <th>Holat</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="branch in admin.detail.branches" :key="branch.id">
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
      id="ws-panel-users"
      role="tabpanel"
      aria-labelledby="ws-tab-users"
      class="admin-card"
    >
      <div class="admin-card-h">
        <h2>Xodimlar (faqat o'qish)</h2>
        <span class="sub">rol yo'q - is_owner + berilgan ruxsatlar</span>
      </div>
      <div class="admin-card-b">
        <article class="admin-row-item">
          <span class="admin-pill admin-pill-success">owner</span>
          <span>
            <b>{{ admin.detail.owner.full_name }}</b>
            <small class="block text-ink-muted">
              {{ admin.detail.owner.login }} . {{ admin.detail.owner.phone }}
            </small>
          </span>
          <span class="admin-mono text-ink-muted">{{ admin.detail.owner.id.slice(0, 8) }}</span>
        </article>
        <div class="admin-empty mt-4">
          <h3>Staff ro'yxati alohida ko'rsatilmaydi</h3>
          <p>
            v1 operator doirasi ega va filiallarni incident response uchun faqat o'qish rejimida
            ko'rsatadi.
          </p>
        </div>
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
            x
          </button>
        </div>
        <form novalidate @submit.prevent="block">
          <div class="admin-modal-b">
            <p class="mb-4 text-sm text-ink-soft">
              Xodimlar sessiyalari darhol bekor qilinadi, ochiq buyurtmalar muzlaydi. Mijozlarga
              ta'sir qilmaydi. Blokdan chiqarilganda sessiyalar avtomatik tiklanmaydi.
            </p>
            <label class="admin-field" for="block-reason">
              <span>Majburiy sabab</span>
              <textarea id="block-reason" v-model="reason"></textarea>
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
  </section>
</template>
