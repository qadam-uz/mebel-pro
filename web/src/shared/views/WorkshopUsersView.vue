<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { useWorkshopStore } from '@/shared/stores/workshop'

const workshop = useWorkshopStore()
const rolePath = useRolePath()
const creating = ref(false)
const createError = ref<string | null>(null)
const form = reactive({
  fullName: '',
  phone: '+998',
  login: '',
  tempPassword: '',
})

async function createStaff() {
  creating.value = true
  createError.value = null
  try {
    await workshop.createUser({
      full_name: form.fullName,
      phone: form.phone,
      login: form.login,
      temp_password: form.tempPassword || undefined,
      grants: [],
    })
    form.fullName = ''
    form.phone = '+998'
    form.login = ''
    form.tempPassword = ''
  } catch {
    createError.value = 'user_create_failed'
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  void workshop.loadUsers()
})
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="font-serif text-3xl font-semibold text-ink">Workshop users</h1>
      <p class="mt-2 text-base text-ink-soft">Create staff and manage branch permissions.</p>
    </div>

    <section class="mp-surface p-5">
      <h2 class="font-serif text-xl font-semibold">Create staff</h2>
      <form class="mt-5 grid gap-4 md:grid-cols-4" @submit.prevent="createStaff">
        <label class="block text-sm font-bold text-ink" for="staff-full-name">
          Full name
          <input
            id="staff-full-name"
            v-model="form.fullName"
            class="mp-input mt-1"
            autocomplete="name"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="staff-phone">
          Phone
          <input
            id="staff-phone"
            v-model="form.phone"
            class="mp-input mt-1"
            autocomplete="tel"
            inputmode="tel"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="staff-login">
          Login
          <input
            id="staff-login"
            v-model="form.login"
            class="mp-input mt-1"
            autocomplete="username"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="staff-temp-password">
          Temp password
          <input
            id="staff-temp-password"
            v-model="form.tempPassword"
            class="mp-input mt-1"
            autocomplete="new-password"
          />
        </label>
        <button
          class="mp-button mp-button-primary md:col-span-4"
          type="submit"
          :disabled="creating"
        >
          {{ creating ? 'Creating' : 'Create user' }}
        </button>
      </form>
      <div
        v-if="workshop.lastTempPassword"
        class="mt-4 rounded-md bg-success-soft p-4 text-success"
      >
        <div class="font-extrabold">Temporary password</div>
        <p class="mt-1 font-mono text-sm">{{ workshop.lastTempPassword }}</p>
      </div>
      <p v-if="createError" class="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
        User could not be created.
      </p>
    </section>

    <section class="mp-surface overflow-hidden">
      <div class="border-b border-hairline px-5 py-4">
        <h2 class="font-serif text-xl font-semibold">Users</h2>
      </div>
      <div v-if="workshop.loading" class="px-5 py-6 text-sm font-bold text-ink-soft">
        Loading users
      </div>
      <div v-else-if="workshop.error" class="px-5 py-6 text-sm font-bold text-danger">
        Users could not be loaded.
      </div>
      <div v-else-if="workshop.users.length === 0" class="px-5 py-6 text-sm text-ink-soft">
        No staff users yet.
      </div>
      <div v-else class="divide-y divide-hairline">
        <RouterLink
          v-for="user in workshop.users"
          :key="user.id"
          :to="rolePath(`/workshop/settings/users/${user.id}`)"
          class="grid gap-2 px-5 py-4 no-underline sm:grid-cols-[1fr_auto]"
        >
          <span>
            <span class="block font-bold text-ink">{{ user.full_name }}</span>
            <span class="block font-mono text-xs text-ink-muted">{{ user.login }}</span>
          </span>
          <span
            class="mp-chip"
            :class="
              user.status === 'active'
                ? 'bg-success-soft text-success'
                : 'bg-danger-soft text-danger'
            "
          >
            <span class="mp-dot" aria-hidden="true"></span>
            {{ user.is_owner ? 'owner' : user.status }}
          </span>
        </RouterLink>
      </div>
    </section>
  </section>
</template>
