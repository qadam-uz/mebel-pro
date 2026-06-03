<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useCuttingStore } from '@/shared/stores/cutting'

const router = useRouter()
const cutting = useCuttingStore()
const creating = ref(false)

async function newCutting() {
  creating.value = true
  try {
    const draft = await cutting.createDraft()
    await router.push(`/c/cutting/${draft.id}`)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold leading-tight tracking-normal text-ink">
          Client workspace
        </h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Create cutting drafts, compare layouts, and keep branch context ready for orders.
        </p>
      </div>
      <button
        type="button"
        class="mp-button mp-button-primary"
        :disabled="creating"
        @click="newCutting"
      >
        {{ creating ? 'Creating' : 'New cutting' }}
      </button>
    </div>

    <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.42fr)]">
      <section class="mp-surface overflow-hidden">
        <div class="border-b border-hairline px-5 py-4">
          <h2 class="font-serif text-xl font-semibold text-ink">Cutting</h2>
          <p class="mt-1 text-sm text-ink-soft">Drafts stay private until an order is placed.</p>
        </div>
        <div class="grid gap-3 p-5 sm:grid-cols-2">
          <RouterLink
            to="/c/cutting/drafts"
            class="rounded-lg border border-hairline bg-sunk p-4 transition hover:border-hairline-strong"
          >
            <span class="mp-chip bg-accent-soft text-accent">
              <span class="mp-dot" aria-hidden="true"></span>
              Drafts
            </span>
            <h3 class="mt-4 text-base font-extrabold text-ink">My cutting drafts</h3>
            <p class="mt-1 text-sm text-ink-soft">Open, delete, or continue saved layouts.</p>
          </RouterLink>
          <RouterLink
            to="/c/branches"
            class="rounded-lg border border-hairline bg-sunk p-4 transition hover:border-hairline-strong"
          >
            <span class="mp-chip bg-info-soft text-info">
              <span class="mp-dot" aria-hidden="true"></span>
              Catalog
            </span>
            <h3 class="mt-4 text-base font-extrabold text-ink">Branches and materials</h3>
            <p class="mt-1 text-sm text-ink-soft">Check carried panels and edge tapes.</p>
          </RouterLink>
          <RouterLink
            to="/c/orders"
            class="rounded-lg border border-hairline bg-sunk p-4 transition hover:border-hairline-strong"
          >
            <span class="mp-chip bg-success-soft text-success">
              <span class="mp-dot" aria-hidden="true"></span>
              Orders
            </span>
            <h3 class="mt-4 text-base font-extrabold text-ink">My orders</h3>
            <p class="mt-1 text-sm text-ink-soft">Track production and pickup status.</p>
          </RouterLink>
        </div>
      </section>

      <aside class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold text-ink">Saved automatically</h2>
        <p class="mt-2 text-sm text-ink-soft">
          The editor saves part rows as you work and flags materials not carried by the preferred
          branch.
        </p>
      </aside>
    </div>
  </section>
</template>
