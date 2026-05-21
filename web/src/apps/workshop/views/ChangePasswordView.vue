<script setup lang="ts">
import { useRouter } from 'vue-router'
import ChangePassword from '@/shared/ui/auth/ChangePassword.vue'
import { useWorkshopAuth } from '../store'

const auth = useWorkshopAuth()
const router = useRouter()

function submit(currentPassword: string, newPassword: string) {
  return auth.changePassword(currentPassword, newPassword)
}

function onDone() {
  router.replace('/workshop')
}
</script>

<template>
  <ChangePassword
    brand-label="Ustaxona boshqaruvi"
    :forced="auth.forcePasswordChange"
    :submit="submit"
    @done="onDone"
  />
</template>
