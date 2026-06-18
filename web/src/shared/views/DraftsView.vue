<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiErrorCode, apiTraceId } from '@/shared/api/client'
import {
  clientErrorLabel,
  formatPercent,
  formatRelativeDate,
  pluralUz,
} from '@/shared/app/clientUi'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useCuttingStore, type CuttingDraft } from '@/shared/stores/cutting'

const DRAFT_CAP = 50

const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const creating = ref(false)
const createError = ref<string | null>(null)
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

function materialName(draft: CuttingDraft, materialId: string) {
  const snapshot = chosenResult(draft)?.material_snapshots[materialId]
  return typeof snapshot?.name === 'string' ? snapshot.name.split('·')[0].trim() : null
}

function draftTitle(draft: CuttingDraft) {
  const materials = [
    ...new Set(
      draft.parts_snapshot
        .map((part) => materialName(draft, part.material_id))
        .filter((value): value is string => Boolean(value)),
    ),
  ]
  const label =
    materials.slice(0, 2).join(' + ') + (materials.length > 2 ? ` +${materials.length - 2}` : '')
  return `${draft.id.slice(0, 8)} · ${label || 'Material tanlanmagan'}`
}

async function newCutting() {
  creating.value = true
  createError.value = null
  try {
    const draft = await cutting.createDraft()
    await router.push(rolePath(`/c/cutting/${draft.id}`))
  } catch (errorValue) {
    createError.value = clientErrorLabel(apiErrorCode(errorValue), "Chizma yaratib bo'lmadi.")
  } finally {
    creating.value = false
  }
}

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

// Resolve a draft's preferred-branch label for the row chip (CB-88). Branch
// options are loaded client-side; no per-draft fetch.
function branchName(draft: CuttingDraft): string | null {
  if (!draft.preferred_branch_id) return null
  const branch = cutting.branchOptions.find((row) => row.branch_id === draft.preferred_branch_id)
  return branch ? `${branch.workshop_name} · ${branch.branch_name}` : null
}

onMounted(() => {
  void cutting.loadDrafts()
  void cutting.loadBranchOptions()
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
      <button
        type="button"
        class="mp-button mp-button-primary"
        :disabled="creating"
        @click="newCutting"
      >
        {{ creating ? 'Yaratilmoqda' : 'Yangi chizma' }}
      </button>
    </div>

    <div v-if="createError" class="client-banner danger mb-4" role="alert">
      <span class="font-mono font-black">!</span>
      <span>{{ createError }}</span>
    </div>

    <div class="client-section-title">
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
        Yangi chizma
      </button>
    </div>

    <div v-else class="grid gap-2">
      <article
        v-for="draft in sortedDrafts"
        :key="draft.id"
        class="client-card grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 p-4 transition hover:border-ink"
      >
        <button type="button" class="min-w-0 text-left" @click="openDraft(draft)">
          <span class="block truncate text-sm font-bold text-ink">{{ draftTitle(draft) }}</span>
          <span v-if="branchName(draft)" class="client-pill client-pill-info mt-1 inline-block">
            {{ branchName(draft) }}
          </span>
          <span class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
            <span
              ><b class="font-mono text-ink">{{ draftParts(draft) }}</b> qism</span
            >
            <span
              ><b class="font-mono text-ink">{{ draftPanels(draft) || '—' }}</b> panel</span
            >
            <span v-if="chosenResult(draft)">
              <b class="font-mono text-ink">{{
                formatPercent(chosenResult(draft)?.waste_percentage)
              }}</b>
              chiqim
            </span>
            <span>{{ formatRelativeDate(draft.updated_at) }} · tahrirlangan</span>
          </span>
        </button>
        <div class="flex items-center gap-2">
          <button type="button" class="font-bold text-accent" @click="openDraft(draft)">
            Ochish →
          </button>
          <button
            type="button"
            class="grid size-8 place-items-center rounded-md border border-hairline text-ink-muted transition hover:border-danger hover:bg-danger-soft hover:text-danger"
            :disabled="deletingId === draft.id"
            aria-label="Chizmani o'chirish"
            @click="requestDeleteDraft(draft)"
          >
            ×
          </button>
        </div>
      </article>
      <p class="sr-only">{{ pluralUz(sortedDrafts.length, 'chizma') }}</p>
    </div>

    <ConfirmDialog
      :open="Boolean(draftPendingDelete)"
      title="Chizmani o'chirish"
      :message="`${pendingDeletePartCount} qismli chizma butunlay o'chiriladi. Bu amal qaytarilmaydi.`"
      confirm-label="O'chirish"
      danger
      :busy="deletingId !== null"
      @cancel="closeDeleteDialog"
      @confirm="confirmDeleteDraft"
    >
      <p v-if="deleteError" class="text-sm font-bold text-danger">
        {{ deleteError }} · trace {{ deleteTraceId ?? 'unavailable' }}
      </p>
    </ConfirmDialog>
  </section>
</template>
