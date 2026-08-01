<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { useRolePath } from '@/shared/app/paths'
import { workshopDraftStatus, workshopErrorMessage } from '@/shared/app/workshopUi'
import { formatRelative } from '@/shared/formatters'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useCuttingStore, type WorkshopDraftSummary } from '@/shared/stores/cutting'
import { useWorkshopStore } from '@/shared/stores/workshop'

// The workshop's unfinished walk-in cuttings: staff started them for a walk-in
// but never placed the order. Saved indefinitely; resume opens the shared editor
// on the saved draft, which routes on to checkout once a result is chosen.
const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const workshop = useWorkshopStore()
const { t } = useI18n()

// A branch-scoped page (routes.ts declares `branchScope: 'branch'`): a draft is
// frozen to the branch it was started on, so the list follows the topbar branch
// exactly as the orders list does.
function loadDrafts() {
  return cutting.loadWorkshopDrafts(workshop.selectedBranchContext)
}

// Named only when the topbar actually offers a choice — a single-branch workshop
// hides the picker, so calling the branch out would be noise there.
const contextBranchName = computed(() => {
  if (workshop.branches.length < 2) return null
  return (
    workshop.branches.find((branch) => branch.id === workshop.selectedBranchContext)?.name ?? null
  )
})
const subtitle = computed(() =>
  contextBranchName.value
    ? t('cutting.drafts.subtitleBranch', { branch: contextBranchName.value })
    : t('cutting.drafts.subtitle'),
)
const emptyMessage = computed(() =>
  contextBranchName.value
    ? t('cutting.drafts.emptyBranch', { branch: contextBranchName.value })
    : t('cutting.drafts.empty'),
)

const pendingDelete = ref<WorkshopDraftSummary | null>(null)
const deleting = ref(false)
const deleteError = ref<string | null>(null)

const drafts = computed(() => cutting.workshopDrafts)

function draftLabel(draft: WorkshopDraftSummary): string {
  return draft.name?.trim() || draft.client_name || t('cutting.editor.untitled')
}

function openDraft(draft: WorkshopDraftSummary) {
  void router.push(rolePath(`/workshop/orders/cutting/${draft.id}`))
}

function newOrder() {
  void router.push(rolePath('/workshop/orders/new'))
}

async function confirmDelete() {
  const draft = pendingDelete.value
  if (!draft) return
  deleting.value = true
  deleteError.value = null
  try {
    await cutting.deleteDraft(draft.id)
    pendingDelete.value = null
    await loadDrafts()
  } catch (caught) {
    deleteError.value = workshopErrorMessage(apiErrorCode(caught))
  } finally {
    deleting.value = false
  }
}

onMounted(() => loadDrafts())

watch(
  () => workshop.selectedBranchContext,
  () => {
    void loadDrafts()
  },
)
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>{{ $t('cutting.drafts.title') }}</h1>
        <div class="sub">{{ subtitle }}</div>
      </div>
      <div class="tools">
        <RouterLink
          :to="rolePath('/workshop/orders')"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          ← {{ $t('cutting.drafts.backToOrders') }}
        </RouterLink>
        <button
          type="button"
          class="mp-button mp-button-primary min-h-9 px-3 text-xs"
          @click="newOrder"
        >
          + {{ $t('cutting.drafts.newOrder') }}
        </button>
      </div>
    </div>

    <section v-if="cutting.loading" class="grid gap-2" aria-live="polite">
      <div v-for="item in 3" :key="item" class="card p-4">
        <span class="sk-line w-1/2"></span>
        <span class="sk-line mt-3 w-4/5"></span>
      </div>
    </section>

    <section v-else-if="cutting.error" class="st-error" role="alert">
      <h3>{{ $t('cutting.drafts.loadErrorTitle') }}</h3>
      <p>{{ workshopErrorMessage(cutting.error) }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        @click="loadDrafts()"
      >
        {{ $t('cutting.action.retry') }}
      </button>
    </section>

    <section
      v-else-if="drafts.length === 0"
      class="card grid place-items-center gap-2 p-10 text-center"
    >
      <h3 class="text-base font-bold">{{ $t('cutting.drafts.emptyTitle') }}</h3>
      <p class="max-w-sm text-sm text-ink-soft">{{ emptyMessage }}</p>
      <button
        type="button"
        class="mp-button mp-button-primary mt-2 min-h-10 px-4"
        @click="newOrder"
      >
        + {{ $t('cutting.drafts.newOrder') }}
      </button>
    </section>

    <div v-else class="grid gap-2">
      <article
        v-for="draft in drafts"
        :key="draft.id"
        class="card grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 p-4"
      >
        <button type="button" class="min-w-0 text-left" @click="openDraft(draft)">
          <span class="flex flex-wrap items-center gap-2">
            <span class="truncate text-sm font-bold text-ink">{{ draftLabel(draft) }}</span>
            <span :class="workshopDraftStatus(draft.has_result).pill">
              {{ workshopDraftStatus(draft.has_result).label }}
            </span>
          </span>
          <span class="mt-1 block font-mono text-xs text-ink-muted">{{ draft.client_phone }}</span>
          <span class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
            <span v-if="draft.branch_name" class="text-ink-soft">{{ draft.branch_name }}</span>
            <span
              ><b class="font-mono text-ink">{{ draft.part_count }}</b>
              {{ $t('cutting.unit.part', draft.part_count) }}</span
            >
            <span v-if="draft.has_result">
              <b class="font-mono text-ink">{{ draft.panel_count || '—' }}</b>
              {{ $t('cutting.unit.panel', draft.panel_count) }}
            </span>
            <span>{{
              $t('cutting.drafts.editedAt', { time: formatRelative(draft.updated_at) })
            }}</span>
          </span>
        </button>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            @click="openDraft(draft)"
          >
            {{ $t('cutting.drafts.resume') }} →
          </button>
          <button
            type="button"
            class="grid size-9 place-items-center rounded-md border border-hairline text-lg text-ink-muted transition hover:border-danger hover:bg-danger-soft hover:text-danger"
            :aria-label="$t('cutting.drafts.deleteAria', { name: draftLabel(draft) })"
            @click="pendingDelete = draft"
          >
            ×
          </button>
        </div>
      </article>
    </div>

    <ConfirmDialog
      :open="pendingDelete !== null"
      :title="$t('cutting.editor.deleteDraft')"
      :message="
        $t('cutting.drafts.deleteMessage', {
          name: pendingDelete ? draftLabel(pendingDelete) : '',
        })
      "
      :confirm-label="$t('cutting.action.delete')"
      :busy-label="$t('cutting.action.deleting')"
      :cancel-label="$t('cutting.action.cancel')"
      :busy="deleting"
      danger
      @confirm="confirmDelete"
      @cancel="pendingDelete = null"
    >
      <p v-if="deleteError" class="mp-field-error">{{ deleteError }}</p>
    </ConfirmDialog>
  </section>
</template>
