<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { roleMessageKey, useRoleConfig } from '@/shared/app/roleConfig'

const config = useRoleConfig()
const { t } = useI18n()

// The sentence used to be assembled from `roleLabel.toLowerCase()`, which is a
// grammar assumption that only holds in Uzbek — Russian needs the app's name in
// a case the nominative label cannot produce. Each role owns its whole sentence.
const roleText = (name: string) => t(roleMessageKey(config.role, name))
</script>

<template>
  <section class="mx-auto max-w-2xl py-10">
    <span class="mp-chip bg-danger-soft text-danger">
      <span class="mp-dot" aria-hidden="true"></span>
      404
    </span>
    <h1 class="mt-5 font-serif text-4xl font-semibold text-ink">{{ t('nav.notFound.title') }}</h1>
    <p class="mt-3 text-base text-ink-soft">{{ roleText('notFoundBody') }}</p>
    <RouterLink :to="config.homePath" class="mp-button mp-button-primary mt-6">
      {{ roleText('backHome') }}
    </RouterLink>
  </section>
</template>
