<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { dekorTurLabel } from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import {
  adminDate,
  adminErrorMessage,
  materialStatusLabel,
  materialStatusTone,
} from '@/shared/app/adminUi'
import { apiErrorCode, captureApiError } from '@/shared/api/client'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore, type Dekor, type MaterialStatus } from '@/shared/stores/admin'

const route = useRoute()
const admin = useAdminStore()
const rolePath = useRolePath()
const toast = useToast()

const dekorId = String(route.params.dekor_id)
// The record is component-local: a detail page owns one row nobody else reads,
// and parking it in the store would leave a stale dekor behind on the next visit.
const dekor = ref<Dekor | null>(null)
const loading = ref(false)
const loadError = ref<string | null>(null)
const loadTraceId = ref<string | null>(null)
const statusTarget = ref<MaterialStatus | null>(null)
const acting = ref(false)

const swatchClass = computed(() =>
  dekor.value
    ? materialSwatchClass(dekor.value)
    : materialSwatchClass({ id: dekorId, nomi: '', kod: null }),
)

async function load() {
  loading.value = true
  loadError.value = null
  loadTraceId.value = null
  try {
    dekor.value = await admin.fetchDekor(dekorId)
  } catch (error) {
    const captured = captureApiError(error, 'dekor_load_failed')
    loadError.value = captured.code
    loadTraceId.value = captured.traceId
  } finally {
    loading.value = false
  }
}

async function confirmStatus() {
  const target = statusTarget.value
  const row = dekor.value
  statusTarget.value = null
  if (!target || !row) return
  acting.value = true
  try {
    // The store patches the cached list too, so going back shows the new state
    // without a reload.
    dekor.value = await admin.setDekorStatus(row.id, target)
    toast.success(target === 'active' ? 'Faollashtirildi' : 'Faol emas qilindi')
  } catch (error) {
    toast.danger(adminErrorMessage(apiErrorCode(error), "Dekor holatini o'zgartirib bo'lmadi."))
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>

<template>
  <section>
    <RouterLink :to="rolePath('/admin/catalog/dekorlar')" class="admin-back">
      ← Dekorlar
    </RouterLink>

    <section v-if="loading" class="admin-card p-5" aria-live="polite">
      <div class="admin-skeleton-line w-2/5"></div>
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-1/5"></div>
    </section>

    <AdminErrorState
      v-else-if="loadError"
      :code="loadError"
      :trace-id="loadTraceId"
      title="Dekor yuklanmadi"
      @retry="load()"
    />

    <template v-else-if="dekor">
      <div class="admin-page-head">
        <div class="flex min-w-0 items-center gap-4">
          <div class="admin-material-thumb">
            <span
              class="admin-material-thumb-swatch sw"
              :class="swatchClass"
              aria-hidden="true"
            ></span>
            <span class="admin-material-thumb-mark" aria-hidden="true">
              {{ dekor.tur === 'kromka' ? 'K' : 'L' }}
            </span>
            <AuthFileImage
              v-if="dekor.image_file_id"
              :file-id="dekor.image_file_id"
              :alt="dekor.label"
              class="admin-material-thumb-img"
            />
          </div>
          <div class="min-w-0">
            <h1 class="truncate">{{ dekor.nomi }}</h1>
            <p class="text-sm font-bold text-ink-soft">{{ dekor.label }}</p>
          </div>
        </div>
        <button
          type="button"
          class="mp-button mp-button-outline"
          :disabled="acting"
          @click="statusTarget = dekor.holat === 'active' ? 'inactive' : 'active'"
        >
          {{ dekor.holat === 'active' ? 'Faol emas qilish' : 'Faollashtirish' }}
        </button>
      </div>

      <section class="admin-card max-w-[720px]">
        <div class="admin-card-h">
          <h2>Ma'lumotlari</h2>
        </div>
        <div class="admin-card-b">
          <dl class="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            <div>
              <dt class="text-xs font-bold text-ink-soft">Ishlab chiqaruvchi</dt>
              <dd class="text-sm font-bold text-ink">{{ dekor.manufacturer_name }}</dd>
            </div>
            <div>
              <dt class="text-xs font-bold text-ink-soft">Tur</dt>
              <dd>
                <span
                  class="admin-pill"
                  :class="dekor.tur === 'kromka' ? 'admin-pill-info' : 'admin-pill-success'"
                >
                  {{ dekorTurLabel(dekor.tur) }}
                </span>
              </dd>
            </div>
            <div>
              <dt class="text-xs font-bold text-ink-soft">Kod</dt>
              <dd class="admin-mono text-sm">{{ dekor.kod ?? "kod yo'q" }}</dd>
            </div>
            <div>
              <dt class="text-xs font-bold text-ink-soft">Tekstura yo'nalishi</dt>
              <dd class="text-sm font-bold text-ink">{{ dekor.tolali ? 'Bor' : "Yo'q" }}</dd>
            </div>
            <div>
              <dt class="text-xs font-bold text-ink-soft">Holat</dt>
              <dd>
                <span class="admin-pill" :class="materialStatusTone(dekor.holat)">
                  {{ materialStatusLabel(dekor.holat) }}
                </span>
              </dd>
            </div>
            <div>
              <dt class="text-xs font-bold text-ink-soft">Qo'shilgan</dt>
              <dd class="text-sm font-bold text-ink">{{ adminDate(dekor.created_at) }}</dd>
            </div>
          </dl>
        </div>
      </section>

      <!-- Derived, read-only: a dekor has no format and no price of its own. Both
           tables below describe what BRANCHES did with it, which is why they are
           reported here and not editable. -->
      <section class="admin-card mt-4">
        <div class="admin-card-h">
          <h2>Tarmoqdagi o'lchamlar</h2>
          <span class="sub">Filiallar shu dekorni qanday o'lchamlarda olib boradi</span>
        </div>
        <div class="admin-card-b">
          <p class="text-sm font-bold text-ink-soft">
            O'lchamlar kesimi hozircha platforma API'sida ochilmagan — dekor javobida faqat
            filiallar soni bor. Kerakli endpoint qo'shilgach shu joyga jadval tushadi.
          </p>
        </div>
      </section>

      <section class="admin-card mt-4">
        <div class="admin-card-h">
          <h2>Olib boradigan filiallar</h2>
          <span class="sub">{{ dekor.branch_usage_count }} ta filial</span>
        </div>
        <div class="admin-card-b">
          <p v-if="dekor.branch_usage_count === 0" class="text-sm font-bold text-ink-soft">
            Hech bir filial bu dekorni hali olib bormaydi.
          </p>
          <p v-else class="text-sm font-bold text-ink-soft">
            {{ dekor.branch_usage_count }} ta filial bu dekorni olib boradi. Filiallar ro'yxati
            hozircha platforma API'sida ochilmagan.
          </p>
        </div>
      </section>
    </template>

    <ConfirmDialog
      :open="statusTarget !== null"
      :title="statusTarget === 'inactive' ? 'Faol emas qilish' : 'Faollashtirish'"
      :message="
        statusTarget === 'inactive'
          ? `${dekor?.label} faol emas qilinadi — uni filiallarning yangi tanlovlaridan yashiriladi; mavjud buyurtmalarga ta'sir qilmaydi.`
          : `${dekor?.label} faollashtiriladi va filial tanlovida ko'rinadi.`
      "
      confirm-label="Tasdiqlash"
      cancel-label="Bekor qilish"
      :danger="statusTarget === 'inactive'"
      :busy="acting"
      @confirm="confirmStatus"
      @cancel="statusTarget = null"
    />
  </section>
</template>
