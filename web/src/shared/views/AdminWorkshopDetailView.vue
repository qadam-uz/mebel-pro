<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { useAdminStore } from '@/shared/stores/admin'

const route = useRoute()
const admin = useAdminStore()
const reason = ref('')
const acting = ref(false)
const actionError = ref<string | null>(null)
const workshopId = String(route.params.workshop_id)
const canBlock = computed(
  () => admin.detail?.workshop.status === 'active' && reason.value.trim().length > 0,
)
const canUnblock = computed(() => admin.detail?.workshop.status === 'blocked')

async function block() {
  if (!canBlock.value) return
  acting.value = true
  actionError.value = null
  try {
    await admin.blockWorkshop(workshopId, reason.value)
    reason.value = ''
  } catch {
    actionError.value = 'workshop_block_failed'
  } finally {
    acting.value = false
  }
}

async function unblock() {
  if (!canUnblock.value) return
  acting.value = true
  actionError.value = null
  try {
    await admin.unblockWorkshop(workshopId)
  } catch {
    actionError.value = 'workshop_unblock_failed'
  } finally {
    acting.value = false
  }
}

onMounted(() => admin.loadWorkshop(workshopId))
</script>

<template>
  <section v-if="admin.loading" class="mp-surface p-5 text-sm font-bold text-ink-soft">
    Loading workshop
  </section>
  <section v-else-if="admin.error" class="mp-surface p-5 text-sm font-bold text-danger">
    Workshop could not be loaded.
  </section>
  <section v-else-if="admin.detail" class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">{{ admin.detail.workshop.name }}</h1>
        <p class="mt-2 font-mono text-sm text-ink-soft">{{ admin.detail.workshop.code }}</p>
      </div>
      <span
        class="mp-chip"
        :class="
          admin.detail.workshop.status === 'active'
            ? 'bg-success-soft text-success'
            : 'bg-danger-soft text-danger'
        "
      >
        <span class="mp-dot" aria-hidden="true"></span>
        {{ admin.detail.workshop.status }}
      </span>
    </div>

    <section class="grid gap-5 lg:grid-cols-2">
      <div class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold">Owner</h2>
        <p class="mt-3 font-bold">{{ admin.detail.owner.full_name }}</p>
        <p class="font-mono text-sm text-ink-soft">{{ admin.detail.owner.login }}</p>
      </div>
      <div class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold">Access</h2>
        <div class="mt-4 flex gap-2">
          <input
            v-model="reason"
            class="min-h-10 flex-1 rounded-md border border-hairline-strong px-3"
            placeholder="Block reason"
          />
          <button
            class="mp-button mp-button-outline"
            type="button"
            :disabled="acting || !canBlock"
            @click="block"
          >
            Block
          </button>
          <button
            class="mp-button mp-button-primary"
            type="button"
            :disabled="acting || !canUnblock"
            @click="unblock"
          >
            Unblock
          </button>
        </div>
        <p v-if="actionError" class="mt-3 text-sm font-bold text-danger">
          Access status could not be changed.
        </p>
      </div>
    </section>

    <section class="mp-surface overflow-hidden">
      <div class="border-b border-hairline px-5 py-4">
        <h2 class="font-serif text-xl font-semibold">Branches</h2>
      </div>
      <div class="divide-y divide-hairline">
        <div v-for="branch in admin.detail.branches" :key="branch.id" class="px-5 py-4">
          <div class="font-bold">{{ branch.name }}</div>
          <div class="text-sm text-ink-soft">{{ branch.address }} · {{ branch.phone }}</div>
        </div>
      </div>
    </section>
  </section>
</template>
