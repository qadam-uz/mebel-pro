<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  adminDateTime,
  dropdownOption,
  errorStatusLabel,
  errorStatusTone,
} from '@/shared/app/adminUi'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import { useAdminStore, type ErrorRecord } from '@/shared/stores/admin'

const admin = useAdminStore()
const toast = useToast()
const selectedId = ref<string | null>(null)
const confirmResolveOpen = ref(false)
const detailPanel = ref<HTMLElement | null>(null)
const detailOpen = computed(() => selectedId.value !== null)
const detailTrap = useFocusTrap(detailPanel, detailOpen, () => (selectedId.value = null))
const resolvingId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const query = ref('')
const statusFilter = ref('all')
const moduleFilter = ref('all')

const statusOptions = [
  dropdownOption('all', 'Hammasi', 'barcha kodlar'),
  dropdownOption('open', 'Ochiq', 'hal qilinmagan'),
  dropdownOption('resolved', 'Hal qilingan', 'tasdiqlangan'),
]
const moduleOptions = computed(() => [
  dropdownOption('all', 'Modul', 'barcha modullar'),
  ...Array.from(new Set(admin.errors.map((error) => error.module))).map((module) =>
    dropdownOption(module, module, 'module'),
  ),
])
const selectedDetail = computed(() =>
  admin.errorDetail?.record.id === selectedId.value ? admin.errorDetail : null,
)
const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return admin.errors.filter((record) => {
    if (statusFilter.value !== 'all' && record.status !== statusFilter.value) return false
    if (moduleFilter.value !== 'all' && record.module !== moduleFilter.value) return false
    if (!needle) return true
    return [record.code, record.module, record.preview_message ?? '']
      .join(' ')
      .toLowerCase()
      .includes(needle)
  })
})

function contextText(value: Record<string, unknown> | null) {
  if (!value) return "Kontekst yo'q"
  return JSON.stringify(value, null, 2)
}

async function openDetail(record: ErrorRecord) {
  selectedId.value = record.id
  actionError.value = null
  try {
    await admin.loadErrorDetail(record.id)
  } catch {
    actionError.value = 'error_detail_failed'
  }
}

async function resolveSelected() {
  if (!selectedId.value) return
  confirmResolveOpen.value = false
  resolvingId.value = selectedId.value
  actionError.value = null
  try {
    await admin.resolveError(selectedId.value)
    toast.success('Xatolik tasdiqlandi')
  } catch {
    actionError.value = 'error_resolve_failed'
    toast.danger('Amal bajarilmadi')
  } finally {
    resolvingId.value = null
  }
}

onMounted(admin.loadErrors)
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Xatolik monitor</h1>
        <p class="sub">Grouped application errors, spike counts, trace IDs va context.</p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadErrors">
        Yangilash
      </button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span class="sr-only">Kod yoki tavsif</span>
        <input v-model="query" placeholder="Kod yoki tavsif" />
      </label>
      <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" />
      <ProjectDropdown v-model="moduleFilter" label="Module" :options="moduleOptions" />
    </div>

    <section v-if="admin.opsLoading" class="admin-card p-5" aria-live="polite">
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="admin.opsError"
      :code="admin.opsError"
      :trace-id="admin.opsTraceId"
      title="Xatoliklar yuklanmadi"
      @retry="admin.loadErrors"
    />

    <section v-else-if="filtered.length === 0" class="admin-empty">
      <h3>Xatolik yozilmagan</h3>
      <p>Xatolik yo'q — zo'r.</p>
    </section>

    <section v-else class="admin-card">
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Kod</th>
              <th>Modul</th>
              <th class="admin-right">24 soat</th>
              <th class="admin-right">7 kun</th>
              <th>Oxirgi</th>
              <th>Tavsif</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in filtered" :key="record.id">
              <td class="nm">
                {{ record.code }}
                <small>{{ errorStatusLabel(record.status) }}</small>
              </td>
              <td class="admin-mono text-ink-muted">{{ record.module }}</td>
              <td class="admin-right admin-mono">{{ record.count_24h }}</td>
              <td class="admin-right admin-mono">{{ record.count_7d }}</td>
              <td class="admin-mono text-ink-muted">
                {{ adminDateTime(record.last_occurred_at) }}
              </td>
              <td class="max-w-[360px] truncate">{{ record.preview_message ?? "Tavsif yo'q" }}</td>
              <td class="admin-right">
                <div class="flex justify-end gap-2">
                  <span class="admin-pill" :class="errorStatusTone(record.status)">
                    {{ errorStatusLabel(record.status) }}
                  </span>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    @click="openDetail(record)"
                  >
                    Tafsilotlar
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
      role="alert"
    >
      Error action bajarilmadi.
    </p>

    <template v-if="selectedId">
      <div class="admin-modal-scrim" aria-hidden="true" @click="selectedId = null"></div>
      <section
        ref="detailPanel"
        class="admin-modal wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="error-title"
        tabindex="-1"
        @keydown="detailTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="error-title">Xatolik tafsiloti</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="selectedId = null"
          >
            x
          </button>
        </div>
        <div class="admin-modal-b">
          <div v-if="!selectedDetail" class="admin-card p-4">
            <div class="admin-skeleton-line w-3/5"></div>
            <div class="admin-skeleton-line w-4/5"></div>
          </div>
          <template v-else>
            <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="font-mono text-sm font-extrabold text-ink">
                  {{ selectedDetail.record.code }}
                </div>
                <p class="mt-1 text-sm text-ink-muted">
                  {{ selectedDetail.record.preview_message }}
                </p>
              </div>
              <button
                type="button"
                class="mp-button mp-button-primary"
                :disabled="
                  selectedDetail.record.status === 'resolved' || resolvingId === selectedId
                "
                @click="confirmResolveOpen = true"
              >
                {{
                  selectedDetail.record.status === 'resolved'
                    ? 'Tasdiqlandi'
                    : resolvingId === selectedId
                      ? 'Tasdiqlanmoqda'
                      : 'Tasdiqlash (resolve)'
                }}
              </button>
            </div>
            <article
              v-for="occurrence in selectedDetail.occurrences"
              :key="occurrence.id"
              class="mb-3 rounded-md border border-hairline bg-sunk p-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="admin-mono font-bold text-ink">trace {{ occurrence.trace_id }}</span>
                <span class="admin-mono text-ink-muted">{{
                  adminDateTime(occurrence.occurred_at)
                }}</span>
              </div>
              <p class="mt-3 text-sm text-ink">{{ occurrence.message }}</p>
              <pre
                class="mt-3 max-h-52 overflow-auto rounded bg-elevated p-3 text-xs text-ink-soft"
                >{{ contextText(occurrence.context) }}</pre
              >
              <pre
                v-if="occurrence.stack"
                class="mt-3 max-h-52 overflow-auto rounded bg-elevated p-3 text-xs text-ink-soft"
                >{{ occurrence.stack }}</pre
              >
            </article>
          </template>
        </div>
        <div class="admin-modal-f">
          <button type="button" class="mp-button mp-button-outline" @click="selectedId = null">
            Yopish
          </button>
        </div>
      </section>
    </template>

    <ConfirmDialog
      :open="confirmResolveOpen"
      title="Xatolikni tasdiqlash"
      message="Bu xatolik kodi hal qilingan deb belgilanadi va monitor ro'yxatida resolved ko'rinadi."
      confirm-label="Tasdiqlash"
      busy-label="Tasdiqlanmoqda"
      cancel-label="Bekor qilish"
      :busy="resolvingId !== null"
      @confirm="resolveSelected"
      @cancel="confirmResolveOpen = false"
    />
  </section>
</template>
