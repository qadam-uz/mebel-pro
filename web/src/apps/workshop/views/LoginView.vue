<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import PasswordLogin from '@/shared/ui/auth/PasswordLogin.vue'
import type { Credentials } from '@/shared/api/auth'
import { useWorkshopAuth } from '../store'

const auth = useWorkshopAuth()
const router = useRouter()
const route = useRoute()

async function submit(creds: Credentials) {
  await auth.loginWorkshop(creds)
  if (auth.forcePasswordChange) {
    router.replace('/auth/change-password')
    return
  }
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/workshop'
  router.replace(redirect)
}
</script>

<template>
  <PasswordLogin
    brand-label="Ustaxona boshqaruvi"
    subtitle="Boshqaruv kabineti"
    :submit="submit"
    footer="Egasi yo xodim sifatida ishlaysiz? Login va parolingizni ustaxona egasidan oling."
  />
</template>
