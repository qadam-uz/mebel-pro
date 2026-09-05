<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import ClientBranchRow from '@/apps/client/components/ClientBranchRow.vue'
import Icon from '@/shared/components/AppIcon.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useClientEntryStore, type ClientWorkshop } from '@/shared/stores/clientEntry'

/**
 * **Ustaxonalarim** — the client's own workshops (spec §2.2, §6.1).
 *
 * Every workshop the client has entered, is pinned to, or has an order or a
 * drawing with — pinned workshop first. One card each: the head links to that
 * workshop's profile, and under it the same branch rows the profile renders,
 * carrying the pin star, «Yangi chizma» and «Katalog». No path from here to a
 * list of every workshop on the platform, which this page replaced.
 */
const entry = useClientEntryStore()
const router = useRouter()
const rolePath = useRolePath()

const workshops = computed(() => entry.workshops)

/**
 * Decision 16 / the mockup: a one-branch workshop is named by the card head, so
 * its single row carries no title of its own and starts at the address.
 */
function rowTitle(workshop: ClientWorkshop, branchName: string): string | null {
  return workshop.branches.length === 1 ? null : branchName
}

function refresh() {
  void entry.loadMyWorkshops()
}

function openProfile(workshop: ClientWorkshop) {
  void router.push(rolePath(`/c/workshops/${workshop.workshop_id}`))
}

onMounted(() => {
  void entry.ensureMyWorkshops()
})
</script>

<template>
  <section>
    <!-- §2: one title per phone screen — the compact header already names this
         page, so the body opens on the sub-line rather than a second H1. The
         desktop header has no page name, so it keeps one. -->
    <div class="client-page-head mb-4 hidden md:flex">
      <div>
        <h1>{{ $t('client.workshops.title') }}</h1>
        <p class="sub">{{ $t('client.workshops.subtitle') }}</p>
      </div>
    </div>
    <p class="mb-3 text-[13px] leading-[1.45] text-ink-soft md:hidden">
      {{ $t('client.workshops.subtitle') }}
    </p>

    <div
      v-if="entry.workshopsLoading && workshops.length === 0"
      class="grid gap-3"
      aria-live="polite"
    >
      <span class="sr-only">{{ $t('client.common.loading') }}</span>
      <div v-for="item in 2" :key="item" class="client-card p-3.5">
        <div class="flex items-center gap-3">
          <div class="client-skeleton size-11 rounded-[14px]"></div>
          <div class="client-skeleton h-5 w-1/3"></div>
        </div>
        <div class="client-skeleton mt-4 h-4 w-2/3"></div>
        <div class="client-skeleton mt-3 h-10 w-1/2"></div>
      </div>
    </div>

    <ClientErrorState
      v-else-if="entry.workshopsError"
      :title="$t('client.workshops.loadFailed')"
      :trace-id="entry.workshopsTraceId"
      @retry="refresh"
    />

    <!-- First run: nothing entered, nothing pinned, no history. The app is
         joined through a workshop's own link, so say exactly that — there is no
         action here that could invent a workshop. -->
    <div v-else-if="workshops.length === 0" class="client-empty">
      <div class="client-empty-icon"><Icon name="store" /></div>
      <h3>{{ $t('client.workshops.emptyTitle') }}</h3>
      <p>{{ $t('client.workshops.emptyBody') }}</p>
    </div>

    <div v-else class="grid gap-3">
      <section v-for="workshop in workshops" :key="workshop.workshop_id" class="client-card">
        <div
          class="client-card-link flex cursor-pointer items-center gap-3 rounded-t-[14px] px-3.5 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent sm:px-5 sm:py-4"
          role="link"
          tabindex="0"
          @click="openProfile(workshop)"
          @keydown.enter="openProfile(workshop)"
          @keydown.space.prevent="openProfile(workshop)"
        >
          <AuthFileImage
            v-if="workshop.logo_file_id"
            :file-id="workshop.logo_file_id"
            :alt="workshop.name"
            size="sm"
            class="size-11 rounded-[14px] border border-hairline object-contain"
          />
          <span
            v-else
            class="grid size-11 shrink-0 place-items-center rounded-[14px] font-display text-lg font-bold"
            :class="
              workshop.is_pinned ? 'bg-accent-soft text-accent-strong' : 'bg-sunk text-ink-soft'
            "
            aria-hidden="true"
          >
            {{ workshop.name.slice(0, 1).toUpperCase() }}
          </span>
          <h2
            class="m-0 min-w-0 flex-1 truncate font-display text-[17px] font-bold tracking-[-0.02em] text-ink"
          >
            {{ workshop.name }}
          </h2>
          <Icon name="chevron-right" class="size-[18px] shrink-0 text-ink-muted" />
        </div>

        <ul class="m-0 list-none border-t border-divider p-0">
          <ClientBranchRow
            v-for="branch in workshop.branches"
            :key="branch.id"
            :branch="branch"
            :workshop-id="workshop.workshop_id"
            :public-code="workshop.public_code"
            :title="rowTitle(workshop, branch.name)"
          />
          <li
            v-if="workshop.branches.length === 0"
            class="px-3.5 py-4 text-sm text-ink-muted sm:px-5"
          >
            {{ $t('client.workshops.noBranches') }}
          </li>
        </ul>
      </section>
    </div>
  </section>
</template>
