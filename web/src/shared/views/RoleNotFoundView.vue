<script setup lang="ts">
import { RouterLink } from 'vue-router'

import { useRoleConfig } from '@/shared/app/roleConfig'

const config = useRoleConfig()
</script>

<template>
  <section class="mx-auto max-w-2xl py-10">
    <span class="mp-chip bg-danger-soft text-danger">
      <span class="mp-dot" aria-hidden="true"></span>
      404
    </span>
    <h1 class="mt-5 font-serif text-4xl font-semibold text-ink">Page not found</h1>
    <p class="mt-3 text-base text-ink-soft">
      This page is not available in the {{ config.roleLabel }} app.
    </p>
    <RouterLink :to="config.homePath" class="mp-button mp-button-primary mt-6">
      {{ config.notFoundHomeLabel }}
    </RouterLink>
  </section>
</template>
