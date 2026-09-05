<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'

import {
  activeClientStatuses,
  clientGreetingName,
  clientStatusLabel,
  clientStatusPillClass,
  draftDisplayName,
  formatPhone,
  formatRelativeDate,
  isClientPinned,
  workshopBranchName,
} from '@/shared/app/clientUi'
import { takeEntryToast } from '@/shared/app/clientEntry'
import { useRolePath } from '@/shared/app/paths'
import Icon from '@/shared/components/AppIcon.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatOrderNumber, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useClientEntryStore } from '@/shared/stores/clientEntry'
import { useCuttingStore, type CuttingDraft } from '@/shared/stores/cutting'
import { useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

/**
 * Home — "what needs attention now" (spec §3).
 *
 * Greeting, the **Ustaxonangiz** card with the page's one primary action under
 * it, the ready banner, at most four active orders and at most three drafts.
 * The count strip and the per-order progress bars are gone: the counts
 * overlapped (Tayyorlanmoqda ⊂ Faol) and were not tappable, and a bar with only
 * four positions said less than the status pill beside it.
 */
const { t } = useI18n()
const router = useRouter()
const rolePath = useRolePath()
const auth = useAuthStore()
const cutting = useCuttingStore()
const entry = useClientEntryStore()
const orders = useOrdersStore()
const toast = useToast()

const ACTIVE_ORDER_LIMIT = 4
const RECENT_DRAFT_LIMIT = 3

const activeOrders = computed(() =>
  orders.clientOrders.filter((order) => activeClientStatuses.includes(order.status)),
)
const visibleActiveOrders = computed(() => activeOrders.value.slice(0, ACTIVE_ORDER_LIMIT))
const readyOrders = computed(() => activeOrders.value.filter((order) => order.status === 'ready'))
const primaryReady = computed(() => readyOrders.value[0] ?? null)

const recentDrafts = computed(() =>
  [...cutting.drafts]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, RECENT_DRAFT_LIMIT),
)

const greetName = computed(() => clientGreetingName(auth.me))
const heading = computed(() =>
  greetName.value ? t('client.home.greeting', { name: greetName.value }) : t('client.home.title'),
)

const isPinned = computed(() => isClientPinned(auth.me))

/**
 * The pinned branch, resolved against Ustaxonalarim.
 *
 * `/auth/me` carries the two *names*, which is enough to title the card; the
 * address, the phone and the workshop id — the card links to that workshop's
 * profile — come from `my-workshops`, which the shell has already loaded. Until
 * it lands the card renders from the names alone rather than holding the page.
 */
const pinnedBranch = computed(() => {
  for (const workshop of entry.workshops) {
    const branch = workshop.branches.find((item) => item.is_pinned)
    if (branch) return { workshop, branch }
  }
  return null
})

/** Decision 16: one branch → the workshop name alone; several → «W · B». */
const workshopCardName = computed(() => {
  const resolved = pinnedBranch.value
  if (resolved) {
    return workshopBranchName(
      resolved.workshop.name,
      resolved.branch.name,
      resolved.workshop.branches.length,
    )
  }
  return workshopBranchName(auth.me?.pinned_workshop_name, auth.me?.pinned_branch_name)
})
const workshopInitial = computed(() =>
  (workshopCardName.value.trim().slice(0, 1) || 'M').toUpperCase(),
)
const workshopProfileTo = computed(() => {
  const id = pinnedBranch.value?.workshop.workshop_id
  return rolePath(id ? `/c/workshops/${id}` : '/c/branches')
})
/** A pill beside a workshop name reads as an order status, so only a closed
 *  branch earns one (§3 item 5). */
const branchClosed = computed(() => pinnedBranch.value?.branch.status === 'temporarily_closed')

const pageLoading = computed(() => cutting.draftsLoading || orders.loading)
/**
 * Stale-while-revalidate: the skeleton is for a cold home only. Coming back
 * from Buyurtmalar or Chizmalar the two lists are already in the store, so the
 * cards render straight away and the refresh happens under them — the page used
 * to blank on every return (client audit 2026-09-03).
 */
