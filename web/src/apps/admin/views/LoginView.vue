<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import PasswordLogin from '@/shared/ui/auth/PasswordLogin.vue'
import type { Credentials } from '@/shared/api/auth'
import { useAdminAuth } from '../store'

const auth = useAdminAuth()
const router = useRouter()
const route = useRoute()

async function submit(creds: Credentials) {
  await auth.loginPlatform(creds)
  if (auth.forcePasswordChange) {
    router.replace('/auth/change-password')
    return
  }
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/admin'
  router.replace(redirect)
}
</script>

<template>
  <PasswordLogin
    brand-label="Superadmin"
    subtitle="Operator paneliga kirish"
    :submit="submit"
    footer="Platforma operatorlari backend CLI orqali yaratiladi. 5 ta noto'g'ri urinishdan keyin 15 daqiqaga bloklanadi."
  />
</template>
