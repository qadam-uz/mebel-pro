<script setup lang="ts">
import { useRouter } from 'vue-router'
import ChangePassword from '@/shared/ui/auth/ChangePassword.vue'
import { useAdminAuth } from '../store'

const auth = useAdminAuth()
const router = useRouter()

function submit(currentPassword: string, newPassword: string) {
  return auth.changePassword(currentPassword, newPassword)
}

function onDone() {
  router.replace('/admin')
}
</script>

<template>
  <ChangePassword
    brand-label="Superadmin"
    :forced="auth.forcePasswordChange"
    :submit="submit"
    @done="onDone"
  />
</template>