const hasListContent = computed(() => orders.clientOrders.length > 0 || cutting.drafts.length > 0)
const showSkeleton = computed(() => pageLoading.value && !hasListContent.value)
const pageError = computed(() => cutting.error ?? orders.error)
const traceId = computed(() => cutting.traceId ?? orders.traceId)
/** Pinned, nothing in flight and nothing saved — the start prompt (§3 item 6). */
const isFirstRun = computed(
  () => isPinned.value && activeOrders.value.length === 0 && cutting.drafts.length === 0,
)

function newCutting() {
  // Opened unsaved — the draft is created on the first optimise
  // (docs/ref/features/cutting.md). Nothing is persisted here.
  void router.push(rolePath('/c/cutting/new'))
}

// Always the parts editor, never straight to the result — same rule as the
// drafts list; the editor's "Davom etish" is what moves on to the result.
function openDraft(draft: CuttingDraft) {
  void router.push(rolePath(`/c/cutting/${draft.id}`))
}

async function reloadHome() {
  // The card's address, phone and workshop id come from Ustaxonalarim; the
  // shell primes it, and asking again here costs nothing when it is in hand.
  await Promise.all([orders.loadClientOrders(), cutting.loadDrafts(), entry.ensureMyWorkshops()])
}

function chosenResult(draft: CuttingDraft) {
  return (
    draft.results.find((result) => result.id === draft.chosen_result_id) ?? draft.results[0] ?? null
  )
}

function draftParts(draft: CuttingDraft) {
  return draft.parts_snapshot.reduce((sum, part) => sum + part.quantity, 0)
}

function draftPanels(draft: CuttingDraft) {
  const result = chosenResult(draft)
  if (!result) return 0
  return Object.values(result.panels_used_by_material).reduce((sum, count) => sum + count, 0)
}

function draftMeta(draft: CuttingDraft) {
  const parts = draftParts(draft)
  const panels = draftPanels(draft)
  return [
    `${parts} ${t('client.unit.part')}`,
    `${panels || '—'} ${t('client.unit.sheet')}`,
    formatRelativeDate(draft.updated_at),
  ].join(' · ')
}

const draftTitle = draftDisplayName

function orderAriaLabel(order: OrderSummary) {
  return `${formatOrderNumber(order.order_number)} — ${clientStatusLabel(order.status)}`
}

onMounted(() => {
  // One-time: the connected line names the workshop the client just entered.
  // Parked by the entry apply and read-and-cleared here, so a plain home load
  // never repeats it and a re-scan truthfully shows it again (spec §2.2/§8).
  const connectedTo = takeEntryToast()
  if (connectedTo) toast.success(t('client.entry.connected', { workshop: connectedTo }))
  void reloadHome()
})
</script>

