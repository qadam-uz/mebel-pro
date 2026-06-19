<script setup lang="ts">
import { RouterLink } from 'vue-router'

import { useStaffLogin } from '@/shared/composables/useStaffLogin'

const { config, login, password, workshopCode, isSubmitting, errorText, submit } = useStaffLogin()
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
        <p class="mt-4 text-lg text-ink-soft">Enter account credentials to continue.</p>
      </div>
    </section>

    <section class="mp-surface self-center p-5 md:p-6" aria-labelledby="signin-title">
      <h2 id="signin-title" class="font-serif text-2xl font-semibold">Sign in</h2>

      <form class="mt-5 space-y-4" @submit.prevent="submit">
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Workshop code</span>
          <input
            v-model="workshopCode"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="text"
            autocomplete="organization"
            required
          />
        </label>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Login</span>
          <input
            v-model="login"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="text"
            autocomplete="username"
            required
          />
        </label>
        <label class="block">
          <span class="mb-2 block text-sm font-bold text-ink">Password</span>
          <input
            v-model="password"
            class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <p
          v-if="errorText"
          class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
        >
          {{ errorText }}
        </p>
        <button type="submit" class="mp-button mp-button-primary w-full" :disabled="isSubmitting">
          {{ isSubmitting ? 'Signing in' : 'Continue' }}
        </button>
      </form>
    </section>
  </main>
</template>
