<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import ClientBranchRow from '@/apps/client/components/ClientBranchRow.vue'
import Icon from '@/shared/components/AppIcon.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useClientEntryStore } from '@/shared/stores/clientEntry'

/**
 * A workshop's own profile — `/c/workshops/:workshopId` (spec §6.1).
 *
 * Only for **related** workshops: the set `/client/my-workshops` returns (entry
 * rows ∪ the pinned branch's workshop ∪ order/draft history). Any other id
 * renders the not-found state — this is not a directory, and the platform's
 * "no cross-workshop storefront" rule is what that enforces.
 *
 * The head is the name and nothing else: no badge, no drawing action. The pin
 * is a branch, so the star and both actions live on the branch rows.
 */
const route = useRoute()
const rolePath = useRolePath()
const entry = useClientEntryStore()

const workshopId = computed(() => String(route.params.workshopId ?? ''))
const workshop = computed(
  () => entry.workshops.find((item) => item.workshop_id === workshopId.value) ?? null,
)
const branches = computed(() => workshop.value?.branches ?? [])

/**
 * Decision 16: a one-branch workshop's single row is titled by the *workshop*
 * name — the branch name never appears. Several branches, and each row is
 * titled by its own.
 */
function rowTitle(branchName: string): string {
  if (branches.value.length === 1) return workshop.value?.name ?? branchName
  return branchName
}

function reload() {
  void entry.loadMyWorkshops()
}

onMounted(() => {
  void entry.ensureMyWorkshops()
})
</script>

<template>
  <section>
    <div v-if="entry.workshopsLoading && !workshop" class="grid gap-3" aria-live="polite">
      <span class="sr-only">{{ $t('client.common.loading') }}</span>
      <div class="client-card p-3.5">
        <div class="flex items-center gap-3">
          <div class="client-skeleton size-13 rounded-[14px]"></div>
          <div class="client-skeleton h-5 w-2/5"></div>
        </div>
      </div>
      <div class="client-card p-3.5">
        <div class="client-skeleton h-4 w-1/3"></div>
        <div class="client-skeleton mt-3 h-4 w-3/4"></div>
        <div class="client-skeleton mt-3 h-10 w-1/2"></div>
      </div>
    </div>

    <ClientErrorState
      v-else-if="entry.workshopsError"
      :title="$t('client.workshops.loadFailed')"
      :trace-id="entry.workshopsTraceId"
      @retry="reload"
    />

    <!-- Not one of the client's own workshops (or gone since the list loaded).
         The standard not-found view, not an error: nothing failed. -->
    <div v-else-if="!workshop" class="client-empty">
      <div class="client-empty-icon"><Icon name="store" /></div>
      <h3>{{ $t('client.workshop.notFoundTitle') }}</h3>
      <p>{{ $t('client.workshop.notFoundBody') }}</p>
      <RouterLink :to="rolePath('/c/branches')" class="mp-button mp-button-primary mt-4">
        {{ $t('client.workshops.title') }}
      </RouterLink>
    </div>

    <template v-else>
      <div class="client-card mb-3 p-3.5 sm:p-5">
        <div class="flex items-center gap-3">
          <AuthFileImage
            v-if="workshop.logo_file_id"
            :file-id="workshop.logo_file_id"
            :alt="workshop.name"
            size="sm"
            class="size-13 rounded-[14px] border border-hairline object-contain"
          />
          <span
            v-else
            class="grid size-13 shrink-0 place-items-center rounded-[14px] bg-accent-soft font-display text-[21px] font-bold text-accent-strong"
            aria-hidden="true"
          >
            {{ workshop.name.slice(0, 1).toUpperCase() }}
          </span>
          <!-- Phones carry the page name in the compact header, so this H2 is
               the workshop's identity rather than a duplicate page title. -->
          <h2
            class="m-0 min-w-0 truncate font-display text-xl font-bold tracking-[-0.02em] text-ink"
          >
            {{ workshop.name }}
          </h2>
        </div>
      </div>

      <div class="client-section-title">
        <h2>{{ $t('client.workshop.branches') }}</h2>
      </div>

      <ul v-if="branches.length > 0" class="client-card m-0 list-none p-0">
        <ClientBranchRow
          v-for="branch in branches"
          :key="branch.id"
          :branch="branch"
          :workshop-id="workshop.workshop_id"
          :public-code="workshop.public_code"
          :title="rowTitle(branch.name)"
        />
      </ul>
      <p v-else class="client-card p-5 text-sm text-ink-muted">
        {{ $t('client.workshops.noBranches') }}
      </p>
    </template>
  </section>
</template>
