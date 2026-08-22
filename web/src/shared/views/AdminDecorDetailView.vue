<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'

import { DECOR_TYPES, decorTypeLabel, isTape } from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { normalizeThickness, standardFormatSet } from '@/shared/app/standardFormats'
import {
  adminDate,
  adminErrorMessage,
  materialStatusLabel,
  materialStatusTone,
} from '@/shared/app/adminUi'
import { ApiError, apiErrorCode, captureApiError } from '@/shared/api/client'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import AppModal from '@/shared/components/AppModal.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import ActionMenu from '@/shared/components/ActionMenu.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useToast } from '@/shared/composables/useToast'
import {
  useAdminStore,
  type Decor,
  type DecorFormat,
  type DecorType,
  type MaterialStatus,
} from '@/shared/stores/admin'

const route = useRoute()
const { t } = useI18n()
const admin = useAdminStore()
const rolePath = useRolePath()
const toast = useToast()

const decorId = String(route.params.decor_id)
// The record is component-local: a detail page owns one row nobody else reads,
// and parking it in the store would leave a stale decor behind on the next visit.
const decor = ref<Decor | null>(null)
const loading = ref(false)
const loadError = ref<string | null>(null)
const loadTraceId = ref<string | null>(null)
const statusTarget = ref<MaterialStatus | null>(null)
const acting = ref(false)

// ── Formats ────────────────────────────────────────────────────────────────
// Platform-owned and immutable: there is no edit, only create and a status
// toggle. A wrong format is deactivated and a correct one added, because branch
// rows, stock and order history all resolve through the format's id.
const formats = ref<DecorFormat[]>([])
const formatsLoading = ref(false)
const formatsError = ref<string | null>(null)
const formOpen = ref(false)
const saving = ref(false)
const formError = ref<string | null>(null)
const formErrorField = ref<string | null>(null)

const draft = reactive({
  type: 'ldsp' as DecorType,
  thickness: '',
  length: '',
  width: '',
  tapeWidth: '',
  finishedSides: 2,
})

const typeOptions = computed(() =>
  DECOR_TYPES.map((value) => ({ value, label: decorTypeLabel(value) })),
)
// FormSelect speaks `string | null`; the draft holds the narrowed enum.
const draftType = computed({
  get: (): string | null => draft.type,
  set: (value: string | null) => {
    draft.type = (value ?? 'ldsp') as DecorType
  },
})
const draftIsTape = computed(() => isTape(draft.type))
// `finished_sides` is a product fact only for the board types; the server
// rejects it on anything else, so the field follows the same rule.
const needsFinishedSides = computed(() => ['ldsp', 'dsp', 'mdf'].includes(draft.type))
// Quick-fill only — the operator can still type anything the manufacturer makes.
const chips = computed(() => standardFormatSet(draft.type))

function formatSize(row: DecorFormat): string {
  if (row.tape_width_mm !== null) return `${row.tape_width_mm} mm`
  return row.length_mm !== null && row.width_mm !== null ? `${row.length_mm}×${row.width_mm}` : '—'
}

async function loadFormats() {
  formatsLoading.value = true
  formatsError.value = null
  try {
    formats.value = await admin.fetchDecorFormats(decorId)
  } catch (error) {
    formatsError.value = captureApiError(error, 'decor_formats_load_failed').code
  } finally {
    formatsLoading.value = false
  }
}

function openFormatForm() {
  draft.type = 'ldsp'
  draft.thickness = ''
  draft.length = ''
  draft.width = ''
  draft.tapeWidth = ''
  draft.finishedSides = 2
  formError.value = null
  formErrorField.value = null
  formOpen.value = true
}

/**
 * Which field the server blamed. `decor_format_shape_mismatch` carries
 * `details.field` so the message can sit next to the input that caused it
 * rather than floating above a six-field form.
 */
function errorField(error: unknown): string | null {
  if (!(error instanceof ApiError) || typeof error.body !== 'object' || error.body === null) {
    return null
  }
  const details = (error.body as { details?: { field?: unknown } }).details
  return typeof details?.field === 'string' ? details.field : null
}

/** Quick-fill both sides of a sheet from one chip. */
function applySizeChip(size: { length_mm: number; width_mm: number }) {
  draft.length = String(size.length_mm)
  draft.width = String(size.width_mm)
}

