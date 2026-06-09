<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { orderPillClass, workshopStatusUz } from '@/shared/app/workshopUi'
import { formatTiyin, formatStockQuantity } from '@/shared/formatters'
import { activeWorkshopStatuses, useOrdersStore } from '@/shared/stores/orders'
import { useAuthStore } from '@/shared/stores/auth'
import { useFinanceStore } from '@/shared/stores/finance'
import { useWorkshopStore } from '@/shared/stores/workshop'

const rolePath = useRolePath()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const orders = useOrdersStore()
const finance = useFinanceStore()

const hasAnyGrant = computed(() => auth.me?.is_owner === true || (auth.me?.grants?.length ?? 0) > 0)
const branchIds = computed(() => workshop.branches.map((branch) => branch.id))
const canFinance = computed(
  () =>
    auth.me?.is_owner === true ||
    (auth.me?.grants ?? []).some((grant) =>
      ['manage_finance', 'view_finance_reports'].includes(grant.permission),
    ),
)
const canInventory = computed(
  () =>
    auth.me?.is_owner === true ||
    (auth.me?.grants ?? []).some((grant) => grant.permission === 'manage_inventory'),
)
const canOrders = computed(
  () =>
    auth.me?.is_owner === true ||
    (auth.me?.grants ?? []).some((grant) =>
      ['view_dashboard', 'manage_orders'].includes(grant.permission),
    ),
)
const activeOrders = computed(() =>
  orders.workshopOrders.filter((order) => activeWorkshopStatuses.includes(order.status)),
)
const recentOrders = computed(() => orders.workshopOrders.slice(0, 8))
const lowStock = computed(() => workshop.stockItems.filter((item) => item.is_low_stock).slice(0, 5))
const netPositive = computed(() => (finance.summary?.net_tiyin ?? 0) >= 0)
const chartValues = [42, 56, 48, 70, 60, 84, 52, 64, 80, 96, 74, 102, 86, 128]
const chartMax = Math.max(...chartValues)

async function loadDashboard() {
  await Promise.all([
    workshop.loadBranchContext().catch(() => undefined),
    orders.loadWorkshopOrders({ status: 'active' }).catch(() => undefined),
  ])
  if (canFinance.value) await finance.loadSummary({}).catch(() => undefined)
  if (canInventory.value && branchIds.value[0]) {
    await workshop.loadStock(branchIds.value[0], { low_stock: true }).catch(() => undefined)
  }
}

