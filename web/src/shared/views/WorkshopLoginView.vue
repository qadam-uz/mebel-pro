<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import Icon from '@/shared/components/AppIcon.vue'
import { useStaffLogin } from '@/shared/composables/useStaffLogin'
import workshopSceneUrl from '@/assets/login-workshop-scene.svg'

// The shared composable owns the Uzbek sign-in copy (QAD-163) — this view used
// to re-declare a byte-identical map of its own.
const { config, login, password, isSubmitting, errorText, submit } = useStaffLogin()

const showPassword = ref(false)

const valuePoints = ['Buyurtmalar oqimi', 'Ishlab chiqarish navbati', 'Ombor va moliya']
</script>

<template>
  <main class="grid min-h-[var(--app-vh)] text-ink lg:grid-cols-[1.05fr_1fr]">
    <!-- Brand panel — hidden below lg; the form carries the brand on mobile. -->
    <section
      class="relative hidden flex-col overflow-hidden bg-accent px-12 py-12 text-white lg:flex xl:px-16"
    >
      <RouterLink :to="config.homePath" class="flex items-center gap-3">
        <span class="inline-flex size-9 items-center justify-center rounded-lg bg-white">
          <img src="/favicon.svg" alt="" class="size-6" />
        </span>
        <span class="font-serif text-xl font-semibold">{{ config.productLabel }}</span>
      </RouterLink>

      <div class="z-10 my-auto max-w-md py-10">
        <h1 class="font-serif text-4xl font-semibold leading-tight">
          Ustaxonangizni bir joydan boshqaring
        </h1>
        <ul class="mt-7 space-y-3.5">
          <li
            v-for="point in valuePoints"
            :key="point"
            class="flex items-center gap-3 text-lg text-white/90"
          >
            <span
              class="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-white/15"
            >
              <Icon name="check" class="size-3.5" />
            </span>
            {{ point }}
          </li>
        </ul>
      </div>

      <!-- Flat workshop illustration, bottom-anchored band (aspect locked). -->
      <img
        :src="workshopSceneUrl"
        alt=""
        class="pointer-events-none mt-8 w-full select-none"
        aria-hidden="true"
      />
    </section>

    <!-- Form panel -->
    <section class="flex items-center justify-center bg-bg px-4 py-10">
      <div class="w-full max-w-[400px]">
        <RouterLink :to="config.homePath" class="mb-7 flex items-center gap-3 lg:hidden">
          <img src="/favicon.svg" alt="" class="size-9" />
          <span class="font-serif text-2xl font-semibold">{{ config.productLabel }}</span>
        </RouterLink>

        <div class="mp-surface p-6 md:p-7" aria-labelledby="signin-title">
          <h2 id="signin-title" class="font-serif text-2xl font-semibold">Kirish</h2>

          <form class="mt-6 space-y-4" @submit.prevent="submit">
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
              <span class="mb-2 block text-sm font-bold text-ink">Parol</span>
              <div class="relative">
                <input
                  v-model="password"
                  class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated pl-3 pr-12 text-base text-ink"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="current-password"
                  required
                />
                <button
                  type="button"
                  class="absolute right-1 top-1/2 inline-flex size-9 -translate-y-1/2 items-center justify-center rounded-md text-ink-muted transition hover:text-ink"
                  :aria-label="showPassword ? 'Parolni yashirish' : 'Parolni ko\'rsatish'"
                  :aria-pressed="showPassword"
                  @click="showPassword = !showPassword"
                >
                  <Icon :name="showPassword ? 'eye-off' : 'eye'" class="size-5" />
                </button>
              </div>
            </label>
            <p
              v-if="errorText"
              class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
              role="alert"
            >
              {{ errorText }}
            </p>
            <button
              type="submit"
              class="mp-button mp-button-primary w-full"
              :disabled="isSubmitting"
            >
              {{ isSubmitting ? 'Tekshirilmoqda' : 'Kirish' }}
            </button>
          </form>
        </div>
      </div>
    </section>
  </main>
</template>
