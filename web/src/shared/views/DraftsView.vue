<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useCuttingStore, type CuttingDraft } from '@/shared/stores/cutting'

const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const creating = ref(false)
const deletingId = ref<string | null>(null)
const draftPendingDelete = ref<CuttingDraft | null>(null)

const sortedDrafts = computed(() =>
  [...cutting.drafts].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  ),
)

function draftSummary(draft: CuttingDraft) {
  const parts = draft.parts_snapshot.reduce((sum, part) => sum + part.quantity, 0)
  const panels = draft.results.find((result) => result.id === draft.chosen_result_id)
  const panelCount = panels
    ? Object.values(panels.panels_used_by_material).reduce((sum, count) => sum + count, 0)
    : 0
  if (parts === 0) return 'No parts yet'
  return `${parts} parts${panelCount ? ` · ${panelCount} panels` : ''}`
}

function dateLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

async function newCutting() {
  creating.value = true
  try {
    const draft = await cutting.createDraft()
    await router.push(rolePath(`/c/cutting/${draft.id}`))
  } finally {
    creating.value = false
  }
}

const pendingDeletePartCount = computed(
  () => draftPendingDelete.value?.parts_snapshot.reduce((sum, part) => sum + part.quantity, 0) ?? 0,
)

function requestDeleteDraft(draft: CuttingDraft) {
  draftPendingDelete.value = draft
}

async function confirmDeleteDraft() {
  const draft = draftPendingDelete.value
  if (!draft) return
  deletingId.value = draft.id
  try {
    await cutting.deleteDraft(draft.id)
    draftPendingDelete.value = null
  } finally {
    deletingId.value = null
  }
}

onMounted(() => {
  void cutting.loadDrafts()
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Cutting drafts</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Saved client cuttings with their branch context and latest result.
        </p>
      </div>
      <button
        type="button"
        class="mp-button mp-button-primary"
        :disabled="creating"
        @click="newCutting"
      >
        {{ creating ? 'Creating' : 'New cutting' }}
      </button>
    </div>

    <section class="mp-surface overflow-hidden">
      <div v-if="cutting.loading" class="space-y-3 p-5" aria-live="polite">
        <div class="h-5 w-40 animate-pulse rounded bg-sunk"></div>
        <div class="h-16 w-full animate-pulse rounded bg-sunk"></div>
        <div class="h-16 w-full animate-pulse rounded bg-sunk"></div>
      </div>

      <div v-else-if="cutting.error" class="p-5">
        <div class="rounded-md bg-danger-soft p-4 text-danger">
          <div class="font-extrabold">Drafts could not be loaded</div>
          <p class="mt-1 text-sm">trace {{ cutting.traceId ?? 'unavailable' }}</p>
          <button
            type="button"
            class="mp-button mp-button-outline mt-4"
            @click="cutting.loadDrafts"
          >
            Retry
          </button>
        </div>
      </div>

      <div
        v-else-if="sortedDrafts.length === 0"
        class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-6"
      >
        <span class="mp-chip bg-warning-soft text-warning">
          <span class="mp-dot" aria-hidden="true"></span>
          Empty
        </span>
        <h2 class="mt-5 font-serif text-2xl font-semibold">No cutting drafts</h2>
        <p class="mt-2 max-w-xl text-base text-ink-soft">
          Start a draft, add panel parts, and run the optimiser when the list is ready.
        </p>
      </div>

      <div v-else class="divide-y divide-hairline">
        <article
          v-for="draft in sortedDrafts"
          :key="draft.id"
          class="grid gap-4 p-5 md:grid-cols-[1fr_auto]"
        >
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="text-base font-extrabold text-ink">{{ draftSummary(draft) }}</h2>
              <span v-if="draft.preferred_branch_id" class="mp-chip bg-info-soft text-info">
                <span class="mp-dot" aria-hidden="true"></span>
                preferred branch
              </span>
              <span v-if="draft.chosen_result_id" class="mp-chip bg-success-soft text-success">
                <span class="mp-dot" aria-hidden="true"></span>
                optimized
              </span>
            </div>
            <p class="mt-1 font-mono text-xs text-ink-muted">
              edited {{ dateLabel(draft.updated_at) }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <RouterLink
              :to="rolePath(`/c/cutting/${draft.id}`)"
              class="mp-button mp-button-primary"
            >
              Open
            </RouterLink>
            <button
              type="button"
              class="mp-button mp-button-outline text-danger"
              :disabled="deletingId === draft.id"
              @click="requestDeleteDraft(draft)"
            >
              {{ deletingId === draft.id ? 'Deleting' : 'Delete' }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <ConfirmDialog
      :open="Boolean(draftPendingDelete)"
      title="Delete draft"
      :message="`Delete this draft with ${pendingDeletePartCount} parts? This cannot be undone.`"
      confirm-label="Delete draft"
      danger
      :busy="deletingId !== null"
      @cancel="draftPendingDelete = null"
      @confirm="confirmDeleteDraft"
    />
  </section>
</template>
