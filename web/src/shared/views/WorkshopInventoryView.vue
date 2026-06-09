<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { branchOptions } from '@/shared/app/workshopUi'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { formatDate, formatStockQuantity } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

const rolePath = useRolePath()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const activeTab = ref<'stock' | 'tx' | 'suppliers'>('stock')
const selectedBranchId = ref('')
const search = ref('')
const lowOnly = ref(false)

const canUseInventory = computed(
  () =>
    auth.me?.is_owner === true ||
    (auth.me?.grants ?? []).some((grant) => grant.permission === 'manage_inventory'),
)
const accessibleBranches = computed(() =>
  auth.me?.is_owner === true
    ? workshop.branches
    : workshop.branches.filter((branch) =>
        (auth.me?.grants ?? []).some(
          (grant) => grant.branch_id === branch.id && grant.permission === 'manage_inventory',
        ),
      ),
)
const branchFilterOptions = computed(() =>
  branchOptions(
    accessibleBranches.value,
    auth.me?.is_owner ? 'Barcha filiallar' : 'Mening filiallarim',
  ),
)
const selectedBranch = computed(
  () => accessibleBranches.value.find((branch) => branch.id === selectedBranchId.value) ?? null,
)
const filteredStock = computed(() => {
  const query = search.value.trim().toLowerCase()
  return workshop.stockItems.filter((item) => {
    if (lowOnly.value && !item.is_low_stock) return false
    if (query && !item.material.name.toLowerCase().includes(query)) return false
    return true
  })
})

function materialMeta(item: (typeof workshop.stockItems)[number]) {
  if (item.kind === 'edge') return `${item.material.thickness_mm} mm · krom (metr)`
  return `${item.material.thickness_mm} mm · ${item.material.panel_length_mm}x${item.material.panel_width_mm}`
}

async function refreshInventory() {
  if (!selectedBranchId.value || selectedBranchId.value === 'all') return
  await workshop.loadInventory(selectedBranchId.value)
}

