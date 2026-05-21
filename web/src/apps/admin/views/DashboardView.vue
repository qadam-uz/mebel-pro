<script setup lang="ts">
// Platform health dashboard — KPIs (workshops / branches / clients counts),
// recent provisioning, and job + error status summaries. NO workshop money.
// Mirrors prototype admin/dashboard.html.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDate } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import * as api from '../api'
import type { DashboardOut } from '../api/types'

const router = useRouter()
const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const data = ref<DashboardOut | null>(null)

const hasFailedJobs = computed(() => (data.value?.failed_jobs_24h ?? 0) > 0)
const hasOpenErrors = computed(() => (data.value?.open_error_groups ?? 0) > 0)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await api.getDashboard()
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function refresh() {
  load()
  toast.ok(t('admin.refreshed'))
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('admin.dashTitle') }}</h1>
        <p class="sub">{{ t('admin.dashSub') }}</p>
      </div>
      <div class="tools">
        <button class="btn btn-ghost btn-sm" type="button" @click="refresh">
          ↻ {{ t('admin.refresh') }}
        </button>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :title="t('admin.dashLoadFailed')" :retry="load" />

    <div v-else-if="loading" class="kpis">
      <div v-for="n in 4" :key="n" class="kpi">
        <div class="sk sk-line" style="width: 60%" />
        <div class="sk" style="height: 34px; width: 70%; margin: 10px 0" />
        <div class="sk sk-line" style="width: 80%" />
      </div>
    </div>

    <template v-else-if="data">
      <div class="kpis">
        <div class="kpi clickable" @click="router.push('/admin/workshops')">
          <div class="lbl">{{ t('admin.kpiActiveWorkshops') }}</div>
          <div class="v num">{{ data.workshops_count }}</div>
          <div class="d">
            <a style="color: var(--accent); font-weight: 600; text-decoration: none">{{
              t('admin.listLink')
            }}</a>
          </div>
        </div>
        <div class="kpi">
          <div class="lbl">{{ t('admin.kpiBranchesClients') }}</div>
          <div class="v num">
            {{ data.branches_count }} <small>{{ t('admin.kpiBranches') }}</small>
          </div>
          <div class="d">
            <span class="muted"
              >{{ data.clients_count }} {{ t('admin.kpiClientsOnPlatform') }}</span
            >
          </div>
        </div>
        <div
          class="kpi clickable"
          :class="{ warn: hasOpenErrors }"
          @click="router.push('/admin/platform/errors')"
        >
          <div class="lbl">{{ t('admin.kpiOpenErrors') }}</div>
          <div class="v num" :style="hasOpenErrors ? 'color:var(--warn)' : ''">
            {{ data.open_error_groups }}
          </div>
          <div class="d">
            <a style="color: var(--accent); font-weight: 600; text-decoration: none">{{
              t('admin.monitorLink')
            }}</a>
          </div>
        </div>
        <div
          class="kpi clickable"
          :class="{ bad: hasFailedJobs }"
          @click="router.push('/admin/platform/jobs')"
        >
          <div class="lbl">{{ t('admin.kpiBackgroundJobs') }}</div>
          <div class="v num" :class="{ 'danger-text': hasFailedJobs }">
            {{ data.failed_jobs_24h }} <small>{{ t('admin.kpiFailedJobs') }}</small>
          </div>
          <div class="d">
            <span :class="hasFailedJobs ? 'danger-text' : 'muted'">
              <b>{{ hasFailedJobs ? data.failed_jobs_24h : t('admin.kpiAllOk') }}</b>
            </span>
            <a style="color: var(--accent); font-weight: 600; text-decoration: none">{{
              t('admin.viewLink')
            }}</a>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-h">
          <h2>{{ t('admin.recentWorkshops') }}</h2>
          <a class="more" @click="router.push('/admin/workshops')">{{ t('admin.allLink') }}</a>
        </div>
        <div class="card-b" style="padding: 0 22px 18px">
          <div v-if="data.recent_workshops.length === 0" class="st-empty">
            <div class="ic">▥</div>
            <h3>{{ t('admin.workshopsEmpty') }}</h3>
          </div>
          <table v-else class="tbl">
            <thead>
              <tr>
                <th>{{ t('admin.colWorkshop') }}</th>
                <th>{{ t('admin.colCreated') }}</th>
                <th>{{ t('admin.colStatus') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="w in data.recent_workshops"
                :key="w.id"
                class="clickable"
                @click="router.push(`/admin/workshops/${w.id}`)"
              >
                <td class="nm">{{ w.name }}</td>
                <td class="num" style="font-size: 11.5px; color: var(--ink-6)">
                  {{ fmtDate(w.created_at) }}
                </td>
                <td>
                  <StatusBadge
                    :tone="w.status === 'active' ? 'ok' : 'bad'"
                    :label="
                      w.status === 'active' ? t('admin.statusActive') : t('admin.statusBlocked')
                    "
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
