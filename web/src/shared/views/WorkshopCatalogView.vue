<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { branchOptions } from '@/shared/app/workshopUi'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { formatStockQuantity, formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import type { MaterialKind, MaterialStatus } from '@/shared/stores/admin'
import { useWorkshopStore } from '@/shared/stores/workshop'

const rolePath = useRolePath()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const selectedBranchId = ref('')
const statusFilter = ref<'all' | MaterialStatus>('all')
const kindFilter = ref<'all' | MaterialKind>('all')
const search = ref('')

const canUseCatalog = computed(
  () =>
    auth.me?.is_owner === true ||
    (auth.me?.grants ?? []).some((grant) => grant.permission === 'manage_catalog'),
)
const accessibleBranches = computed(() =>
  auth.me?.is_owner === true
    ? workshop.branches
    : workshop.branches.filter((branch) =>
        (auth.me?.grants ?? []).some(
          (grant) => grant.branch_id === branch.id && grant.permission === 'manage_catalog',
        ),
      ),
)
const branchFilterOptions = computed(() =>
  branchOptions(
    accessibleBranches.value,
    auth.me?.is_owner ? 'Barcha filiallar' : 'Mening filiallarim',
  ),
)
const statusOptions = [
  { value: 'all', label: 'Hammasi', meta: 'barcha holatlar', status: 'active' as const },
  { value: 'active', label: 'Faol', meta: 'mijozlarga ko‘rinadi', status: 'active' as const },
  {
    value: 'inactive',
    label: 'Faol emas',
    meta: 'mijozlardan yashirilgan',
    status: 'blocked' as const,
  },
]
const kindOptions = [
  { value: 'all', label: 'Barcha turlar', meta: 'panel va krom', status: 'active' as const },
  { value: 'panel', label: 'Panel', meta: 'dona/panel narxi', status: 'active' as const },
  { value: 'edge', label: 'Krom', meta: 'metr narxi', status: 'active' as const },
]
const selectedBranch = computed(
  () => accessibleBranches.value.find((branch) => branch.id === selectedBranchId.value) ?? null,
)
const filteredRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  return workshop.branchMaterials.filter((row) => {
    if (query && !row.material.name.toLowerCase().includes(query)) return false
    return true
  })
})

function materialMeta(row: (typeof workshop.branchMaterials)[number]) {
  const material = row.material
  if (material.kind === 'edge') return `krom · ${material.thickness_mm} mm · ${material.color}`
  return `${material.type?.toUpperCase() ?? 'panel'} · ${material.thickness_mm} mm · ${material.color} · ${material.panel_length_mm}x${material.panel_width_mm}`
}

function priceUnit(kind: MaterialKind) {
  return kind === 'edge' ? '/ metr' : '/ panel'
}

async function refreshCatalog() {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
  await workshop.loadBranchMaterials(selectedBranchId.value, {
    status: statusFilter.value === 'all' ? null : statusFilter.value,
    kind: kindFilter.value === 'all' ? null : kindFilter.value,
    search: search.value,
  })
}

watch([selectedBranchId, statusFilter, kindFilter], () => {
  void refreshCatalog()
})

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  selectedBranchId.value = accessibleBranches.value[0]?.id ?? ''
  await refreshCatalog()
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Filial material katalogi</h1>
        <p class="sub">
          Filial qaysi materiallarni sotadi va qanday narxda — mijozlar shu ro'yxatdan ko'radi.
        </p>
      </div>
      <div class="tools">
        <RouterLink
          v-if="selectedBranch"
          :to="rolePath(`/workshop/branches/${selectedBranch.id}`)"
          class="mp-button mp-button-primary"
        >
          Material qo'shish
        </RouterLink>
      </div>
    </div>

    <div v-if="!canUseCatalog" class="st-empty">
      <h3>Material katalogiga ruxsatingiz yo'q</h3>
      <p>Ustaxona egasiga murojaat qiling.</p>
    </div>

    <div v-else-if="accessibleBranches.length === 0" class="st-empty">
      <h3>Filial biriktirilmagan</h3>
      <p>Filial biriktirilgach, katalog shu yerda ko'rinadi.</p>
    </div>

    <template v-else>
      <div class="filters">
        <label class="grid gap-1">
          <span class="filter-label">Qidirish</span>
          <input
            v-model="search"
            class="mp-input min-w-64"
            placeholder="Material qidirish..."
            @input="refreshCatalog"
          />
        </label>
        <ProjectDropdown v-model="selectedBranchId" label="Filial" :options="branchFilterOptions" />
        <ProjectDropdown v-model="kindFilter" label="Tur" :options="kindOptions" />
        <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" />
      </div>

      <section v-if="workshop.setupLoading" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="workshop.setupError" class="st-error">
        <h3>Ma'lumotni yuklab bo'lmadi</h3>
        <p>trace_id: {{ workshop.setupTraceId ?? 'unavailable' }}</p>
      </section>

      <section v-else class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Material</th>
                <th>Tur</th>
                <th>Filial</th>
                <th class="right">Narx</th>
                <th class="right">Min zaxira</th>
                <th>Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in filteredRows" :key="row.id">
                <td>
                  <div class="flex min-w-0 items-center gap-3">
                    <span class="sw"></span>
                    <span class="min-w-0">
                      <span class="nm">{{ row.material.name }}</span>
                      <small class="block truncate text-ink-muted">{{ materialMeta(row) }}</small>
                    </span>
                  </div>
                </td>
                <td>
                  <span :class="row.material.kind === 'edge' ? 'pill p-eb' : 'pill p-cut'">
                    <span class="pd"></span
                    >{{ row.material.kind === 'edge' ? 'Krom (metr)' : 'Panel' }}
                  </span>
                </td>
                <td>{{ selectedBranch?.name ?? '—' }}</td>
                <td class="amt">
                  {{ formatTiyin(row.price_tiyin) }}
                  <small>{{ priceUnit(row.material.kind) }}</small>
                </td>
                <td class="amt muted">
                  {{
                    formatStockQuantity(row.min_stock, row.material.kind === 'edge' ? 'm' : 'panel')
                  }}
                </td>
                <td>
                  <span :class="row.status === 'active' ? 'pill p-ok' : 'pill p-dn'">
                    <span class="pd"></span>{{ row.status === 'active' ? 'Faol' : 'Faol emas' }}
                  </span>
                </td>
                <td class="right">
                  <RouterLink
                    v-if="selectedBranch"
                    :to="rolePath(`/workshop/branches/${selectedBranch.id}`)"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  >
                    Narx / min
                  </RouterLink>
                </td>
              </tr>
              <tr v-if="filteredRows.length === 0">
                <td colspan="7">
                  <div class="st-empty !border-0 !py-8">
                    <h3>Bu filialga material qo'shilmagan</h3>
                    <p>Platforma katalogidan material qo'shing.</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>