watch(selectedBranchId, () => {
  void refreshInventory()
})

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  selectedBranchId.value = accessibleBranches.value[0]?.id ?? ''
  await refreshInventory()
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Ombor</h1>
        <p class="sub">Filiallarda mavjud panellar va krom materiallari.</p>
      </div>
      <div class="tools">
        <RouterLink
          v-if="selectedBranch"
          :to="rolePath(`/workshop/branches/${selectedBranch.id}`)"
          class="mp-button mp-button-primary"
        >
          Filial omborini boshqarish
        </RouterLink>
      </div>
    </div>

    <div v-if="!canUseInventory" class="st-empty">
      <h3>Ombor bo'limiga ruxsatingiz yo'q</h3>
      <p>Ustaxona egasiga murojaat qiling.</p>
    </div>

    <div v-else-if="accessibleBranches.length === 0" class="st-empty">
      <h3>Filial biriktirilmagan</h3>
      <p>Filial biriktirilgach, ombor qoldiqlari shu yerda ko'rinadi.</p>
    </div>

    <template v-else>
      <div class="tabs">
        <button
          class="tab"
          :class="{ on: activeTab === 'stock' }"
          type="button"
          @click="activeTab = 'stock'"
        >
          Joriy ombor
        </button>
        <button
          class="tab"
          :class="{ on: activeTab === 'tx' }"
          type="button"
          @click="activeTab = 'tx'"
        >
          Tranzaksiyalar
        </button>
        <button
          class="tab"
          :class="{ on: activeTab === 'suppliers' }"
          type="button"
          @click="activeTab = 'suppliers'"
        >
          Yetkazib beruvchilar
        </button>
      </div>

      <div class="filters">
        <label class="grid gap-1">
          <span class="filter-label">Qidirish</span>
          <input v-model="search" class="mp-input min-w-64" placeholder="Material qidirish..." />
        </label>
        <ProjectDropdown v-model="selectedBranchId" label="Filial" :options="branchFilterOptions" />
        <label
          v-if="activeTab === 'stock'"
          class="flex min-h-10 items-center gap-2 text-sm font-bold text-ink"
        >
          <input v-model="lowOnly" type="checkbox" class="size-4 accent-[var(--color-accent)]" />
          Faqat past zaxiralar
        </label>
      </div>

      <div v-if="workshop.inventoryLoading" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </div>

      <div v-else-if="workshop.inventoryError" class="st-error">
        <h3>Ma'lumotni yuklab bo'lmadi</h3>
        <p>trace_id: {{ workshop.inventoryTraceId ?? 'unavailable' }}</p>
      </div>

      <section v-else-if="activeTab === 'stock'" class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Material</th>
                <th>Filial</th>
                <th class="right">Mavjud</th>
                <th class="right">Min</th>
                <th>Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredStock" :key="item.id">
                <td>
                  <div class="flex min-w-0 items-center gap-3">
                    <span class="sw"></span>
                    <span class="min-w-0">
                      <span class="nm">{{ item.material.name }}</span>
                      <small class="block truncate text-ink-muted">{{ materialMeta(item) }}</small>
                    </span>
                  </div>
                </td>
                <td>{{ selectedBranch?.name ?? '—' }}</td>
                <td class="amt" :class="{ 'warn-text': item.is_low_stock }">
                  {{ formatStockQuantity(item.on_hand, item.display_unit) }}
                </td>
                <td class="amt muted">
                  {{ formatStockQuantity(item.min_stock, item.display_unit) }}
                </td>
                <td>
                  <span :class="item.is_low_stock ? 'pill p-warn' : 'pill p-ok'">
                    <span class="pd"></span>{{ item.is_low_stock ? 'Past' : 'OK' }}
                  </span>
                </td>
                <td class="right">
                  <RouterLink
                    v-if="selectedBranch"
                    :to="rolePath(`/workshop/branches/${selectedBranch.id}`)"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  >
                    Boshqarish
                  </RouterLink>
                </td>
              </tr>
              <tr v-if="filteredStock.length === 0">
                <td colspan="6">
                  <div class="st-empty !border-0 !py-8">
                    <h3>Bu filialga material qo'shilmagan</h3>
                    <p>Katalogdan material qo'shing.</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-else-if="activeTab === 'tx'" class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Vaqt</th>
                <th>Turi</th>
                <th>Material</th>
                <th class="right">Miqdor</th>
                <th>Keyin</th>
                <th>Buyurtma</th>
                <th>Kim qildi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in workshop.stockTransactions" :key="tx.id">
                <td class="num text-ink-muted">{{ formatDate(tx.created_at) }}</td>
                <td>
                  <span
                    :class="
                      tx.type === 'stock_in'
                        ? 'pill p-ok'
                        : tx.type === 'adjust'
                          ? 'pill p-warn'
                          : tx.type === 'restore'
                            ? 'pill p-conf'
                            : 'pill p-bad'
                    "
                  >
                    <span class="pd"></span>{{ tx.type }}
                  </span>
                </td>
                <td class="nm">{{ tx.material_name }}</td>
                <td class="amt" :class="tx.quantity >= 0 ? 'success-text' : 'danger-text'">
                  {{ tx.quantity > 0 ? '+' : '' }}{{ tx.quantity }}
                </td>
                <td class="num muted">{{ tx.balance_after }}</td>
                <td>
                  <RouterLink
                    v-if="tx.order_id"
                    :to="rolePath(`/workshop/orders/${tx.order_id}`)"
                    class="id no-underline"
                  >
                    {{ tx.order_id.slice(0, 8) }}
                  </RouterLink>
                  <span v-else class="muted">{{ tx.supplier_name ?? tx.note ?? '—' }}</span>
                </td>
                <td>
                  <small class="text-ink-soft">{{ tx.actor_user_id ?? 'System' }}</small>
                </td>
              </tr>
              <tr v-if="workshop.stockTransactions.length === 0">
                <td colspan="7">
                  <div class="st-empty !border-0 !py-8"><h3>Tranzaksiya yo'q</h3></div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-else class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Nomi</th>
                <th>Telefon</th>
                <th>Izoh</th>
                <th>Holat</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="supplier in workshop.suppliers" :key="supplier.id">
                <td class="nm">{{ supplier.name }}</td>
                <td class="num">{{ supplier.phone ?? '—' }}</td>
                <td>{{ supplier.note ?? '—' }}</td>
                <td>
                  <span :class="supplier.status === 'active' ? 'pill p-ok' : 'pill p-dn'">
                    <span class="pd"></span
                    >{{ supplier.status === 'active' ? 'Faol' : 'Faol emas' }}
                  </span>
                </td>
              </tr>
              <tr v-if="workshop.suppliers.length === 0">
                <td colspan="4">
                  <div class="st-empty !border-0 !py-8"><h3>Yetkazib beruvchi yo'q</h3></div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>
