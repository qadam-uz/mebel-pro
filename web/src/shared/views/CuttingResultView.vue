<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import {
  clientCuttingEditorAdapter,
  type CuttingEditorAdapterFactory,
} from '@/shared/app/cuttingEditorAdapter'
import { traceLine } from '@/shared/app/errorTrace'
import { useRolePath } from '@/shared/app/paths'
import CuttingResultsSection from '@/shared/components/CuttingResultsSection.vue'
import { useToast } from '@/shared/composables/useToast'
import { useCuttingStore } from '@/shared/stores/cutting'

const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const toast = useToast()
const { t } = useI18n()
const adapter = (
  (route.meta.cuttingEditorAdapter as CuttingEditorAdapterFactory | undefined) ??
  clientCuttingEditorAdapter
)()

const draftId = computed(() => String(route.params.id))
const draft = computed(() => cutting.currentDraft)
const activePanelId = ref<string | null>(null)
const revisionOrderId = computed(() => draft.value?.revision_of_order_id ?? null)
const branchId = computed(
  () => draft.value?.preferred_branch_id ?? adapter.branch.fixed?.id ?? null,
)
const checkoutPath = computed(() => {
  const current = draft.value
  if (!current) return adapter.paths.drafts
  if (current.revision_of_order_id && adapter.orderRevision) {
    return adapter.orderRevision.reviewPath(current.id)
  }
  return adapter.paths.checkout(current.id)
})

onMounted(async () => {
  try {
    await cutting.loadDraft(draftId.value)
    const loaded = cutting.currentDraft
    if (!loaded) return
    const chosen =
      loaded.results.find((result) => result.id === loaded.chosen_result_id) ??
      loaded.results[0] ??
      null
    if (!chosen) {
      toast.warn(t('cutting.result.optimizeFirst'))
      await router.replace(rolePath(adapter.paths.editor(loaded.id)))
      return
    }
    activePanelId.value = chosen.panels[0]?.id ?? null
  } catch {
    // The store owns the retryable error state rendered below.
  }
})
</script>

<template>
  <section>
    <RouterLink
      :to="rolePath(adapter.paths.editor(draftId))"
      class="mp-button mp-button-outline mb-3 min-h-9 px-3 text-xs"
    >
      <span aria-hidden="true">←</span>
      {{ $t('cutting.result.editParts') }}
    </RouterLink>

    <section v-if="cutting.loading" class="grid gap-3" aria-live="polite">
      <div class="client-skeleton h-28"></div>
      <div class="client-skeleton h-80"></div>
    </section>

    <section v-else-if="cutting.error" class="client-error">
      <div class="client-error-icon">!</div>
      <h3>{{ $t('cutting.result.loadErrorTitle') }}</h3>
      <p>{{ $t('cutting.result.loadErrorBody') }}</p>
      <p class="client-trace">{{ traceLine(cutting.traceId) }}</p>
    </section>

    <CuttingResultsSection
      v-else-if="draft && draft.results.length > 0"
      :draft="draft"
      :optimize-error="null"
      :checkout-path="checkoutPath"
      :checkout-label="revisionOrderId ? $t('cutting.result.saveChanges') : undefined"
      :branch-id="branchId"
      :quote-for-draft="adapter.quoteForDraft"
      v-model:active-panel-id="activePanelId"
    />
  </section>
</template>
