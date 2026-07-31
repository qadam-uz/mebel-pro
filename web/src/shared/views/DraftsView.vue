<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { apiErrorCode, apiTraceId } from '@/shared/api/client'
import {
  clientErrorLabel,
  draftDisplayName,
  formatRelativeDate,
  pluralUz,
} from '@/shared/app/clientUi'
import { traceSuffix } from '@/shared/app/errorTrace'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useCuttingStore, type CuttingDraft } from '@/shared/stores/cutting'

const DRAFT_CAP = 50

const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const deletingId = ref<string | null>(null)
const draftPendingDelete = ref<CuttingDraft | null>(null)
const deleteError = ref<string | null>(null)
const deleteTraceId = ref<string | null>(null)

const sortedDrafts = computed(() =>
  [...cutting.drafts].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  ),
)
const pendingDeletePartCount = computed(() => draftParts(draftPendingDelete.value))

function chosenResult(draft: CuttingDraft | null) {
  if (!draft) return null
  return (
    draft.results.find((result) => result.id === draft.chosen_result_id) ?? draft.results[0] ?? null
  )
}

function draftParts(draft: CuttingDraft | null) {
  return draft?.parts_snapshot.reduce((sum, part) => sum + part.quantity, 0) ?? 0
}

function draftPanels(draft: CuttingDraft) {
  const result = chosenResult(draft)
  if (!result) return 0
  return Object.values(result.panels_used_by_material).reduce((sum, count) => sum + count, 0)
}

const draftTitle = draftDisplayName

function newCutting() {
  // Open the editor unsaved — the draft is created on the first optimise
  // (docs/ref/features/cutting.md). Nothing is persisted here.
  void router.push(rolePath('/c/cutting/new'))
}

// Always the parts editor, never straight to the result: opening a draft means
// looking at what is in it. The editor's own "Davom etish" carries on to the
// cutting result when one already exists.
function openDraft(draft: CuttingDraft) {
  void router.push(rolePath(`/c/cutting/${draft.id}`))
}

function requestDeleteDraft(draft: CuttingDraft) {
  draftPendingDelete.value = draft
}

function closeDeleteDialog() {
  draftPendingDelete.value = null
  deleteError.value = null
  deleteTraceId.value = null
}

async function confirmDeleteDraft() {
  const draft = draftPendingDelete.value
  if (!draft) return
  deletingId.value = draft.id
  deleteError.value = null
  deleteTraceId.value = null
  try {
    await cutting.deleteDraft(draft.id)
    draftPendingDelete.value = null
  } catch (errorValue) {
    // Keep the dialog open and surface the reason instead of leaking an
    // unhandled rejection (CB-24).
    deleteError.value = clientErrorLabel(apiErrorCode(errorValue), "Chizmani o'chirib bo'lmadi.")
    deleteTraceId.value = apiTraceId(errorValue)
  } finally {
    deletingId.value = null
  }
}

onMounted(() => {
  void cutting.loadDrafts()
})
</script>

<template>
  <section>
    <div class="client-page-head">
      <div>
        <h1>Saqlangan chizmalar</h1>
        <p class="sub">
          Saqlangan chizmani oching yoki yangi chizma boshlang. Chizmalar muddatsiz saqlanadi.
        </p>
      </div>
      <button type="button" class="mp-button mp-button-primary" @click="newCutting">
        + Yangi chizma
      </button>
    </div>

    <div v-if="cutting.loading || sortedDrafts.length > 0" class="client-section-title">
      <h2>Hammasi</h2>
      <span v-if="cutting.loading" class="client-skeleton inline-block h-4 w-20"></span>
      <span v-else class="font-mono text-sm text-ink-muted">
        <b class="text-ink">{{ sortedDrafts.length }}</b> / {{ DRAFT_CAP }} chizma
      </span>
    </div>

    <div v-if="cutting.loading" class="grid gap-2" aria-live="polite">
      <div v-for="item in 3" :key="item" class="client-card grid grid-cols-[1fr_auto] gap-4 p-4">
        <div>
          <div class="client-skeleton h-4 w-1/2"></div>
          <div class="client-skeleton mt-3 h-3 w-4/5"></div>
        </div>
        <div class="client-skeleton h-4 w-16"></div>
      </div>
    </div>

    <ClientErrorState
      v-else-if="cutting.error"
      title="Chizmalarni yuklab bo'lmadi"
      :trace-id="cutting.traceId"
      @retry="cutting.loadDrafts"
    />

    <div v-else-if="sortedDrafts.length === 0" class="client-empty">
      <div class="client-empty-icon"><Icon name="scissors" /></div>
      <h3>Saqlangan chizma yo'q</h3>
      <p>Saqlangan chizma yo'q — yangisini boshlang.</p>
      <button type="button" class="mp-button mp-button-primary mt-4" @click="newCutting">
        + Yangi chizma
      </button>
    </div>

    <div v-else class="grid gap-3">
      <!-- Same card as the home "Chizmalar" section, plus the delete control —
           the two lists show the same object and had drifted into two shapes. -->
      <article
        v-for="draft in sortedDrafts"
        :key="draft.id"
        class="client-card client-card-link flex cursor-pointer items-center gap-3 p-4 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-tint"
        role="link"
        tabindex="0"
        :aria-label="draftTitle(draft)"
        @click="openDraft(draft)"
        @keydown.enter="openDraft(draft)"
      >
        <span class="grid size-10 shrink-0 place-items-center rounded-[11px] bg-sunk text-ink-soft">
          <Icon name="scissors" />
        </span>
        <div class="min-w-0 flex-1">
          <div class="truncate font-mono text-sm font-bold text-ink">
            {{ draftTitle(draft) }}
          </div>
          <div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-muted">
            <span
              ><b class="font-mono text-ink">{{ draftParts(draft) }}</b> detal</span
            >
            <span
              ><b class="font-mono text-ink">{{ draftPanels(draft) || '—' }}</b> list</span
            >
            <span>{{ formatRelativeDate(draft.updated_at) }}</span>
          </div>
        </div>
        <RouterLink
          :to="rolePath(`/c/cutting/${draft.id}`)"
          class="mp-button mp-button-outline hidden min-h-9 shrink-0 px-3 text-xs sm:inline-flex"
          @click.stop
        >
          Davom etish →
        </RouterLink>
        <!-- `.stop` so deleting never doubles as opening the card behind it. -->
        <button
          type="button"
          class="grid size-9 shrink-0 place-items-center rounded-md border border-hairline text-lg text-ink-muted transition hover:border-danger hover:bg-danger-soft hover:text-danger"
          :disabled="deletingId === draft.id"
          aria-label="Chizmani o'chirish"
          @click.stop="requestDeleteDraft(draft)"
        >
          ×
        </button>
      </article>
      <p class="sr-only">{{ pluralUz(sortedDrafts.length, 'chizma') }}</p>
    </div>

    <ConfirmDialog
      :open="Boolean(draftPendingDelete)"
      title="Chizmani o'chirish"
      :message="`${pendingDeletePartCount} detalli chizma butunlay o'chiriladi. Bu amal qaytarilmaydi.`"
      confirm-label="O'chirish"
      cancel-label="Bekor qilish"
      danger
      :busy="deletingId !== null"
      @cancel="closeDeleteDialog"
      @confirm="confirmDeleteDraft"
    >
      <p v-if="deleteError" class="text-sm font-bold text-danger">
        {{ deleteError }}{{ traceSuffix(deleteTraceId) }}
      </p>
    </ConfirmDialog>
  </section>
</template>
