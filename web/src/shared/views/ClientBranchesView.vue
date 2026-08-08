<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { formatPhone } from '@/shared/app/clientUi'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { yandexMapUrl } from '@/shared/app/yandexMapLink'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useClientCatalogStore, type ClientBranch } from '@/shared/stores/clientCatalog'

const catalog = useClientCatalogStore()
const search = ref('')
let searchTimer: number | undefined

const visibleBranches = computed(() => catalog.branches)

async function refreshBranches() {
  // One request now — the branch payload carries an inline material preview
  // (CB-13), so the old per-branch materials N+1 is gone.
  await catalog.loadBranches(search.value)
}

function mapUrl(branch: ClientBranch) {
  return yandexMapUrl(branch.latitude, branch.longitude)
}

/** Every published number, primary first — all of them tap-to-call (QAD-158). */
function phones(branch: ClientBranch) {
  return [branch.phone, ...(branch.additional_phones ?? [])]
}

watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void refreshBranches(), SEARCH_DEBOUNCE_MS)
})

onMounted(refreshBranches)
</script>

<template>
  <section>
    <div class="client-page-head mb-2">
      <div>
        <h1>{{ $t('client.branches.title') }}</h1>
        <p class="sub">{{ $t('client.branches.subtitle') }}</p>
      </div>
    </div>

    <div class="client-banner info !mb-5">
      <span class="font-bold text-ink">i</span>
      <span>{{ $t('client.branches.note') }}</span>
    </div>

    <label class="mb-2 block text-sm font-bold text-ink" for="branch-search">{{
      $t('client.common.search')
    }}</label>
    <div class="relative mb-5 max-w-[380px]">
      <span
        class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
        aria-hidden="true"
      >
        <Icon name="search" />
      </span>
      <input
        id="branch-search"
        v-model="search"
        class="mp-input pl-10"
        :aria-label="$t('client.branches.searchPlaceholder')"
        :placeholder="$t('client.branches.searchPlaceholder')"
      />
    </div>

    <div v-if="catalog.loading" class="grid gap-3" aria-live="polite">
      <div
        v-for="item in 4"
        :key="item"
        class="client-card grid grid-cols-[50px_minmax(0,1fr)_auto] gap-4 p-5 max-[480px]:grid-cols-[50px_minmax(0,1fr)]"
      >
        <div class="client-skeleton size-[50px]"></div>
        <div>
          <div class="client-skeleton h-4 w-1/3"></div>
          <div class="client-skeleton mt-3 h-3 w-2/3"></div>
          <div class="client-skeleton mt-3 h-3 w-4/5"></div>
        </div>
        <div class="client-skeleton h-6 w-16"></div>
      </div>
    </div>

    <ClientErrorState
      v-else-if="catalog.error"
      :title="$t('client.branches.loadFailed')"
      :trace-id="catalog.traceId"
      @retry="refreshBranches"
    />

    <div v-else-if="visibleBranches.length === 0" class="client-empty">
      <div class="client-empty-icon"><Icon name="store" /></div>
      <h3>{{ $t('client.branches.emptyTitle') }}</h3>
      <p>{{ $t('client.branches.emptyBody') }}</p>
    </div>

    <div v-else class="grid gap-3">
      <article
        v-for="branch in visibleBranches"
        :key="branch.branch_id"
        class="client-card grid grid-cols-[50px_minmax(0,1fr)_auto] items-center gap-4 p-5 max-[480px]:grid-cols-[50px_minmax(0,1fr)]"
        :class="branch.status !== 'active' ? 'bg-sunk' : ''"
      >
        <div
          class="grid size-[50px] place-items-center rounded-lg font-display text-lg font-bold"
          :class="
            branch.status === 'active'
              ? 'bg-accent-tint text-accent-strong'
              : 'bg-warning-soft text-warning'
          "
          aria-hidden="true"
        >
          {{ branch.branch_name.slice(0, 1).toUpperCase() }}
        </div>

        <div class="min-w-0">
          <h2 class="m-0 truncate font-display text-lg font-semibold text-ink">
            {{ branch.workshop_name }} · {{ branch.branch_name }}
          </h2>
          <p class="mt-1 text-xs text-ink-muted">{{ branch.address }}</p>
          <!-- Only when the branch has a pin — an address alone does not get a
               client to the door in a city where the same street repeats. -->
          <!-- A pin icon that opens Yandex Maps, not an embedded map: this is a
               list, and a map per card would mount a Leaflet instance and a
               tile round-trip for every branch on screen. -->
          <a
            v-if="mapUrl(branch)"
            :href="mapUrl(branch) ?? undefined"
            target="_blank"
            rel="noopener noreferrer"
            class="mt-1 grid size-11 place-items-center rounded-md border border-hairline text-accent-deep transition hover:border-hairline-strong hover:bg-sunk"
            :title="$t('client.branches.openMap')"
            :aria-label="$t('client.branches.openMap')"
          >
            <Icon name="map-pin" class="size-[18px]" />
          </a>
          <p class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            <a
              v-for="(phone, index) in phones(branch)"
              :key="phone"
              class="inline-flex min-h-11 items-center text-xs font-bold text-accent-deep underline underline-offset-2"
              :href="`tel:${phone}`"
            >
              {{ formatPhone(phone) }}
              <span
                v-if="index === 0 && phones(branch).length > 1"
                class="ml-1 font-sans text-[11px] text-ink-muted"
              >
                {{ $t('client.branches.primaryPhone') }}
              </span>
            </a>
          </p>
          <p v-if="branch.status !== 'active'" class="mt-2 text-sm font-bold text-warning">
            {{ branch.closed_reason ?? $t('client.branches.closed') }}
          </p>
        </div>

        <span
          class="client-pill max-[480px]:col-span-2 max-[480px]:mt-1 max-[480px]:justify-self-start"
          :class="branch.status === 'active' ? 'client-pill-ready' : 'client-pill-info'"
        >
          {{
            branch.status === 'active' ? $t('client.branches.active') : $t('client.branches.closed')
          }}
        </span>
      </article>
    </div>
  </section>
</template>
