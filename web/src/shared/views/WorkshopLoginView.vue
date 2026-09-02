<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import BrandMark from '@/shared/components/BrandMark.vue'
import Icon from '@/shared/components/AppIcon.vue'
import LocaleSwitcher from '@/shared/components/LocaleSwitcher.vue'
import { useStaffLogin } from '@/shared/composables/useStaffLogin'
import workshopSceneUrl from '@/assets/login-workshop-scene.svg'

// The shared composable owns the sign-in failure copy (QAD-163) — this view used
// to re-declare a byte-identical map of its own.
const { config, login, password, isSubmitting, errorText, submit } = useStaffLogin()

const { t } = useI18n()
const showPassword = ref(false)

const valuePoints = computed(() => [
  t('shell.login.valueOrders'),
  t('shell.login.valueProduction'),
  t('shell.login.valueInventory'),
])
</script>

<template>
  <main class="grid min-h-[var(--app-vh)] text-ink lg:grid-cols-[1.05fr_1fr]">
    <!-- Brand panel — hidden below lg; the form carries the brand on mobile.
         `deep`, not `accent`: the panel hosts login-workshop-scene.svg, whose
         whole value ramp is tuned to sit on the graphite brand surface (see the
         SVG's own header), so it must not follow a retheme of the action
         colour. Bone text on graphite is the original pairing. -->
    <section
      class="relative hidden flex-col overflow-hidden bg-deep px-12 py-12 text-on-accent lg:flex xl:px-16"
    >
      <RouterLink :to="config.homePath" class="flex items-center gap-3">
        <span class="inline-flex size-9 items-center justify-center rounded-lg bg-white">
          <BrandMark :size="24" />
        </span>
        <span class="font-display text-xl font-semibold">{{ config.productLabel }}</span>
      </RouterLink>

      <div class="z-10 my-auto max-w-md py-10">
        <h1 class="font-display text-4xl font-semibold leading-tight">
          {{ $t('shell.login.headline') }}
        </h1>
        <ul class="mt-7 space-y-3.5">
          <li
            v-for="point in valuePoints"
            :key="point"
            class="flex items-center gap-3 text-lg text-on-accent/85"
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
          <BrandMark :size="36" />
          <span class="font-display text-2xl font-semibold">{{ config.productLabel }}</span>
        </RouterLink>

        <div class="mp-surface p-6 md:p-7" aria-labelledby="signin-title">
          <h2 id="signin-title" class="font-display text-2xl font-semibold">
            {{ $t('shell.login.title') }}
          </h2>

          <form class="mt-6 space-y-4" @submit.prevent="submit">
            <label class="block">
              <span class="mb-2 block text-sm font-bold text-ink">{{
                $t('shell.login.loginLabel')
              }}</span>
              <input
                v-model="login"
                class="min-h-11 w-full rounded-md border border-hairline-strong bg-elevated px-3 text-base text-ink"
                type="text"
                autocomplete="username"
                required
              />
            </label>
            <label class="block">
              <span class="mb-2 block text-sm font-bold text-ink">{{
                $t('shell.login.passwordLabel')
              }}</span>
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
                  :aria-label="
                    showPassword ? $t('shell.login.hidePassword') : $t('shell.login.showPassword')
                  "
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
              {{ isSubmitting ? $t('shell.login.submitting') : $t('shell.login.submit') }}
            </button>
          </form>

          <!-- The shell — and with it the topbar switcher — does not render on
               an auth route, so the one screen a user who cannot read Uzbek
               meets first would otherwise have no way to change the language. -->
          <div class="mt-6 border-t border-hairline pt-5">
            <LocaleSwitcher variant="segmented" />
          </div>
        </div>
      </div>
    </section>
  </main>
</template>
