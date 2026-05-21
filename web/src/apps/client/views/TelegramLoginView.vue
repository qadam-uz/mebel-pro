<script setup lang="ts">
// Client sign-in — Telegram Login only (no password; see docs/access-patterns).
// Loads the bot username from /auth/telegram-config, mounts the official
// Telegram Login Widget, and posts its payload to the store on callback.
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/api/client'
import { telegramConfig } from '@/shared/api/auth'
import { t } from '@/shared/i18n'
import { useClientAuth } from '../store'

const auth = useClientAuth()
const router = useRouter()
const route = useRoute()
const widgetHost = ref<HTMLElement | null>(null)
const error = ref('')

// The widget calls window.onTelegramAuth(user) on success.
declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, unknown>) => void
  }
}

async function onAuth(payload: Record<string, unknown>) {
  error.value = ''
  try {
    await auth.loginClientTelegram(payload)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : t('auth.wrongCredentials')
  }
}

onMounted(async () => {
  window.onTelegramAuth = onAuth
  try {
    const { bot_username } = await telegramConfig()
    if (!bot_username || !widgetHost.value) return
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.async = true
    script.setAttribute('data-telegram-login', bot_username)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-userpic', 'false')
    script.setAttribute('data-request-access', 'write')
    script.setAttribute('data-onauth', 'onTelegramAuth(user)')
    widgetHost.value.appendChild(script)
  } catch {
    // Bot not configured (e.g. local dev) — the widget just won't render.
  }
})
</script>

<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <span class="brand">
        <span class="mk">M</span>
        <span style="font-family: var(--f-display); font-size: 19px; font-weight: 600">
          {{ t('common.appName') }}
        </span>
      </span>
      <h1>{{ t('auth.telegramSignIn') }}</h1>
      <p class="sub">{{ t('auth.telegramSub') }}</p>

      <div v-if="error" class="err-msg">{{ error }}</div>

      <div ref="widgetHost" style="display: flex; justify-content: center; min-height: 48px" />
    </div>
  </div>
</template>
