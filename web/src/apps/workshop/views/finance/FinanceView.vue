<script setup lang="ts">
// Finance — Dashboard (Income/Expenses/Net KPIs + per-category/per-branch
// breakdown from /finance/report), Income list (+form, edit/void), Expenses
// list (+form, edit/void), Worker production report. view_finance_reports =
// read-only (mutate buttons hidden). Mirrors prototype finance.html/expenses.html.
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { AppTabs } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { useWorkshopAuth } from '../../store'
import { useBranchesStore } from '../../stores/branches'
import FinanceDashboard from './FinanceDashboard.vue'
import IncomeList from './IncomeList.vue'
import ExpenseList from './ExpenseList.vue'
import ProductionReport from './ProductionReport.vue'

const route = useRoute()
const auth = useWorkshopAuth()
const branchesStore = useBranchesStore()

const canMutate = computed(() => auth.can('manage_finance'))

const tabs = computed(() => [
  { id: 'dashboard', label: t('workshop.financeTabDashboard') },
  { id: 'income', label: t('workshop.financeTabIncome') },
  { id: 'expenses', label: t('workshop.financeTabExpenses') },
  { id: 'production', label: t('workshop.financeTabProduction') },
])

const activeTab = ref('dashboard')

function syncFromRoute() {
  if (route.name === 'finance-expenses') activeTab.value = 'expenses'
  else if (route.name === 'finance-production') activeTab.value = 'production'
  else if (route.name === 'finance-income') activeTab.value = 'income'
}

watch(() => route.name, syncFromRoute)
onMounted(() => {
  branchesStore.load()
  syncFromRoute()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('workshop.financeTitle') }}</h1>
        <p class="sub">{{ t('workshop.financeSub') }}</p>
      </div>
    </div>

    <div v-if="!canMutate" class="banner" style="margin-bottom: 14px">
      <div class="ic">i</div>
      <div class="grow">{{ t('workshop.financeReadonly') }}</div>
    </div>

    <AppTabs v-model="activeTab" :tabs="tabs" />

    <FinanceDashboard v-if="activeTab === 'dashboard'" />
    <IncomeList v-else-if="activeTab === 'income'" :can-mutate="canMutate" />
    <ExpenseList v-else-if="activeTab === 'expenses'" :can-mutate="canMutate" />
    <ProductionReport v-else-if="activeTab === 'production'" :can-mutate="canMutate" />
  </div>
</template>