function optionalInt(value: string): number | null {
  const parsed = Number(value.trim())
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

async function submitFormat() {
  formError.value = null
  formErrorField.value = null
  saving.value = true
  try {
    const created = await admin.createDecorFormat(decorId, {
      type: draft.type,
      thickness_mm: normalizeThickness(draft.thickness.replace(',', '.')),
      length_mm: draftIsTape.value ? null : optionalInt(draft.length),
      width_mm: draftIsTape.value ? null : optionalInt(draft.width),
      tape_width_mm: draftIsTape.value ? optionalInt(draft.tapeWidth) : null,
      finished_sides: needsFinishedSides.value ? draft.finishedSides : null,
    })
    formats.value = [...formats.value, created]
    formOpen.value = false
    toast.success(t('catalog.formats.created'))
    // `format_count` lives on the decor and drives the admin list column.
    await load()
  } catch (error) {
    const code = apiErrorCode(error)
    formError.value = adminErrorMessage(code, t('catalog.formats.saveFailed'))
    formErrorField.value = errorField(error)
  } finally {
    saving.value = false
  }
}

async function toggleFormatStatus(row: DecorFormat) {
  const next: MaterialStatus = row.status === 'active' ? 'inactive' : 'active'
  try {
    const updated = await admin.setDecorFormatStatus(decorId, row.id, next)
    formats.value = formats.value.map((item) => (item.id === updated.id ? updated : item))
    toast.success(t('catalog.formats.statusChanged'))
    await load()
  } catch (error) {
    toast.danger(adminErrorMessage(apiErrorCode(error), t('catalog.formats.saveFailed')))
  }
}

const swatchClass = computed(() =>
  decor.value
    ? materialSwatchClass(decor.value)
    : materialSwatchClass({ id: decorId, name: '', code: null }),
)

async function load() {
  loading.value = true
  loadError.value = null
  loadTraceId.value = null
  try {
    decor.value = await admin.fetchDecor(decorId)
  } catch (error) {
    const captured = captureApiError(error, 'decor_load_failed')
    loadError.value = captured.code
    loadTraceId.value = captured.traceId
  } finally {
    loading.value = false
  }
}

async function confirmStatus() {
  const target = statusTarget.value
  const row = decor.value
  statusTarget.value = null
  if (!target || !row) return
  acting.value = true
  try {
    // The store patches the cached list too, so going back shows the new state
    // without a reload.
    decor.value = await admin.setDecorStatus(row.id, target)
    toast.success(target === 'active' ? 'Faollashtirildi' : 'Faol emas qilindi')
  } catch (error) {
    toast.danger(adminErrorMessage(apiErrorCode(error), "Dekor holatini o'zgartirib bo'lmadi."))
  } finally {
    acting.value = false
  }
}

onMounted(async () => {
  await load()
  await loadFormats()
})
</script>

<template>
  <section>
    <RouterLink :to="rolePath('/admin/catalog/decors')" class="admin-back"> ← Dekorlar </RouterLink>

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

    <template v-else-if="decor">
      <div class="admin-page-head">
        <div class="flex min-w-0 items-center gap-4">
          <div class="admin-material-thumb">
            <span
              class="admin-material-thumb-swatch sw"
              :class="swatchClass"
              aria-hidden="true"
            ></span>
            <AuthFileImage
              v-if="decor.image_file_id"
              :file-id="decor.image_file_id"
              :alt="decor.label"
              class="admin-material-thumb-img"
            />
          </div>
          <div class="min-w-0">
            <h1 class="truncate">{{ decor.name }}</h1>
            <p class="text-sm font-bold text-ink-soft">{{ decor.label }}</p>
          </div>
        </div>
        <button
          type="button"
          class="mp-button mp-button-outline"
          :disabled="acting"
          @click="statusTarget = decor.status === 'active' ? 'inactive' : 'active'"
        >
          {{ decor.status === 'active' ? 'Faol emas qilish' : 'Faollashtirish' }}
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
              <dd class="text-sm font-bold text-ink">{{ decor.manufacturer_name }}</dd>
            </div>
            <div>
              <dt class="text-xs font-bold text-ink-soft">Kod</dt>
              <dd class="admin-mono text-sm">{{ decor.code ?? "code yo'q" }}</dd>
            </div>
            <div>
              <dt class="text-xs font-bold text-ink-soft">Tekstura yo'nalishi</dt>
              <dd class="text-sm font-bold text-ink">{{ decor.has_grain ? 'Bor' : "Yo'q" }}</dd>
            </div>
            <div>
              <dt class="text-xs font-bold text-ink-soft">Holat</dt>
              <dd>
                <span class="admin-pill" :class="materialStatusTone(decor.status)">
                  {{ materialStatusLabel(decor.status) }}
                </span>
              </dd>
            </div>
            <div>
              <dt class="text-xs font-bold text-ink-soft">Qo'shilgan</dt>
              <dd class="text-sm font-bold text-ink">{{ adminDate(decor.created_at) }}</dd>
            </div>
          </dl>
        </div>
      </section>

      <!-- Formats: the platform's product list for this decor. Immutable by
           design — a wrong one is deactivated and a correct one added, because
           branch rows, stock, cutting panels and order history all resolve
           through a format's id, and re-dimensioning it in place would rewrite
           what those rows mean. -->
      <section class="admin-card mt-4">
        <div class="admin-card-h">
          <h2>{{ $t('catalog.formats.title') }}</h2>
          <span class="sub">{{ $t('catalog.formats.subtitle') }}</span>
          <button type="button" class="mp-button mp-button-primary ml-auto" @click="openFormatForm">
            {{ $t('catalog.formats.add') }}
          </button>
        </div>
        <div class="admin-card-b">
          <div v-if="formatsLoading" aria-live="polite">
            <div class="admin-skeleton-line w-3/5"></div>
            <div class="admin-skeleton-line w-2/5"></div>
          </div>

          <AdminErrorState
            v-else-if="formatsError"
            :code="formatsError"
            title="Formatlar yuklanmadi"
            @retry="loadFormats()"
          />

          <p v-else-if="formats.length === 0" class="text-sm font-bold text-ink-soft">
            {{ $t('catalog.formats.empty') }}
          </p>

          <div v-else class="admin-table-wrap">
            <table class="admin-table">
              <thead>
                <tr>
                  <th>{{ $t('catalog.formats.colType') }}</th>
                  <th class="admin-right">{{ $t('catalog.formats.colThickness') }}</th>
                  <th class="admin-right">{{ $t('catalog.formats.colSize') }}</th>
                  <th>{{ $t('catalog.formats.colSides') }}</th>
                  <th>{{ $t('catalog.formats.colStatus') }}</th>
                  <th><span class="sr-only">Amallar</span></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in formats" :key="row.id">
                  <td>
                    <span
                      class="admin-pill"
                      :class="row.type === 'kromka' ? 'admin-pill-info' : 'admin-pill-success'"
                    >
                      {{ decorTypeLabel(row.type) }}
                    </span>
                  </td>
                  <td class="admin-right admin-mono">{{ row.thickness_mm }} mm</td>
                  <td class="admin-right admin-mono">{{ formatSize(row) }}</td>
                  <!-- Only the board types record it; a tape or a plank has no
                       finished-face count to show. -->
                  <td class="text-sm font-bold text-ink">
                    {{
                      row.finished_sides === null
                        ? '—'
                        : $t(`catalog.finishedSides.${row.finished_sides}`)
                    }}
                  </td>
                  <td>
                    <span class="admin-pill" :class="materialStatusTone(row.status)">
                      {{
                        row.status === 'active'
                          ? materialStatusLabel(row.status)
                          : $t('catalog.formats.discontinued')
                      }}
                    </span>
                  </td>
                  <td>
                    <ActionMenu
                      :label="row.label"
                      :items="[
                        {
                          label:
                            row.status === 'active'
                              ? $t('catalog.formats.deactivate')
                              : $t('catalog.formats.activate'),
                          icon: row.status === 'active' ? 'ban' : 'check',
                          danger: row.status === 'active',
                        },
                      ]"
                      @select="toggleFormatStatus(row)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <p class="mt-3 text-xs text-ink-muted">{{ $t('catalog.formats.immutable') }}</p>
        </div>
      </section>

      <section class="admin-card mt-4">
        <div class="admin-card-h">
          <h2>Olib boradigan filiallar</h2>
          <span class="sub">{{ decor.branch_usage_count }} ta filial</span>
        </div>
        <div class="admin-card-b">
          <p v-if="decor.branch_usage_count === 0" class="text-sm font-bold text-ink-soft">
            Hech bir filial bu dekorni hali olib bormaydi.
          </p>
          <p v-else class="text-sm font-bold text-ink-soft">
            {{ decor.branch_usage_count }} ta filial bu dekorni olib boradi. Filiallar ro'yxati
            hozircha platforma API'sida ochilmagan.
          </p>
        </div>
      </section>
    </template>

    <!-- Create only, never edit: the shape rule and the natural key are both
         enforced server-side, and the fields the form shows follow the chosen
         type — kromka carries a tape width, a board carries a size, and only
         the board types carry a finished-face count. -->
    <AppModal :open="formOpen" :title="$t('catalog.formats.formTitle')" @close="formOpen = false">
      <form class="grid gap-3" @submit.prevent="submitFormat">
        <!-- FormSelect renders its own visible, persistent label. -->
        <FormSelect
          id="fmt-type"
          v-model="draftType"
          :label="$t('catalog.formats.type')"
          :options="typeOptions"
        />

        <label class="admin-field" for="fmt-thickness">
          <span>{{ $t('catalog.formats.thickness') }}</span>
          <input
            id="fmt-thickness"
            v-model="draft.thickness"
            class="mp-input"
            inputmode="decimal"
            :aria-invalid="formErrorField === 'thickness_mm' || undefined"
            :class="formErrorField === 'thickness_mm' ? '!border-danger' : ''"
          />
          <span v-if="chips.qalinliklar.length" class="mt-1 flex flex-wrap gap-1">
            <button
              v-for="value in chips.qalinliklar"
              :key="value"
              type="button"
              class="mp-filter-chip"
              @click="draft.thickness = value"
            >
              {{ value }}
            </button>
          </span>
        </label>

        <template v-if="draftIsTape">
          <label class="admin-field" for="fmt-tape">
            <span>{{ $t('catalog.formats.tapeWidth') }}</span>
            <input
              id="fmt-tape"
              v-model="draft.tapeWidth"
              class="mp-input"
              inputmode="numeric"
              :aria-invalid="formErrorField === 'tape_width_mm' || undefined"
              :class="formErrorField === 'tape_width_mm' ? '!border-danger' : ''"
            />
            <span v-if="chips.kromkaEnlar.length" class="mt-1 flex flex-wrap gap-1">
              <button
                v-for="value in chips.kromkaEnlar"
                :key="value"
                type="button"
                class="mp-filter-chip"
                @click="draft.tapeWidth = String(value)"
              >
                {{ value }}
              </button>
            </span>
          </label>
        </template>

        <template v-else>
          <div class="grid grid-cols-2 gap-3">
            <label class="admin-field" for="fmt-length">
              <span>{{ $t('catalog.formats.length') }}</span>
              <input
                id="fmt-length"
                v-model="draft.length"
                class="mp-input"
                inputmode="numeric"
                :aria-invalid="formErrorField === 'length_mm' || undefined"
                :class="formErrorField === 'length_mm' ? '!border-danger' : ''"
              />
            </label>
            <label class="admin-field" for="fmt-width">
              <span>{{ $t('catalog.formats.width') }}</span>
              <input
                id="fmt-width"
                v-model="draft.width"
                class="mp-input"
                inputmode="numeric"
                :aria-invalid="formErrorField === 'length_mm' || undefined"
              />
            </label>
          </div>
          <span v-if="chips.olchamlar.length" class="flex flex-wrap gap-1">
            <button
              v-for="size in chips.olchamlar"
              :key="`${size.length_mm}x${size.width_mm}`"
              type="button"
              class="mp-filter-chip"
              @click="applySizeChip(size)"
            >
              {{ size.length_mm }}×{{ size.width_mm }}
            </button>
          </span>

          <div v-if="needsFinishedSides" class="admin-field">
            <span id="fmt-sides-label">{{ $t('catalog.finishedSides.label') }}</span>
            <div class="flex gap-2" role="group" aria-labelledby="fmt-sides-label">
              <button
                v-for="sides in [1, 2]"
                :key="sides"
                type="button"
                class="mp-filter-chip"
                :class="
                  draft.finishedSides === sides
                    ? 'border-accent-tint bg-accent-soft text-accent-strong'
                    : undefined
                "
                :aria-pressed="draft.finishedSides === sides"
                @click="draft.finishedSides = sides"
              >
                {{ $t(`catalog.finishedSides.${sides}`) }}
              </button>
            </div>
            <span class="text-xs text-ink-muted">{{ $t('catalog.finishedSides.hint') }}</span>
          </div>
        </template>

        <p
          v-if="formError"
          class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          role="alert"
        >
          {{ formError }}
        </p>

        <div class="flex flex-wrap gap-2">
          <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
            {{ saving ? $t('catalog.formats.submit') + '…' : $t('catalog.formats.submit') }}
          </button>
          <button type="button" class="mp-button mp-button-outline" @click="formOpen = false">
            {{ $t('catalog.formats.cancel') }}
          </button>
        </div>
      </form>
    </AppModal>

    <ConfirmDialog
      :open="statusTarget !== null"
      :title="statusTarget === 'inactive' ? 'Faol emas qilish' : 'Faollashtirish'"
      :message="
        statusTarget === 'inactive'
          ? `${decor?.label} faol emas qilinadi — uni filiallarning yangi tanlovlaridan yashiriladi; mavjud buyurtmalarga ta'sir qilmaydi.`
          : `${decor?.label} faollashtiriladi va filial tanlovida ko'rinadi.`
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
