<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import {
  activeClientStatuses,
  clientPhaseIndex,
  clientPhaseLabels,
  clientStatusLabel,
  clientStatusPillClass,
  formatPercent,
  formatRelativeDate,
  pluralUz,
} from '@/shared/app/clientUi'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useRolePath } from '@/shared/app/paths'
import { formatTiyin } from '@/shared/formatters'
import { useCuttingStore, type CuttingDraft } from '@/shared/stores/cutting'
import { useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const orders = useOrdersStore()

const activeOrders = computed(() =>
  orders.clientOrders.filter((order) => activeClientStatuses.includes(order.status)),
)
const recentDrafts = computed(() =>
  [...cutting.drafts]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 4),
)
const productionCount = computed(
  () =>
    activeOrders.value.filter(
      (order) => order.status === 'cutting' || order.status === 'edge_banding',
    ).length,
)
const readyCount = computed(
  () => activeOrders.value.filter((order) => order.status === 'ready').length,
)
const pageLoading = computed(() => cutting.loading || orders.loading)
const pageError = computed(() => cutting.error ?? orders.error)
const traceId = computed(() => cutting.traceId ?? orders.traceId)

function newCutting() {
  // Open the editor unsaved — the draft is created on the first optimise
  // (docs/ref/features/cutting.md). Nothing is persisted here.
  void router.push(rolePath('/c/cutting/new'))
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

function draftTitle(draft: CuttingDraft) {
  const materials = [
    ...new Set(
      draft.parts_snapshot
        .map((part) => resultMaterialName(draft, part.material_id))
        .filter((value): value is string => Boolean(value)),
    ),
  ]
  const label =
    materials.slice(0, 2).join(' + ') + (materials.length > 2 ? ` +${materials.length - 2}` : '')
  return `${draft.id.slice(0, 8)} · ${label || 'Material tanlanmagan'}`
}

function resultMaterialName(draft: CuttingDraft, materialId: string) {
  const result = chosenResult(draft)
  const snapshot = result?.material_snapshots[materialId]
  return typeof snapshot?.name === 'string' ? snapshot.name.split('·')[0].trim() : null
}

function currentAction(order: OrderSummary) {
  if (order.status === 'new') return 'Tafsilot'
  if (order.status === 'ready') return 'Olishga tayyor'
  return 'Kuzatish'
}

function stepNodeClass(order: OrderSummary, index: number) {
  const current = clientPhaseIndex(order.status)
  if (index < current) return 'done'
  if (index === current) return 'cur'
  return ''
}

onMounted(() => {
  void reloadHome()
})
</script>

<template>
  <section>
    <div class="mb-5 flex flex-wrap items-center justify-between gap-4">
      <h1 class="font-serif text-[26px] font-semibold leading-tight text-ink">Bosh sahifa</h1>
      <button type="button" class="mp-button mp-button-primary" @click="newCutting">
        Yangi kesim chizmasi
      </button>
    </div>

    <div v-if="pageLoading" class="grid gap-3 md:grid-cols-4" aria-live="polite">
      <div v-for="item in 4" :key="item" class="client-card flex items-center gap-3 p-4">
        <div class="client-skeleton size-9"></div>
        <div class="flex-1">
          <div class="client-skeleton h-5 w-10"></div>
          <div class="client-skeleton mt-2 h-3 w-24"></div>
        </div>
      </div>
    </div>

    <ClientErrorState
      v-else-if="pageError"
      title="Bosh sahifani yuklab bo'lmadi"
      :trace-id="traceId"
      @retry="reloadHome"
    />

    <template v-else>
      <div class="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <RouterLink
          :to="rolePath('/c/orders')"
          class="client-card flex items-center gap-3 p-4 no-underline transition hover:border-ink"
        >
          <span
            class="grid size-9 place-items-center rounded-lg bg-sunk font-mono font-bold text-ink-soft"
            >B</span
          >
          <span>
            <span class="block font-mono text-[22px] font-bold leading-none text-ink">{{
              activeOrders.length
            }}</span>
            <span class="mt-1 block text-xs font-semibold text-ink-muted">Faol buyurtma</span>
          </span>
        </RouterLink>
        <RouterLink
          :to="rolePath('/c/orders')"
          class="client-card flex items-center gap-3 p-4 no-underline transition hover:border-ink"
        >
          <span
            class="grid size-9 place-items-center rounded-lg bg-sunk font-mono font-bold text-ink-soft"
            >I</span
          >
          <span>
            <span class="block font-mono text-[22px] font-bold leading-none text-ink">{{
              productionCount
            }}</span>
            <span class="mt-1 block text-xs font-semibold text-ink-muted">Ishlab chiqarishda</span>
          </span>
        </RouterLink>
        <RouterLink
          :to="rolePath('/c/orders')"
          class="client-card flex items-center gap-3 p-4 no-underline transition hover:border-ink"
          :class="readyCount > 0 ? 'border-accent-tint bg-accent-soft' : ''"
        >
          <span
            class="grid size-9 place-items-center rounded-lg bg-accent-soft font-mono font-bold text-accent"
            >T</span
          >
          <span>
            <span
              class="block font-mono text-[22px] font-bold leading-none"
              :class="readyCount > 0 ? 'text-accent' : 'text-ink'"
              >{{ readyCount }}</span
            >
            <span class="mt-1 block text-xs font-semibold text-ink-muted">Olishga tayyor</span>
          </span>
        </RouterLink>
        <RouterLink
          :to="rolePath('/c/cutting/drafts')"
          class="client-card flex items-center gap-3 p-4 no-underline transition hover:border-ink"
        >
          <span
            class="grid size-9 place-items-center rounded-lg bg-sunk font-mono font-bold text-ink-soft"
            >C</span
          >
          <span>
            <span class="block font-mono text-[22px] font-bold leading-none text-ink">{{
              cutting.drafts.length
            }}</span>
            <span class="mt-1 block text-xs font-semibold text-ink-muted">Saqlangan chizma</span>
          </span>
        </RouterLink>
      </div>

      <div
        class="mb-5 flex flex-wrap items-center justify-between gap-4 rounded-[10px] bg-accent px-5 py-4 text-white shadow-[0_4px_10px_-3px_rgb(15_27_45_/_18%)]"
      >
        <div>
          <div class="font-serif text-lg font-semibold">Yangi kesim chizmasi</div>
          <div class="mt-1 text-sm opacity-85">
            Qism o'lchamlarini kiriting — tizim panellarga optimal joylashtiradi va ustaxona narxini
            hisoblaydi.
          </div>
        </div>
        <button
          type="button"
          class="mp-button bg-white text-accent hover:bg-white"
          @click="newCutting"
        >
          Boshlash
        </button>
      </div>

      <div class="grid items-start gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <section>
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
            <p>Hali buyurtma bermagansiz — chizmadan boshlang.</p>
            <button type="button" class="mp-button mp-button-primary mt-4" @click="newCutting">
              Yangi chizma
            </button>
          </div>

          <div v-else class="grid gap-3">
            <article
              v-for="order in activeOrders"
              :key="order.id"
              class="client-card cursor-pointer p-4 transition hover:border-ink focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-tint"
              role="link"
              tabindex="0"
              :aria-label="`${order.order_number} — ${order.branch_name}`"
              @click="router.push(rolePath(`/c/orders/${order.id}`))"
              @keydown.enter="router.push(rolePath(`/c/orders/${order.id}`))"
            >
              <div class="flex items-start justify-between gap-3">
                <div>
                  <h3 class="m-0 font-mono text-base font-bold text-ink">
                    {{ order.order_number }}
                  </h3>
                  <div class="mt-1 text-sm text-ink-muted">
                    <b class="font-semibold text-ink">{{ order.branch_name }}</b> ·
                    {{ formatRelativeDate(order.created_at) }}
                  </div>
                </div>
                <span :class="clientStatusPillClass(order.status)">
                  {{ clientStatusLabel[order.status] }}
                </span>
              </div>

              <div class="my-4 flex items-center">
                <template v-for="(label, index) in clientPhaseLabels" :key="label">
                  <span class="flex shrink-0 flex-col items-center gap-1">
                    <span
                      class="size-3 rounded-full border-2"
                      :class="
                        stepNodeClass(order, index) === 'done'
                          ? 'border-accent bg-accent'
                          : stepNodeClass(order, index) === 'cur'
                            ? 'border-accent bg-elevated shadow-[0_0_0_4px_rgb(15_118_110_/_28%)]'
                            : 'border-hairline bg-elevated'
                      "
                    ></span>
                    <span
                      class="hidden whitespace-nowrap text-[10px] font-semibold text-ink-muted sm:block"
                    >
                      {{ label }}
                    </span>
                  </span>
                  <span
                    v-if="index < 4"
                    class="mb-5 h-0.5 flex-1 rounded bg-hairline sm:mb-[22px]"
                    :class="index < clientPhaseIndex(order.status) ? 'bg-accent' : ''"
                  ></span>
                </template>
              </div>

              <div
                class="flex flex-wrap items-center justify-between gap-3 border-t border-hairline pt-3"
              >
                <div class="font-mono text-sm font-bold text-ink">
                  {{ formatTiyin(order.total_tiyin) }}
                  <small class="font-sans text-xs font-medium text-ink-muted">jami narx</small>
                </div>
                <RouterLink
                  :to="rolePath(`/c/orders/${order.id}`)"
                  class="mp-button mp-button-primary min-h-8 px-3 text-xs"
                  @click.stop
                >
                  {{ currentAction(order) }}
                </RouterLink>
              </div>
            </article>
          </div>
        </section>

        <aside>
          <div class="client-section-title">
            <h2>So'nggi chizmalar</h2>
            <RouterLink
              :to="rolePath('/c/cutting/drafts')"
              class="text-sm font-bold text-ink-soft no-underline hover:text-ink"
            >
              Barchasi →
            </RouterLink>
          </div>

          <div v-if="recentDrafts.length === 0" class="client-empty">
            <div class="client-empty-icon"><Icon name="scissors" /></div>
            <h3>Saqlangan chizma yo'q</h3>
            <p>Yangisini boshlang.</p>
            <button type="button" class="mp-button mp-button-primary mt-4" @click="newCutting">
              Yangi chizma
            </button>
          </div>

          <div v-else class="grid gap-2">
            <article
              v-for="draft in recentDrafts"
              :key="draft.id"
              class="client-card grid cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-3 p-4 transition hover:border-ink focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-tint"
              role="link"
              tabindex="0"
              :aria-label="draftTitle(draft)"
              @click="router.push(rolePath(`/c/cutting/${draft.id}`))"
              @keydown.enter="router.push(rolePath(`/c/cutting/${draft.id}`))"
            >
              <div class="min-w-0">
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
              <span class="font-bold text-accent" aria-hidden="true">→</span>
            </article>
          </div>
          <p class="sr-only">{{ pluralUz(recentDrafts.length, 'chizma') }}</p>
        </aside>
      </div>
    </template>
  </section>
</template>
