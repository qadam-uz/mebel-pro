<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { useStaffLogin } from '@/shared/composables/useStaffLogin'

const { config, login, password, isSubmitting, error, submit } = useStaffLogin()

// AB-13: useStaffLogin is shared with the workshop login, so map the error CODE
// to Uzbek locally here rather than translating the shared English text map
// (which would change the colleague-owned workshop SPA's copy).
const ADMIN_LOGIN_ERROR_UZ: Record<string, string> = {
  invalid_credentials: "Login yoki parol noto'g'ri.",
  account_locked: "Hisob vaqtincha bloklangan. Birozdan so'ng urinib ko'ring.",
  account_blocked: 'Hisob bloklangan.',
  network_error: "Server bilan bog'lanib bo'lmadi.",
}
const errorText = computed(() =>
  error.value ? (ADMIN_LOGIN_ERROR_UZ[error.value] ?? "Kirib bo'lmadi.") : null,
)
</script>

<template>
  <main class="admin-auth-wrap">
    <section class="admin-auth-card" aria-labelledby="admin-login-title">
      <RouterLink :to="config.homePath" class="client-brand mb-7 inline-flex">
        <img src="/favicon.svg" alt="" class="size-8" />
        <span class="client-brand-name">Mebel Pro</span>
      </RouterLink>

      <form class="space-y-4" @submit.prevent="submit">
        <div>
          <h1 id="admin-login-title" class="font-serif text-3xl font-semibold leading-tight">
            Operator paneliga kirish
          </h1>
          <p class="mt-2 text-sm text-ink-soft">
            Platforma operatori login va parol bilan kiradi. Hujjatlar va API havolalari alohida
            HTTP-Basic himoyasida ochiladi.
          </p>
        </div>

        <label class="admin-field" for="admin-login">
          <span class="admin-field-label">Login</span>
          <input id="admin-login" v-model="login" type="text" autocomplete="username" required />
        </label>

        <label class="admin-field" for="admin-password">
          <span class="admin-field-label">Parol</span>
          <input
            id="admin-password"
            v-model="password"
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
          {{ isSubmitting ? 'Tekshirilmoqda' : 'Kirish' }}
        </button>
      </form>

      <p class="mt-6 border-t border-hairline pt-5 text-center text-xs text-ink-muted">
        Sessiya serverda saqlanadi va bloklash yoki parol almashtirishda darhol bekor qilinadi.
      </p>
    </section>
  </main>
</template>
