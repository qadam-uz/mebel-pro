<script setup lang="ts">
import { RouterLink } from 'vue-router'

import { useRoleConfig } from '@/shared/app/roleConfig'

const config = useRoleConfig()
</script>

<template>
  <main class="grid min-h-screen bg-bg px-4 py-8 text-ink md:grid-cols-[1fr_minmax(360px,460px)]">
    <section class="flex min-h-[320px] flex-col justify-between py-6 md:px-8">
      <RouterLink :to="config.homePath" class="flex items-center gap-3">
        <img src="/favicon.svg" alt="" class="size-9" />
        <span class="font-serif text-2xl font-semibold">{{ config.productLabel }}</span>
      </RouterLink>

      <div class="max-w-xl">
        <p class="mp-chip mb-5">
          <span class="mp-dot" aria-hidden="true"></span>
          {{ config.roleLabel }}
        </p>
        <h1 class="font-serif text-4xl font-semibold leading-tight tracking-normal md:text-5xl">
          {{ config.roleLabel }} sign-in
        </h1>
        <p class="mt-4 text-lg text-ink-soft">Enter credentials to continue to your workspace.</p>
      </div>
    </section>

    <section class="mp-surface self-center p-5 md:p-6" aria-labelledby="signin-title">
      <h2 id="signin-title" class="font-serif text-2xl font-semibold">Sign in</h2>
      <div class="mt-5 space-y-4">
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Login or phone</span>
          <input
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="text"
            autocomplete="username"
          />
        </label>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Password or OTP</span>
          <input
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="password"
            autocomplete="current-password"
          />
        </label>
        <RouterLink :to="config.homePath" class="mp-button mp-button-primary w-full">
          Continue
        </RouterLink>
      </div>
    </section>
  </main>
</template>