<template>
  <section>
    <!-- The greeting alone: the pinned line under it read like a staff badge,
         and the counts line beside it went with the count strip (§3 item 1). -->
    <h1
      class="mb-2.5 font-display text-[22px] font-semibold leading-[1.15] tracking-[-0.02em] text-ink md:mb-4 md:text-[26px]"
    >
      {{ heading }}
    </h1>

    <!-- The card and its action are read off the principal, not off this page's
         two lists, so they stay put while those load or fail. -->
    <template v-if="isPinned">
      <!-- The label is a card caption on phones and a section heading on
           desktop — the same word in the shape each layout has room for. -->
      <div class="client-section-title hidden md:flex">
        <h2>{{ $t('client.home.yourWorkshop') }}</h2>
      </div>
      <RouterLink
        :to="workshopProfileTo"
        class="client-card client-card-link block p-3 no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 sm:p-3.5 md:p-5"
      >
        <div
          class="text-[12.5px] font-bold leading-[1.2] tracking-[0.01em] text-ink-muted md:hidden"
        >
          {{ $t('client.home.yourWorkshop') }}
        </div>
        <div class="mt-2 flex items-center gap-3 md:mt-0 md:gap-4">
          <AuthFileImage
            v-if="pinnedBranch?.workshop.logo_file_id"
            :file-id="pinnedBranch.workshop.logo_file_id"
            :alt="workshopCardName"
            size="sm"
            class="size-11 shrink-0 rounded-[14px] border border-hairline object-contain md:size-14 md:rounded-2xl"
          />
          <span
            v-else
            class="grid size-11 shrink-0 place-items-center rounded-[14px] bg-accent-soft font-display text-lg font-bold text-accent-strong md:size-14 md:rounded-2xl md:text-[22px]"
            aria-hidden="true"
          >
            {{ workshopInitial }}
          </span>
          <span class="flex min-w-0 flex-1 flex-col gap-0.5 md:gap-[3px]">
            <span class="flex min-w-0 flex-wrap items-center gap-2">
              <span
                class="min-w-0 truncate text-[15px] font-bold leading-[1.3] text-ink md:font-display md:text-[19px] md:tracking-[-0.02em]"
              >
                {{ workshopCardName }}
              </span>
              <span v-if="branchClosed" class="client-pill client-pill-info">
                {{ $t('client.workshops.closed') }}
              </span>
            </span>
            <span
              v-if="pinnedBranch"
              class="text-[12.5px] leading-[1.35] text-ink-muted md:text-sm md:leading-[1.45]"
            >
              {{ pinnedBranch.branch.address }}
            </span>
            <!-- Tap-to-call sits inside a card that is itself a link: the
                 anchor wins the tap on its own 44px row, the card takes the
                 rest. -->
            <a
              v-if="pinnedBranch"
              class="inline-flex min-h-11 items-center text-[13px] font-bold text-accent-deep underline underline-offset-2 md:min-h-9 md:text-sm"
              :href="`tel:${pinnedBranch.branch.phone}`"
              @click.stop
            >
              {{ formatPhone(pinnedBranch.branch.phone) }}
            </a>
          </span>
          <Icon name="chevron-right" class="size-[18px] shrink-0 text-ink-muted md:size-5" />
        </div>
      </RouterLink>

      <!-- Outside the card, because a card that is a link must not hold a
           second tap target (UX review 2026-09-05). -->
      <div class="mb-3 mt-2.5 md:mb-[22px] md:mt-3.5 md:flex md:justify-end">
        <button
          type="button"
          class="mp-button mp-button-primary min-h-[46px] w-full md:min-h-11 md:w-auto"
          @click="newCutting"
        >
          <Icon name="plus" class="size-[18px]" />
          {{ $t('client.home.newDrawing') }}
        </button>
      </div>
    </template>

    <!-- Un-pinned: no card, and no «Yangi chizma» anywhere on the page — a
         drawing needs a branch, so the one action opens Ustaxonalarim (§2.2). -->
    <template v-else>
      <div class="client-card flex items-start gap-3 p-3.5 md:p-5">
        <span
          class="grid size-10 shrink-0 place-items-center rounded-[10px] bg-sunk text-ink-muted"
          aria-hidden="true"
        >
          <Icon name="store" class="size-5" />
        </span>
        <span class="min-w-0 flex-1">
          <b class="block text-sm font-bold leading-[1.35] text-ink md:text-base">
            {{ $t('client.home.pickWorkshopTitle') }}
          </b>
          <span class="mt-[3px] block text-[12.5px] leading-[1.45] text-ink-muted md:text-sm">
            {{ $t('client.home.pickWorkshopBody') }}
          </span>
        </span>
      </div>
      <div class="mb-4 mt-3 md:mb-[22px] md:flex md:justify-end">
        <RouterLink
          :to="rolePath('/c/branches')"
          class="mp-button mp-button-primary min-h-[46px] w-full md:min-h-11 md:w-auto"
        >
          <Icon name="store" class="size-[17px]" />
          {{ $t('client.home.pickWorkshop') }}
        </RouterLink>
      </div>
    </template>

    <!-- Loading and error cover the two lists only; the card above is already
         on screen and must not blink. -->
    <div v-if="showSkeleton" class="grid gap-3" aria-live="polite">
      <span class="sr-only">{{ $t('client.common.loading') }}</span>
      <div class="flex items-center justify-between gap-3 border-b border-divider pb-2">
        <div class="client-skeleton h-[18px] w-[132px]"></div>
        <div class="client-skeleton h-[13px] w-16"></div>
      </div>
      <div class="client-card px-3.5">
        <div
          v-for="item in 3"
          :key="item"
          class="flex items-center justify-between gap-3 border-b border-divider py-3 last:border-b-0"
        >
          <div class="min-w-0 flex-1">
            <div class="client-skeleton h-3.5 w-24"></div>
            <div class="client-skeleton mt-1.5 h-3 w-32"></div>
          </div>
          <div class="shrink-0 text-right">
            <div class="client-skeleton ml-auto h-[19px] w-[88px] rounded-full"></div>
            <div class="client-skeleton ml-auto mt-1.5 h-3 w-[72px]"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Only when there is nothing else to show: a refresh that fails behind
         lists already on screen leaves them there rather than replacing a
         working page with an error card. -->
    <ClientErrorState
      v-else-if="pageError && !hasListContent"
      :title="$t('client.home.loadFailed')"
      :trace-id="traceId"
      @retry="reloadHome"
    />

    <template v-else>
      <!-- Information, not an action: «Olib ketdi» is the workshop's mark at
           the counter, so the whole banner is simply a link to the order. -->
      <RouterLink
        v-if="primaryReady"
        :to="rolePath(`/c/orders/${primaryReady.id}`)"
        class="mb-3 block rounded-[14px] border border-accent-tint bg-accent-soft p-3 no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 md:mb-[22px] md:p-5"
      >
        <span class="flex items-center gap-3 md:gap-5">
          <span
            class="grid size-[38px] shrink-0 place-items-center rounded-[11px] border border-accent-tint bg-elevated text-accent md:size-12 md:rounded-[14px]"
            aria-hidden="true"
          >
            <Icon name="check" class="size-5 md:size-6" />
          </span>
          <span class="min-w-0 flex-1">
            <span
              class="block text-[12.5px] font-bold leading-[1.2] text-accent-strong md:font-semibold"
            >
              {{ $t('client.home.readyTitle') }}
            </span>
            <span class="mt-0.5 block text-base font-bold leading-[1.25] text-ink md:text-lg">
              {{ formatOrderNumber(primaryReady.order_number) }}
            </span>
            <span class="mt-0.5 hidden text-sm text-ink-muted md:block">
              {{ workshopBranchName(primaryReady.workshop_name, primaryReady.branch_name) }}
              <template v-if="readyOrders.length > 1">
                · {{ $t('client.home.readyMore', readyOrders.length - 1) }}
              </template>
            </span>
          </span>
          <span class="hidden self-stretch border-l border-accent-tint md:block"></span>
          <span class="shrink-0 text-right">
            <span class="block text-[12.5px] font-bold leading-[1.2] text-ink-muted">
              {{ $t('client.home.totalPrice') }}
            </span>
            <span class="mt-0.5 block text-[15px] font-bold leading-[1.25] text-ink md:text-base">
              {{ formatTiyin(primaryReady.total_tiyin) }}
            </span>
          </span>
          <Icon name="chevron-right" class="size-[18px] shrink-0 text-accent-strong md:size-5" />
        </span>
        <span class="mt-2 block truncate text-[12.5px] text-ink-muted md:hidden">
          {{ workshopBranchName(primaryReady.workshop_name, primaryReady.branch_name) }}
          <template v-if="readyOrders.length > 1">
            · {{ $t('client.home.readyMore', readyOrders.length - 1) }}
          </template>
        </span>
      </RouterLink>

      <!-- Side by side on desktop, stacked on phones. An empty section is
           omitted rather than filled with a zero state: the card and its action
           above already carry the page. -->
      <!-- Dimmed, not replaced, while the lists revalidate — same affordance
           Buyurtmalar uses for a filter change. -->
      <div
        class="transition-opacity md:grid md:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)] md:items-start md:gap-6"
        :class="pageLoading && hasListContent ? 'opacity-60' : ''"
      >
        <section v-if="visibleActiveOrders.length > 0" class="mb-5 md:mb-0">
          <div class="client-section-title">
            <h2>{{ $t('client.home.activeOrders') }}</h2>
            <RouterLink
              :to="rolePath('/c/orders?status=active')"
              class="text-[13px] font-bold text-ink-soft no-underline hover:text-ink"
            >
              {{ $t('client.common.viewAll') }} →
            </RouterLink>
          </div>

          <div class="client-card">
            <RouterLink
              v-for="order in visibleActiveOrders"
              :key="order.id"
              :to="rolePath(`/c/orders/${order.id}`)"
              class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2.5 border-b border-divider px-3.5 py-[7px] no-underline last:border-b-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent md:grid-cols-[130px_minmax(0,1fr)_auto_auto] md:gap-x-[18px] md:px-5 md:py-3.5"
              :aria-label="orderAriaLabel(order)"
            >
              <!-- One row on desktop (number · name · pill · total); two on a
                 phone, where 390px has no room for four columns. -->
              <span class="row-start-1 text-sm font-bold leading-[1.35] text-ink md:text-[15px]">
                {{ formatOrderNumber(order.order_number) }}
              </span>
              <span
                :class="clientStatusPillClass(order.status)"
                class="row-start-1 justify-self-end md:col-start-3"
              >
                {{ clientStatusLabel(order.status) }}
              </span>
              <span
                class="row-start-2 min-w-0 truncate text-[12.5px] leading-[1.3] text-ink-muted md:col-start-2 md:row-start-1 md:text-sm"
              >
                {{ order.draft_name || '' }}
              </span>
              <span
                class="row-start-2 justify-self-end whitespace-nowrap text-[13px] font-bold leading-[1.3] text-ink md:col-start-4 md:row-start-1 md:min-w-[112px] md:text-right md:text-[15px]"
              >
                {{ formatTiyin(order.total_tiyin) }}
              </span>
            </RouterLink>
          </div>
        </section>

        <section v-if="recentDrafts.length > 0">
          <div class="client-section-title">
            <h2>{{ $t('client.home.continueDrafts') }}</h2>
            <RouterLink
              :to="rolePath('/c/cutting/drafts')"
              class="text-[13px] font-bold text-ink-soft no-underline hover:text-ink"
            >
              {{ $t('client.home.allDraftsCount', { n: cutting.drafts.length }) }} →
            </RouterLink>
          </div>

          <div class="client-card">
            <button
              v-for="draft in recentDrafts"
              :key="draft.id"
              type="button"
              class="flex w-full items-center gap-3 border-b border-divider px-3.5 py-[7px] text-left last:border-b-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent md:px-5 md:py-3.5"
              @click="openDraft(draft)"
            >
              <span
                class="grid size-8 shrink-0 place-items-center rounded-[10px] bg-sunk text-ink-soft md:size-10 md:rounded-[11px]"
                aria-hidden="true"
              >
                <Icon name="scissors" class="size-[17px] md:size-5" />
              </span>
              <span class="min-w-0 flex-1">
                <span
                  class="block truncate text-[13.5px] font-bold leading-[1.3] text-ink md:text-[15px] md:font-semibold"
                >
                  {{ draftTitle(draft) }}
                </span>
                <span
                  class="block truncate text-[12.5px] leading-[1.3] text-ink-muted md:text-[13px]"
                >
                  {{ draftMeta(draft) }}
                </span>
              </span>
              <span
                class="mp-button mp-button-outline hidden min-h-9 shrink-0 px-3 text-[12.5px] md:inline-flex"
              >
                {{ $t('client.common.continue') }} →
              </span>
              <Icon name="chevron-right" class="size-4 shrink-0 text-ink-muted md:hidden" />
            </button>
          </div>
        </section>
      </div>

      <!-- First run: the card and its action are above, so the prompt carries
           no second button (§3 item 6). -->
      <div v-if="isFirstRun" class="client-empty">
        <div class="client-empty-icon"><Icon name="scissors" /></div>
        <h3>{{ $t('client.home.firstRunTitle') }}</h3>
        <p>{{ $t('client.home.firstRunBody') }}</p>
      </div>
    </template>
  </section>
</template>
