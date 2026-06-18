<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { formatTiyin } from '@/shared/formatters'
import {
  useClientCatalogStore,
  type ClientBranch,
  type ClientBranchMaterial,
} from '@/shared/stores/clientCatalog'

const catalog = useClientCatalogStore()
const search = ref('')
const loadingMaterials = ref(false)
let searchTimer: number | undefined

const visibleBranches = computed(() => catalog.branches)

async function refreshBranches() {
  await catalog.loadBranches(search.value)
  loadingMaterials.value = true
  try {
    await Promise.all(
      catalog.branches.map((branch) => catalog.loadMaterialsForBranch(branch.branch_id)),
    )
  } finally {
    loadingMaterials.value = false
  }
}

function materialLabels(branchId: string) {
  const rows = catalog.materialsByBranch[branchId] ?? []
  return rows.map(materialTitle)
}

function materialTitle(material: ClientBranchMaterial) {
  const name = material.name.split('·')[0].trim()
  const price = formatTiyin(material.price_tiyin)
  return `${material.manufacturer_name} ${name} · ${price}/${material.display_unit}`
}

function hours(branch: ClientBranch) {
  const values = Object.values(branch.working_hours ?? {}).filter(
    (value): value is string => typeof value === 'string' && value.trim().length > 0,
  )
  return values[0] ?? "Ish vaqti ko'rsatilmagan"
}

watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void refreshBranches(), 250)
})

onMounted(refreshBranches)
</script>

<template>
  <section>
    <div class="client-page-head mb-2">
      <div>
        <h1>Ustaxonalar</h1>
        <p class="sub">Faol ustaxonalar va ularda mavjud materiallar.</p>
      </div>
    </div>

    <div class="client-banner info !mb-5">
      <span class="font-bold text-accent">i</span>
      <span>Bu ro'yxat shunchaki ma'lumot uchun. Buyurtma uchun chizmadan boshlang.</span>
    </div>

    <label class="mb-2 block text-sm font-bold text-ink" for="branch-search">Qidirish</label>
    <input
      id="branch-search"
      v-model="search"
      class="mp-input mb-5 max-w-[380px]"
      aria-label="Ustaxona yoki shahar nomi"
      placeholder="Ustaxona yoki shahar nomi bo'yicha qidirish..."
    />

    <div v-if="catalog.loading" class="grid gap-3" aria-live="polite">
      <div
        v-for="item in 4"
        :key="item"
        class="client-card grid grid-cols-[50px_1fr_auto] gap-4 p-5"
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

    <div v-else-if="catalog.error" class="client-error">
      <div class="client-error-icon">!</div>
      <h3>Ustaxonalarni yuklab bo'lmadi</h3>
      <p>Ulanishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.</p>
      <p class="client-trace">trace_id: {{ catalog.traceId ?? 'unavailable' }}</p>
      <button type="button" class="mp-button mp-button-outline mt-4" @click="refreshBranches">
        Qayta urinish
      </button>
    </div>

    <div v-else-if="visibleBranches.length === 0" class="client-empty">
      <div class="client-empty-icon">U</div>
      <h3>Ustaxona topilmadi</h3>
      <p>Qidiruv bo'yicha faol yoki vaqtincha yopiq ustaxona yo'q.</p>
    </div>

    <div v-else class="grid gap-3">
      <article
        v-for="branch in visibleBranches"
        :key="branch.branch_id"
        class="client-card grid grid-cols-[50px_minmax(0,1fr)_auto] items-center gap-4 p-5"
        :class="branch.status !== 'active' ? 'opacity-70' : ''"
      >
        <div
          class="grid size-[50px] place-items-center rounded-lg font-serif text-lg font-bold"
          :class="
            branch.status === 'active'
              ? 'bg-accent-tint text-accent'
              : 'bg-warning-soft text-warning'
          "
          aria-hidden="true"
        >
          {{ branch.branch_name.slice(0, 1).toUpperCase() }}
        </div>

        <div class="min-w-0">
          <h2 class="m-0 truncate font-serif text-lg font-semibold text-ink">
            {{ branch.workshop_name }} · {{ branch.branch_name }}
          </h2>
          <p class="mt-1 font-mono text-xs text-ink-muted">
            {{ branch.address }} · {{ hours(branch) }} · {{ branch.phone }}
          </p>
          <p v-if="loadingMaterials" class="mt-2 text-sm text-ink-soft">
            Materiallar yuklanmoqda...
          </p>
          <p
            v-else-if="materialLabels(branch.branch_id).length > 0"
            class="mt-2 text-sm text-ink-soft"
          >
            Materiallar:
            <b class="font-semibold text-ink">
              {{ materialLabels(branch.branch_id).slice(0, 4).join(' · ') }}
            </b>
            <span v-if="materialLabels(branch.branch_id).length > 4">
              +{{ materialLabels(branch.branch_id).length - 4 }}
            </span>
          </p>
          <p v-else class="mt-2 text-sm text-ink-soft">Ochiq materiallar ko'rsatilmagan.</p>
          <p v-if="branch.status !== 'active'" class="mt-2 text-sm font-bold text-warning">
            {{ branch.closed_reason ?? 'Vaqtincha yopiq' }}
          </p>
        </div>

        <span
          class="client-pill"
          :class="branch.status === 'active' ? 'client-pill-ready' : 'client-pill-info'"
        >
          {{ branch.status === 'active' ? 'Faol' : 'Vaqtincha yopiq' }}
        </span>
      </article>
    </div>
  </section>
</template>
