<script setup lang="ts">
import { RouterLink } from 'vue-router'

import { useRoleConfig } from '@/shared/app/roleConfig'

const config = useRoleConfig()
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Cutting drafts</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Drafts saved by the client appear here with their panel count and branch context.
        </p>
      </div>
      <RouterLink :to="config.homePath" class="mp-button mp-button-outline">Back home</RouterLink>
    </div>

    <div class="mp-surface p-5">
      <div class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-6">
        <span class="mp-chip bg-warning-soft text-warning">
          <span class="mp-dot" aria-hidden="true"></span>
          Empty
        </span>
        <h2 class="mt-5 font-serif text-2xl font-semibold">No cutting drafts</h2>
        <p class="mt-2 max-w-xl text-base text-ink-soft">
          Saved drafts will show file names, material choices, and last edit time.
        </p>
      </div>
    </div>
  </section>
</template>