onMounted(loadDashboard)
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Asosiy</h1>
        <div class="date">Bugun · <b>ustaxona boshqaruvi</b></div>
      </div>
      <div class="tools">
        <button
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          type="button"
          @click="loadDashboard"
        >
          Yangilash
        </button>
        <RouterLink
          :to="rolePath('/workshop/orders')"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          Buyurtmalar
        </RouterLink>
      </div>
    </div>

    <div v-if="!hasAnyGrant" class="st-empty">
      <h3>Sizga hali hech qanday ruxsat berilmagan</h3>
      <p>Filial va vazifa biriktirilgach, ishingiz shu yerda ko'rinadi.</p>
    </div>

    <template v-else>
      <div class="kpis">
        <RouterLink v-if="canOrders" :to="rolePath('/workshop/orders')" class="kpi no-underline">
          <div class="lbl">Ishlab chiqarishda</div>
          <div class="v num">{{ activeOrders.length }}</div>
          <div class="d"><span>faol buyurtmalar</span><span class="more">taxta</span></div>
        </RouterLink>

        <RouterLink v-if="canFinance" :to="rolePath('/workshop/finance')" class="kpi no-underline">
          <div class="lbl">Tushum</div>
          <div class="v num">{{ formatTiyin(finance.summary?.income_tiyin ?? 0) }}</div>
          <div class="d"><span>yozilgan</span></div>
        </RouterLink>

        <RouterLink
          v-if="canFinance"
          :to="rolePath('/workshop/finance/expenses')"
          class="kpi no-underline"
        >
          <div class="lbl">Xarajatlar</div>
          <div class="v num">{{ formatTiyin(finance.summary?.expense_tiyin ?? 0) }}</div>
          <div class="d"><span>yozilgan</span></div>
        </RouterLink>

        <RouterLink
          v-if="canFinance"
          :to="rolePath('/workshop/finance')"
          class="kpi no-underline"
          :class="netPositive ? '' : 'bad'"
        >
          <div class="lbl" :class="netPositive ? 'success-text' : 'danger-text'">Foyda</div>
          <div class="v num" :class="netPositive ? 'success-text' : 'danger-text'">
            {{ formatTiyin(finance.summary?.net_tiyin ?? 0) }}
          </div>
          <div class="d"><span>tushum - xarajat</span></div>
        </RouterLink>

        <RouterLink
          v-if="canInventory"
          :to="rolePath('/workshop/inventory')"
          class="kpi warn no-underline"
        >
          <div class="lbl">Pastdagi zaxiralar</div>
          <div class="v num warn-text">{{ lowStock.length }}</div>
          <div class="d"><span>ombor</span></div>
        </RouterLink>
      </div>

      <div class="two-col">
        <div class="grid gap-[18px]">
          <div class="card">
            <div class="card-h">
              <div>
                <h2>Savdo · so'nggi 14 kun</h2>
                <div class="sub">
                  Jami · <b>{{ formatTiyin(finance.summary?.income_tiyin ?? 0) }}</b>
                </div>
              </div>
              <div class="flex gap-1">
                <button class="mp-button mp-button-outline min-h-8 px-2 text-xs" type="button">
                  7 K
                </button>
                <button class="mp-button mp-button-primary min-h-8 px-2 text-xs" type="button">
                  14 K
                </button>
                <button class="mp-button mp-button-outline min-h-8 px-2 text-xs" type="button">
                  30 K
                </button>
              </div>
            </div>
            <div class="card-b">
              <div class="flex h-52 items-end gap-1 border-b border-hairline px-1 pb-1">
                <span
                  v-for="(value, index) in chartValues"
                  :key="index"
                  class="block flex-1 rounded-t-sm"
                  :class="
                    index === chartValues.length - 1
                      ? 'bg-accent'
                      : value === chartMax
                        ? 'bg-ink'
                        : 'bg-hairline-strong'
                  "
                  :style="{ height: `${Math.max(12, (value / chartMax) * 170)}px` }"
                  aria-hidden="true"
                ></span>
              </div>
              <div class="mt-3 flex justify-between font-mono text-[11px] text-ink-muted">
                <span>2-may</span>
                <span>8-may</span>
                <span>15-may</span>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-h">
              <h2>Ishlab chiqarish · filiallar bo'yicha</h2>
              <RouterLink :to="rolePath('/workshop/branches')" class="more">filiallar</RouterLink>
            </div>
            <div class="card-b">
              <div
                class="grid gap-px overflow-hidden rounded-lg border border-hairline bg-hairline md:grid-cols-3"
              >
                <RouterLink
                  v-for="branch in workshop.branches"
                  :key="branch.id"
                  :to="rolePath(`/workshop/branches/${branch.id}`)"
                  class="bg-elevated p-4 no-underline transition hover:bg-sunk"
                >
                  <div
                    class="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-muted"
                  >
                    {{ branch.name }}
                  </div>
                  <div class="mt-2 font-serif text-3xl font-semibold text-ink">
                    {{ activeOrders.filter((order) => order.branch_id === branch.id).length }}
                    <small class="font-sans text-sm text-ink-muted">buyurtma</small>
                  </div>
                  <p class="mt-2 font-mono text-[11px] text-ink-muted">
                    {{
                      branch.status === 'temporarily_closed' ? 'vaqtincha yopiq' : branch.address
                    }}
                  </p>
                </RouterLink>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-h">
              <div>
                <h2>So'nggi buyurtmalar</h2>
                <div class="sub">Oxirgi yozuvlar · {{ recentOrders.length }} ta</div>
              </div>
              <RouterLink :to="rolePath('/workshop/orders')" class="more"
                >taxtani ochish</RouterLink
              >
            </div>
            <div class="card-b !p-0">
              <div class="table-wrap">
                <table class="tbl">
                  <thead>
                    <tr>
                      <th>Buyurtma</th>
                      <th>Mijoz</th>
                      <th>Filial</th>
                      <th>Holat</th>
                      <th class="right">Summa</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="order in recentOrders" :key="order.id" class="clickable">
                      <td class="id">
                        <RouterLink
                          :to="rolePath(`/workshop/orders/${order.id}`)"
                          class="no-underline"
                        >
                          {{ order.order_number }}
                        </RouterLink>
                      </td>
                      <td class="nm">{{ order.contact_name }}</td>
                      <td>{{ order.branch_name }}</td>
                      <td>
                        <span :class="orderPillClass(order.status)">
                          <span class="pd"></span>{{ workshopStatusUz[order.status] }}
                        </span>
                      </td>
                      <td class="amt">{{ formatTiyin(order.total_tiyin) }}</td>
                    </tr>
                    <tr v-if="recentOrders.length === 0">
                      <td colspan="5">
                        <div class="st-empty !border-0 !py-8">
                          <h3>Buyurtma yo'q</h3>
                          <p>Mijozlar buyurtma bergach shu yerda chiqadi.</p>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <div class="grid content-start gap-[18px]">
          <div class="card">
            <div class="card-h">
              <h2>Tugayotgan zaxira</h2>
              <RouterLink :to="rolePath('/workshop/inventory')" class="more">ombor</RouterLink>
            </div>
            <div class="card-b">
              <div v-if="workshop.inventoryLoading" class="grid gap-3">
                <span class="sk-line"></span>
                <span class="sk-line"></span>
                <span class="sk-line"></span>
              </div>
              <div v-else-if="lowStock.length === 0" class="st-empty !py-8">
                <h3>Past zaxira yo'q</h3>
                <p>Tanlangan filial materiallari me'yorda.</p>
              </div>
              <div v-else>
                <div v-for="item in lowStock" :key="item.id" class="row-item">
                  <div class="flex min-w-0 items-center gap-3">
                    <div class="sw"></div>
                    <div class="min-w-0">
                      <div class="nm truncate">{{ item.material.name }}</div>
                      <small class="text-ink-muted"
                        >min {{ formatStockQuantity(item.min_stock, item.display_unit) }}</small
                      >
                    </div>
                  </div>
                  <div class="meta warn-text">
                    {{ formatStockQuantity(item.on_hand, item.display_unit) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
