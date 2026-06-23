<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { formatDate } from '@/shared/formatters'
import { metres, useCuttingStore, type WorkshopCuttingPlanSummary } from '@/shared/stores/cutting'

const cutting = useCuttingStore()
const rolePath = useRolePath()

function panelCount(plan: WorkshopCuttingPlanSummary) {
  return Object.values(plan.panels_used_by_material).reduce((sum, count) => sum + count, 0)
}

onMounted(() => {
  void cutting.loadWorkshopPlans()
})
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="font-serif text-3xl font-semibold text-ink">Kesim rejalar</h1>
      <p class="mt-2 max-w-2xl text-base text-ink-soft">
        Ruxsatli filiallar bo'yicha tasdiqlangan buyurtma kesim chizmalari.
      </p>
    </div>

    <section class="mp-surface overflow-hidden">
      <div
        v-if="cutting.workshopLoading"
        class="p-5 text-sm font-bold text-ink-soft"
        aria-live="polite"
      >
        Kesim rejalar yuklanmoqda
      </div>
      <div v-else-if="cutting.error === 'permission_denied'" class="p-5">
        <div class="rounded-md bg-warning-soft p-4 text-warning">
          <div class="font-extrabold">Ruxsat yo'q</div>
          <p class="mt-1 text-sm">Bu akkaunt ustaxona kesim rejalarini ocha olmaydi.</p>
        </div>
      </div>
      <div v-else-if="cutting.error" class="p-5">
        <div class="rounded-md bg-danger-soft p-4 text-danger">
          <div class="font-extrabold">Kesim rejalarni yuklab bo'lmadi</div>
          <p class="mt-1 text-sm">trace {{ cutting.traceId ?? 'unavailable' }}</p>
        </div>
      </div>
      <div
        v-else-if="cutting.workshopPlans.length === 0"
        class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-6"
      >
        <h2 class="font-serif text-2xl font-semibold text-ink">Tasdiqlangan kesim reja yo'q</h2>
        <p class="mt-2 text-sm text-ink-soft">
          Buyurtmaga bog'langan rejalar buyurtma tasdiqlangandan keyin ko'rinadi.
        </p>
      </div>
      <div v-else class="divide-y divide-hairline">
        <article
          v-for="plan in cutting.workshopPlans"
          :key="plan.id"
          class="grid gap-4 p-5 md:grid-cols-[1fr_auto]"
        >
          <div>
            <h2 class="text-base font-extrabold text-ink">{{ plan.order_number }}</h2>
            <p v-if="plan.confirmed_at" class="mt-1 text-xs text-ink-muted">
              Tasdiqlangan: {{ formatDate(plan.confirmed_at) }}
            </p>
            <div class="mt-3 flex flex-wrap gap-2">
              <span class="mp-chip bg-success-soft text-success">
                <span class="mp-dot" aria-hidden="true"></span>
                tasdiqlangan
              </span>
              <span class="mp-chip">{{ panelCount(plan) }} panel</span>
              <span class="mp-chip">{{ metres(plan.total_edge_length_mm) }} krom</span>
              <span class="mp-chip">{{ plan.algorithm_name }}</span>
            </div>
          </div>
          <RouterLink
            :to="rolePath(`/workshop/cutting-plans/${plan.id}`)"
            class="mp-button mp-button-primary"
          >
            Ochish
          </RouterLink>
        </article>
      </div>
    </section>
  </section>
</template>
