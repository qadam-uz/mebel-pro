<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import { formatTiyin } from '@/shared/formatters'
import { useClientCatalogStore, type ClientBranchMaterial } from '@/shared/stores/clientCatalog'

const catalog = useClientCatalogStore()
const branchSearch = ref('')
const materialSearch = ref('')

const branchOptions = computed(() =>
  catalog.branches.map((branch) => ({
    value: branch.branch_id,
    label: `${branch.workshop_name} · ${branch.branch_name}`,
    meta:
      branch.status === 'temporarily_closed'
        ? (branch.closed_reason ?? 'temporarily closed')
        : branch.address,
  })),
)
const selectedBranch = computed(() =>
  catalog.branches.find((branch) => branch.branch_id === catalog.selectedBranchId),
)

async function refreshBranches() {
  await catalog.loadBranches(branchSearch.value)
  if (catalog.selectedBranchId)
    await catalog.loadMaterials(catalog.selectedBranchId, materialSearch.value)
}

async function refreshMaterials() {
  if (catalog.selectedBranchId)
    await catalog.loadMaterials(catalog.selectedBranchId, materialSearch.value)
}

function materialSpec(material: ClientBranchMaterial) {
  if (material.kind === 'edge') return `${material.thickness_mm} mm edge`
  return `${material.thickness_mm} mm · ${material.panel_length_mm}x${material.panel_width_mm} mm`
}

watch(
  () => catalog.selectedBranchId,
  async (id) => {
    if (id) await catalog.loadMaterials(id, materialSearch.value)
  },
)

onMounted(refreshBranches)
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="font-serif text-3xl font-semibold text-ink">Branches and materials</h1>
      <p class="mt-2 text-base text-ink-soft">
        Browse active workshop branches and public material prices before creating a cutting draft.
      </p>
    </div>

    <section class="mp-surface overflow-hidden">
      <div class="grid gap-3 border-b border-hairline p-5 lg:grid-cols-[1fr_auto]">
        <div>
          <label class="mb-1 block text-sm font-bold text-ink" for="client-branch-search">
            Search branches
          </label>
          <input
            id="client-branch-search"
            v-model="branchSearch"
            class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
          />
        </div>
        <button class="mp-button mp-button-outline self-end" type="button" @click="refreshBranches">
          Search
        </button>
      </div>

      <div
        v-if="catalog.loading"
        class="px-5 py-6 text-sm font-bold text-ink-soft"
        aria-live="polite"
      >
        Loading branches
      </div>
      <div v-else-if="catalog.error" class="px-5 py-6 text-sm font-bold text-danger">
        Branch directory could not be loaded. trace {{ catalog.traceId ?? 'unavailable' }}
      </div>
      <div v-else-if="catalog.branches.length === 0" class="px-5 py-6 text-sm text-ink-soft">
        No active workshop branches match the search.
      </div>
      <div v-else class="grid gap-5 p-5 xl:grid-cols-[minmax(320px,0.78fr)_minmax(0,1.22fr)]">
        <div class="space-y-3">
          <FormSelect
            v-model="catalog.selectedBranchId"
            label="Selected branch"
            :options="branchOptions"
          />
          <article v-if="selectedBranch" class="rounded-lg border border-hairline bg-sunk p-4">
            <div class="flex flex-wrap items-center gap-3">
              <AuthFileImage
                v-if="selectedBranch.workshop_logo_file_id"
                :file-id="selectedBranch.workshop_logo_file_id"
                alt=""
                class="size-12 rounded-md object-cover"
              />
              <div class="min-w-0">
                <h2 class="truncate text-lg font-extrabold text-ink">
                  {{ selectedBranch.workshop_name }}
                </h2>
                <p class="text-sm text-ink-soft">{{ selectedBranch.branch_name }}</p>
              </div>
            </div>
            <dl class="mt-4 grid gap-3 text-sm">
              <div>
                <dt class="font-bold text-ink">Address</dt>
                <dd class="text-ink-soft">{{ selectedBranch.address }}</dd>
              </div>
              <div>
                <dt class="font-bold text-ink">Phone</dt>
                <dd class="text-ink-soft">{{ selectedBranch.phone }}</dd>
              </div>
              <div>
                <dt class="font-bold text-ink">Status</dt>
                <dd>
                  <span
                    class="mp-chip"
                    :class="
                      selectedBranch.status === 'active'
                        ? 'bg-success-soft text-success'
                        : 'bg-warning-soft text-warning'
                    "
                  >
                    <span class="mp-dot" aria-hidden="true"></span>
                    {{
                      selectedBranch.status === 'active'
                        ? 'active'
                        : `temporarily closed · ${selectedBranch.closed_reason ?? 'reason not set'}`
                    }}
                  </span>
                </dd>
              </div>
            </dl>
          </article>
        </div>

        <section class="min-w-0">
          <div class="grid gap-3 md:grid-cols-[1fr_auto]">
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="client-material-search">
                Search materials
              </label>
              <input
                id="client-material-search"
                v-model="materialSearch"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              />
            </div>
            <button
              class="mp-button mp-button-outline self-end"
              type="button"
              @click="refreshMaterials"
            >
              Apply
            </button>
          </div>

          <div
            v-if="catalog.materialsLoading"
            class="mt-5 text-sm font-bold text-ink-soft"
            aria-live="polite"
          >
            Loading materials
          </div>
          <div
            v-else-if="catalog.materialsError"
            class="mt-5 rounded-md bg-danger-soft p-4 font-bold text-danger"
          >
            Materials could not be loaded. trace {{ catalog.materialsTraceId ?? 'unavailable' }}
          </div>
          <div
            v-else-if="catalog.materials.length === 0"
            class="mt-5 rounded-md border border-dashed border-hairline-strong p-5 text-sm text-ink-soft"
          >
            No active public materials match this branch and search.
          </div>
          <div v-else class="mt-5 grid gap-3">
            <article
              v-for="material in catalog.materials"
              :key="material.id"
              class="grid gap-3 rounded-lg border border-hairline bg-elevated p-4 md:grid-cols-[auto_1fr_auto]"
            >
              <AuthFileImage
                v-if="material.image_file_id"
                :file-id="material.image_file_id"
                alt=""
                class="size-14 rounded-md object-cover"
              />
              <div
                v-else
                class="grid size-14 place-items-center rounded-md bg-accent-soft font-serif font-bold text-accent"
                aria-hidden="true"
              >
                {{ material.kind.slice(0, 1).toUpperCase() }}
              </div>
              <div class="min-w-0">
                <h3 class="truncate text-base font-extrabold text-ink">{{ material.name }}</h3>
                <p class="mt-1 text-sm text-ink-soft">
                  {{ material.manufacturer_name }} · {{ materialSpec(material) }}
                </p>
                <p class="mt-1 font-mono text-xs text-ink-muted">
                  {{ material.color }}{{ material.decor_code ? ` · ${material.decor_code}` : '' }}
                </p>
              </div>
              <div class="text-left md:text-right">
                <div class="text-base font-extrabold text-ink">
                  {{ formatTiyin(material.price_tiyin) }}
                </div>
                <div class="text-xs font-bold uppercase text-ink-muted">
                  per {{ material.display_unit }}
                </div>
              </div>
            </article>
          </div>
        </section>
      </div>
    </section>
  </section>
</template>
