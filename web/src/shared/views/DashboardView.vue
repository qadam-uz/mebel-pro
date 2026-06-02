<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { ApiError, api } from '@/shared/api/client'
import { useRoleConfig, type ShellStateKind } from '@/shared/app/roleConfig'

interface HealthResponse {
  status: string
  env: string
}

const config = useRoleConfig()
const status = ref<ShellStateKind>('loading')
const health = ref<HealthResponse | null>(null)
const traceId = ref<string | null>(null)

const statusTone = computed(
  () =>
    ({
      loading: 'text-info bg-info-soft',
      empty: 'text-warning bg-warning-soft',
      error: 'text-danger bg-danger-soft',
      ready: 'text-success bg-success-soft',
    })[status.value],
)

async function fetchHealth() {
  status.value = 'loading'
  traceId.value = null
  try {
    health.value = await api.get<HealthResponse>('/readyz')
    status.value = 'ready'
  } catch (error) {
    status.value = 'error'
    health.value = null
    if (error instanceof ApiError && typeof error.body === 'object' && error.body) {
      const body = error.body as { trace_id?: string }
      traceId.value = body.trace_id ?? null
    }
  }
}

onMounted(fetchHealth)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold leading-tight tracking-normal text-ink">
          {{ config.dashboardTitle }}
        </h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          {{ config.dashboardSubtitle }}
        </p>
      </div>
      <RouterLink
        v-if="!config.primaryActionTo.startsWith('/api')"
        :to="config.primaryActionTo"
        class="mp-button mp-button-primary"
      >
        {{ config.primaryActionLabel }}
      </RouterLink>
      <a v-else :href="config.primaryActionTo" class="mp-button mp-button-primary">
        {{ config.primaryActionLabel }}
      </a>
    </div>

    <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <article
        v-for="state in config.states"
        :key="state.kind"
        class="mp-surface p-4"
        :aria-current="state.kind === status ? 'true' : undefined"
      >
        <span
          class="mp-chip"
          :class="state.kind === status ? statusTone : 'bg-sunk text-ink-muted'"
        >
          <span class="mp-dot" aria-hidden="true"></span>
          {{ state.kind }}
        </span>
        <h2 class="mt-4 text-base font-extrabold text-ink">{{ state.label }}</h2>
        <p class="mt-1 text-sm text-ink-soft">{{ state.detail }}</p>
      </article>
    </div>

    <div class="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Readiness</h2>
          <p class="mt-1 text-sm text-ink-soft">Backend status for this workspace.</p>
        </div>
        <div class="p-5">
          <div v-if="status === 'loading'" class="space-y-3" aria-live="polite">
            <div class="h-4 w-40 animate-pulse rounded bg-sunk"></div>
            <div class="h-10 w-full animate-pulse rounded bg-sunk"></div>
            <div class="h-10 w-2/3 animate-pulse rounded bg-sunk"></div>
          </div>
          <div v-else-if="status === 'error'" class="rounded-lg bg-danger-soft p-4 text-danger">
            <div class="font-extrabold">Backend readiness failed</div>
            <p class="mt-1 text-sm">Retry after the API is reachable.</p>
            <p v-if="traceId" class="mt-2 font-mono text-xs">trace {{ traceId }}</p>
            <button type="button" class="mp-button mp-button-outline mt-4" @click="fetchHealth">
              Retry
            </button>
          </div>
          <div v-else class="rounded-lg bg-success-soft p-4 text-success">
            <div class="font-extrabold">API ready</div>
            <p class="mt-1 font-mono text-sm">{{ health?.status }} · {{ health?.env }}</p>
          </div>
        </div>
      </section>

      <aside class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold text-ink">First-run state</h2>
        <p class="mt-2 text-sm text-ink-soft">
          {{ config.states.find((state) => state.kind === 'empty')?.detail }}
        </p>
        <div class="mt-5 rounded-lg border border-dashed border-hairline-strong bg-sunk p-4">
          <div class="text-sm font-extrabold text-ink">
            {{ config.states.find((state) => state.kind === 'empty')?.label }}
          </div>
          <p class="mt-1 text-sm text-ink-soft">
            New records will appear here after they are created.
          </p>
        </div>
      </aside>
    </div>
  </section>
</template>
