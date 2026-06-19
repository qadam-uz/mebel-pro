<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { useRolePath } from '@/shared/app/paths'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { branchOptions } from '@/shared/app/workshopUi'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatStockQuantity, formatTiyin } from '@/shared/formatters'
import type { MaterialKind, MaterialStatus, PanelMaterialType } from '@/shared/stores/admin'
import { useWorkshopStore } from '@/shared/stores/workshop'

const rolePath = useRolePath()
const permissions = useWorkshopPermissions()
const workshop = useWorkshopStore()
const toast = useToast()
const route = useRoute()
const selectedBranchId = ref('')
const statusFilter = ref<'all' | MaterialStatus>('all')
const kindFilter = ref<'all' | MaterialKind>('all')
const manufacturerFilter = ref('all')
const materialTypeFilter = ref<'all' | PanelMaterialType>('all')
const search = ref('')
const rowActionId = ref<string | null>(null)
const rowActionError = ref<string | null>(null)
const rowActionTraceId = ref<string | null>(null)
let searchTimer: number | undefined

const canUseCatalog = computed(() => permissions.can(p.manageCatalog))
const accessibleBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, [p.manageCatalog]),
)
const branchFilterOptions = computed(() =>
  branchOptions(
    accessibleBranches.value,
    permissions.isOwner.value ? 'Barcha filiallar' : 'Mening filiallarim',
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
const materialTypeOptions = [
  { value: 'all', label: 'Barcha panel turlari', meta: 'panel turi', status: 'active' as const },
  { value: 'dsp', label: 'DSP', meta: 'laminat panel', status: 'active' as const },
  { value: 'mdf', label: 'MDF', meta: 'MDF panel', status: 'active' as const },
  { value: 'plywood', label: 'Fanera', meta: 'plywood', status: 'active' as const },
  {
    value: 'natural_wood',
    label: "Tabiiy yog'och",
    meta: 'natural_wood',
    status: 'active' as const,
  },
  { value: 'other', label: 'Boshqa', meta: 'other', status: 'active' as const },
]
const selectedBranch = computed(
  () => accessibleBranches.value.find((branch) => branch.id === selectedBranchId.value) ?? null,
)
const manufacturerOptions = computed(() => {
  const byId = new Map<string, string>()
  for (const row of workshop.branchMaterials) {
    byId.set(row.material.manufacturer_id, row.material.manufacturer_name)
  }
  return [
    {
      value: 'all',
      label: 'Barcha ishlab chiqaruvchilar',
      meta: 'filtr',
      status: 'active' as const,
    },
    ...[...byId.entries()]
      .sort((left, right) => left[1].localeCompare(right[1]))
      .map(([value, label]) => ({ value, label, meta: 'manufacturer', status: 'active' as const })),
  ]
})
function applyContextBranch() {
  const contextBranchId = workshop.selectedBranchContext
  if (!contextBranchId) return
  if (!accessibleBranches.value.some((branch) => branch.id === contextBranchId)) return
  selectedBranchId.value = contextBranchId
}

function routeSearchValue() {
  const value = route.query.search
  return typeof value === 'string' ? value : ''
}

function applyRouteSearch() {
  const value = routeSearchValue()
  if (value !== search.value) search.value = value
}

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
  rowActionError.value = null
  rowActionTraceId.value = null
  await workshop
    .loadBranchMaterials(selectedBranchId.value, {
      status: statusFilter.value === 'all' ? null : statusFilter.value,
      kind: kindFilter.value === 'all' ? null : kindFilter.value,
      manufacturer_id: manufacturerFilter.value === 'all' ? null : manufacturerFilter.value,
      material_type: materialTypeFilter.value === 'all' ? null : materialTypeFilter.value,
      search: search.value,
    })
    .catch(() => undefined)
}

async function toggleVisibility(row: (typeof workshop.branchMaterials)[number]) {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
  rowActionId.value = row.id
  rowActionError.value = null
  rowActionTraceId.value = null
  try {
    await workshop.setBranchMaterialStatus(
      selectedBranchId.value,
      row.id,
      row.status === 'active' ? 'inactive' : 'active',
    )
    toast.success("Material holati o'zgartirildi.")
  } catch (caught) {
    rowActionError.value = "Material holatini o'zgartirib bo'lmadi."
    rowActionTraceId.value = apiTraceId(caught)
  } finally {
    rowActionId.value = null
  }
}

watch([selectedBranchId, statusFilter, kindFilter, manufacturerFilter, materialTypeFilter], () => {
  void refreshCatalog()
})

watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void refreshCatalog(), 250)
})

watch(selectedBranchId, (value) => {
  if (value && value !== 'all') workshop.setSelectedBranchContext(value)
})

watch(
  () => workshop.selectedBranchContext,
  () => {
    applyContextBranch()
  },
)

watch(
  () => route.query.search,
  () => {
    applyRouteSearch()
  },
)

onMounted(async () => {
  applyRouteSearch()
  await workshop.loadBranchContext().catch(() => undefined)
  selectedBranchId.value = accessibleBranches.value[0]?.id ?? ''
  applyContextBranch()
  window.clearTimeout(searchTimer)
  await refreshCatalog()
})

onBeforeUnmount(() => {
  window.clearTimeout(searchTimer)
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
          Filial katalogini ochish
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
          <input v-model="search" class="mp-input min-w-64" placeholder="Material qidirish..." />
        </label>
        <ProjectDropdown v-model="selectedBranchId" label="Filial" :options="branchFilterOptions" />
        <ProjectDropdown v-model="kindFilter" label="Tur" :options="kindOptions" />
        <ProjectDropdown
          v-model="manufacturerFilter"
          label="Ishlab chiqaruvchi"
          :options="manufacturerOptions"
        />
        <ProjectDropdown
          v-model="materialTypeFilter"
          label="Panel turi"
          :options="materialTypeOptions"
        />
        <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" />
      </div>

      <div v-if="rowActionError" class="banner danger mb-4">
        <div class="grow">
          {{ rowActionError }} · trace_id: {{ rowActionTraceId ?? 'unavailable' }}
        </div>
      </div>

      <section v-if="workshop.catalogLoading" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="workshop.catalogError" class="st-error">
        <h3>Ma'lumotni yuklab bo'lmadi</h3>
        <p>trace_id: {{ workshop.catalogTraceId ?? 'unavailable' }}</p>
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
              <tr v-for="row in workshop.branchMaterials" :key="row.id">
                <td>
                  <div class="flex min-w-0 items-center gap-3">
                    <span class="sw" :class="materialSwatchClass(row.material)"></span>
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
                  <button
                    type="button"
                    class="mp-button mp-button-outline ml-2 min-h-8 px-2 text-xs"
                    :disabled="rowActionId === row.id"
                    @click="toggleVisibility(row)"
                  >
                    {{
                      rowActionId === row.id
                        ? 'Saqlanmoqda'
                        : row.status === 'active'
                          ? 'Mijozdan yashirish'
                          : "Mijozga ko'rsatish"
                    }}
                  </button>
                </td>
              </tr>
              <tr v-if="workshop.branchMaterials.length === 0">
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
