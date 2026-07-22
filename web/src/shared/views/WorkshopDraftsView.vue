<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { useRolePath } from '@/shared/app/paths'
import { workshopDraftStatus, workshopErrorMessage } from '@/shared/app/workshopUi'
import { formatRelativeUz } from '@/shared/formatters'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useCuttingStore, type WorkshopDraftSummary } from '@/shared/stores/cutting'

// The workshop's unfinished walk-in cuttings: staff started them for a walk-in
// but never placed the order. Saved indefinitely; resume opens the shared editor
// on the saved draft, which routes on to checkout once a result is chosen.
const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()

const pendingDelete = ref<WorkshopDraftSummary | null>(null)
const deleting = ref(false)
const deleteError = ref<string | null>(null)

const drafts = computed(() => cutting.workshopDrafts)

function draftLabel(draft: WorkshopDraftSummary): string {
  return draft.name?.trim() || draft.client_name || 'Nomsiz chizma'
}

function wastePercent(draft: WorkshopDraftSummary): string | null {
  if (draft.waste_percentage === null) return null
  return `${(draft.waste_percentage * 100).toFixed(1)}%`
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
    await cutting.loadWorkshopDrafts()
  } catch (caught) {
    deleteError.value = workshopErrorMessage(apiErrorCode(caught))
  } finally {
    deleting.value = false
  }
}

onMounted(() => cutting.loadWorkshopDrafts())
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Saqlangan chizmalar</h1>
        <div class="sub">Tugallanmagan mijoz chizmalari — davom eting yoki o'chiring.</div>
      </div>
      <div class="tools">
        <RouterLink
          :to="rolePath('/workshop/orders')"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          ← Buyurtmalar
        </RouterLink>
        <button
          type="button"
          class="mp-button mp-button-primary min-h-9 px-3 text-xs"
          @click="newOrder"
        >
          + Yangi buyurtma
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
      <h3>Chizmalarni yuklab bo'lmadi</h3>
      <p>{{ workshopErrorMessage(cutting.error) }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        @click="cutting.loadWorkshopDrafts()"
      >
        Qayta urinish
      </button>
    </section>

    <section
      v-else-if="drafts.length === 0"
      class="card grid place-items-center gap-2 p-10 text-center"
    >
      <h3 class="text-base font-bold">Saqlangan chizma yo'q</h3>
      <p class="max-w-sm text-sm text-ink-soft">
        Tugallanmagan chizmalar shu yerda saqlanadi. "+ Yangi buyurtma" orqali mijoz uchun chizma
        boshlang.
      </p>
      <button
        type="button"
        class="mp-button mp-button-primary mt-2 min-h-10 px-4"
        @click="newOrder"
      >
        + Yangi buyurtma
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
              ><b class="font-mono text-ink">{{ draft.part_count }}</b> qism</span
            >
            <span v-if="draft.has_result">
              <b class="font-mono text-ink">{{ draft.panel_count || '—' }}</b> panel
            </span>
            <span v-if="wastePercent(draft)">
              <b class="font-mono text-ink">{{ wastePercent(draft) }}</b> chiqim
            </span>
            <span>{{ formatRelativeUz(draft.updated_at) }} · tahrirlangan</span>
          </span>
        </button>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            @click="openDraft(draft)"
          >
            Davom etish →
          </button>
          <button
            type="button"
            class="grid size-9 place-items-center rounded-md border border-hairline text-lg text-ink-muted transition hover:border-danger hover:bg-danger-soft hover:text-danger"
            :aria-label="`${draftLabel(draft)} chizmasini o'chirish`"
            @click="pendingDelete = draft"
          >
            ×
          </button>
        </div>
      </article>
    </div>

    <ConfirmDialog
      :open="pendingDelete !== null"
      title="Chizmani o'chirish"
      :message="`${pendingDelete ? draftLabel(pendingDelete) : ''} chizmasi butunlay o'chiriladi. Bu amal qaytarilmaydi.`"
      confirm-label="O'chirish"
      busy-label="O'chirilmoqda"
      cancel-label="Bekor qilish"
      :busy="deleting"
      danger
      @confirm="confirmDelete"
      @cancel="pendingDelete = null"
    >
      <p v-if="deleteError" class="mp-field-error">{{ deleteError }}</p>
    </ConfirmDialog>
  </section>
</template>
