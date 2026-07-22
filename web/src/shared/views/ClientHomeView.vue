<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import {
  activeClientStatuses,
  clientGreetingName,
  draftDisplayName,
  clientHomeSubtitle,
  clientNextPhaseLabel,
  clientPhaseProgress,
  clientStatusLabel,
  clientStatusPillClass,
  formatPercent,
  formatRelativeDate,
} from '@/shared/app/clientUi'
import { useRolePath } from '@/shared/app/paths'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useCuttingStore, type CuttingDraft } from '@/shared/stores/cutting'
import { useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

const router = useRouter()
const rolePath = useRolePath()
const auth = useAuthStore()
const cutting = useCuttingStore()
const orders = useOrdersStore()

const activeOrders = computed(() =>
  orders.clientOrders.filter((order) => activeClientStatuses.includes(order.status)),
)
const readyOrders = computed(() => activeOrders.value.filter((order) => order.status === 'ready'))
const primaryReady = computed(() => readyOrders.value[0] ?? null)
const productionCount = computed(
  () =>
    activeOrders.value.filter(
      (order) => order.status === 'cutting' || order.status === 'edge_banding',
    ).length,
)
const recentDrafts = computed(() =>
  [...cutting.drafts]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 4),
)

const greetName = computed(() => clientGreetingName(auth.me))
const heading = computed(() => (greetName.value ? `Salom, ${greetName.value}` : 'Bosh sahifa'))
const subtitle = computed(() =>
  clientHomeSubtitle({
    ready: readyOrders.value.length,
    active: activeOrders.value.length,
    drafts: cutting.drafts.length,
  }),
)
// Nothing active and nothing saved → a single focused start state instead of a wall of zeros.
const isFirstRun = computed(() => activeOrders.value.length === 0 && cutting.drafts.length === 0)

const pageLoading = computed(() => cutting.loading || orders.loading)
const pageError = computed(() => cutting.error ?? orders.error)
const traceId = computed(() => cutting.traceId ?? orders.traceId)

function newCutting() {
  // Open the editor unsaved — the draft is created on the first optimise
  // (docs/ref/features/cutting.md). Nothing is persisted here.
  void router.push(rolePath('/c/cutting/new'))
}

function openOrder(id: string) {
  void router.push(rolePath(`/c/orders/${id}`))
}

function openDraft(draft: CuttingDraft) {
  const suffix = chosenResult(draft) ? '/result' : ''
  void router.push(rolePath(`/c/cutting/${draft.id}${suffix}`))
}

async function reloadHome() {
  await Promise.all([orders.loadClientOrders(), cutting.loadDrafts()])
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

const draftTitle = draftDisplayName

function currentAction(order: OrderSummary) {
  if (order.status === 'new') return 'Tafsilot'
  if (order.status === 'ready') return 'Olib ketish'
  return 'Kuzatish'
}

onMounted(() => {
  void reloadHome()
})
</script>

<template>
  <section>
    <div class="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-[26px] font-semibold leading-tight text-ink">{{ heading }}</h1>
        <p v-if="!pageLoading && !pageError && !isFirstRun" class="mt-1 text-sm text-ink-soft">
          {{ subtitle }}
        </p>
      </div>
      <!-- First-run shows a centred CTA in the empty state, so the header button
           would be redundant; it appears only once the dashboard has content and
           there's no other persistent "new draft" affordance. -->
      <button
        v-if="!isFirstRun"
        type="button"
        class="mp-button mp-button-primary"
        @click="newCutting"
      >
        <Icon name="plus" class="size-[18px]" /> Yangi kesim chizmasi
      </button>
    </div>

    <div
      v-if="pageLoading"
      class="grid grid-cols-3 gap-px overflow-hidden rounded-[14px] bg-hairline"
      aria-live="polite"
    >
      <span class="sr-only">Yuklanmoqda…</span>
      <div
        v-for="item in 3"
        :key="item"
        class="flex items-center gap-2.5 bg-elevated p-3 sm:gap-3 sm:p-4"
      >
        <div class="client-skeleton size-10 shrink-0"></div>
        <div class="min-w-0 flex-1">
          <div class="client-skeleton h-5 w-8"></div>
          <div class="client-skeleton mt-2 h-3 w-full max-w-20"></div>
        </div>
      </div>
    </div>

    <ClientErrorState
      v-else-if="pageError"
      title="Bosh sahifani yuklab bo'lmadi"
      :trace-id="traceId"
      @retry="reloadHome"
    />

    <div v-else-if="isFirstRun" class="client-empty">
      <div class="client-empty-icon"><Icon name="scissors" /></div>
      <h3>Birinchi chizmangizdan boshlang</h3>
      <p>
        Qism o'lchamlarini kiriting — tizim panellarga optimal joylashtiradi va ustaxona narxini
        hisoblaydi.
      </p>
      <button type="button" class="mp-button mp-button-primary mt-4" @click="newCutting">
        + Yangi chizma
      </button>
    </div>

    <template v-else>
      <div
        v-if="primaryReady"
        class="mb-5 flex flex-col gap-4 rounded-[14px] border border-accent-tint bg-accent-soft p-5 sm:flex-row sm:items-center sm:gap-5"
      >
        <span
          class="grid size-12 shrink-0 place-items-center rounded-[14px] border border-accent-tint bg-elevated text-accent"
        >
          <Icon name="check" />
        </span>
        <div class="min-w-0 flex-1">
          <div class="text-[11px] font-extrabold uppercase tracking-wider text-accent">
            Olishga tayyor
          </div>
          <div class="mt-0.5 font-mono text-lg font-bold text-ink">
            {{ primaryReady.order_number }}
          </div>
          <div class="mt-0.5 text-sm text-ink-muted">
            {{ primaryReady.branch_name }}
            <template v-if="readyOrders.length > 1">
              · yana {{ readyOrders.length - 1 }} ta tayyor</template
            >
          </div>
        </div>
        <div class="hidden self-stretch border-l border-accent-tint sm:block"></div>
        <div class="sm:text-right">
          <div class="text-[11px] font-bold text-ink-muted">Jami narx</div>
          <div class="mt-0.5 font-mono text-base font-bold text-ink">
            {{ formatTiyin(primaryReady.total_tiyin) }}
          </div>
        </div>
        <button
          type="button"
          class="mp-button mp-button-primary"
          @click="openOrder(primaryReady.id)"
        >
          <Icon name="box" class="size-[18px]" /> Olib ketish
        </button>
      </div>

      <div
        class="mb-6 grid grid-cols-3 overflow-hidden rounded-[14px] border border-hairline bg-elevated shadow-[0_1px_2px_rgb(15_27_45_/_4%)]"
      >
        <RouterLink
          :to="rolePath('/c/orders')"
          class="flex items-center gap-2.5 border-r border-hairline p-3 no-underline sm:gap-3 sm:p-4"
        >
          <span
            class="grid size-10 shrink-0 place-items-center rounded-[11px] bg-sunk text-ink-soft"
          >
            <Icon name="box" />
          </span>
          <span>
            <span class="block font-mono text-[22px] font-bold leading-none text-ink">{{
              activeOrders.length
            }}</span>
            <span class="mt-1 block text-xs font-semibold text-ink-muted">Faol buyurtma</span>
          </span>
        </RouterLink>
        <RouterLink
          :to="rolePath('/c/orders')"
          class="flex items-center gap-2.5 border-r border-hairline p-3 no-underline sm:gap-3 sm:p-4"
        >
          <span
            class="grid size-10 shrink-0 place-items-center rounded-[11px] bg-sunk text-ink-soft"
          >
            <Icon name="layers" />
          </span>
          <span>
            <span class="block font-mono text-[22px] font-bold leading-none text-ink">{{
              productionCount
            }}</span>
            <span class="mt-1 block text-xs font-semibold text-ink-muted">Ishlab chiqarishda</span>
          </span>
        </RouterLink>
        <RouterLink
          :to="rolePath('/c/cutting/drafts')"
          class="flex items-center gap-2.5 p-3 no-underline sm:gap-3 sm:p-4"
        >
          <span
            class="grid size-10 shrink-0 place-items-center rounded-[11px] bg-sunk text-ink-soft"
          >
            <Icon name="scissors" />
          </span>
          <span>
            <span class="block font-mono text-[22px] font-bold leading-none text-ink">{{
              cutting.drafts.length
            }}</span>
            <span class="mt-1 block text-xs font-semibold text-ink-muted">Saqlangan chizma</span>
          </span>
        </RouterLink>
      </div>

      <section class="mb-6">
        <div class="client-section-title">
          <h2>Faol buyurtmalar</h2>
          <RouterLink
            :to="rolePath('/c/orders')"
            class="text-sm font-bold text-ink-soft no-underline hover:text-ink"
          >
            Barchasi →
          </RouterLink>
        </div>

        <div v-if="activeOrders.length === 0" class="client-empty">
          <div class="client-empty-icon"><Icon name="box" /></div>
          <h3>Faol buyurtma yo'q</h3>
          <p>Saqlangan chizmangizdan buyurtma bering yoki yangisidan boshlang.</p>
          <button type="button" class="mp-button mp-button-primary mt-4" @click="newCutting">
            + Yangi chizma
          </button>
        </div>

        <div v-else class="grid gap-3">
          <article
            v-for="order in activeOrders"
            :key="order.id"
            class="client-card client-card-link grid cursor-pointer gap-3 p-4 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-tint sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1.4fr)_auto] sm:items-center sm:gap-5"
            :class="order.status === 'ready' ? 'border-accent-tint bg-accent-soft/40' : ''"
            role="link"
            tabindex="0"
            :aria-label="`${order.order_number} — ${order.branch_name}`"
            @click="openOrder(order.id)"
            @keydown.enter="openOrder(order.id)"
          >
            <div class="min-w-0">
              <div class="font-mono text-base font-bold text-ink">{{ order.order_number }}</div>
              <div class="mt-1 text-sm text-ink-muted">
                <b class="font-semibold text-ink">{{ order.branch_name }}</b> ·
                {{ formatRelativeDate(order.created_at) }}
              </div>
            </div>

            <div class="min-w-0">
              <div class="h-1.5 overflow-hidden rounded-full bg-hairline">
                <span
                  class="block h-full rounded-full bg-accent"
                  :style="{ width: `${clientPhaseProgress(order.status)}%` }"
                ></span>
              </div>
              <div class="mt-1.5 text-xs text-ink-muted">
                <template v-if="clientNextPhaseLabel(order.status)"
                  >Keyingi:
                  <b class="text-ink">{{ clientNextPhaseLabel(order.status) }}</b></template
                >
                <template v-else
                  >Joriy: <b class="text-ink">{{ clientStatusLabel[order.status] }}</b></template
                >
              </div>
            </div>

            <div class="flex items-center justify-between gap-3 sm:justify-end sm:gap-4">
              <span :class="clientStatusPillClass(order.status)">
                {{ clientStatusLabel[order.status] }}
              </span>
              <span class="font-mono text-sm font-bold text-ink">{{
                formatTiyin(order.total_tiyin)
              }}</span>
              <RouterLink
                :to="rolePath(`/c/orders/${order.id}`)"
                class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                @click.stop
              >
                {{ currentAction(order) }}
              </RouterLink>
            </div>
          </article>
        </div>
      </section>

      <section>
        <div class="client-section-title">
          <h2>Davom ettirish</h2>
          <RouterLink
            :to="rolePath('/c/cutting/drafts')"
            class="text-sm font-bold text-ink-soft no-underline hover:text-ink"
          >
            Barcha chizmalar →
          </RouterLink>
        </div>

        <div v-if="recentDrafts.length === 0" class="client-empty">
          <div class="client-empty-icon"><Icon name="scissors" /></div>
          <h3>Saqlangan chizma yo'q</h3>
          <p>Yangisini boshlang.</p>
          <button type="button" class="mp-button mp-button-primary mt-4" @click="newCutting">
            + Yangi chizma
          </button>
        </div>

        <div v-else class="grid gap-3">
          <article
            v-for="draft in recentDrafts"
            :key="draft.id"
            class="client-card client-card-link flex cursor-pointer items-center gap-3 p-4 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-tint"
            role="link"
            tabindex="0"
            :aria-label="draftTitle(draft)"
            @click="openDraft(draft)"
            @keydown.enter="openDraft(draft)"
          >
            <span
              class="grid size-10 shrink-0 place-items-center rounded-[11px] bg-sunk text-ink-soft"
            >
              <Icon name="scissors" />
            </span>
            <div class="min-w-0 flex-1">
              <div class="truncate font-mono text-sm font-bold text-ink">
                {{ draftTitle(draft) }}
              </div>
              <div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-muted">
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
                <span>{{ formatRelativeDate(draft.updated_at) }}</span>
              </div>
            </div>
            <RouterLink
              :to="rolePath(`/c/cutting/${draft.id}${chosenResult(draft) ? '/result' : ''}`)"
              class="mp-button mp-button-outline hidden min-h-9 shrink-0 px-3 text-xs sm:inline-flex"
              @click.stop
            >
              Davom etish →
            </RouterLink>
            <span class="shrink-0 font-bold text-accent sm:hidden" aria-hidden="true">→</span>
          </article>
        </div>
      </section>
    </template>
  </section>
</template>
