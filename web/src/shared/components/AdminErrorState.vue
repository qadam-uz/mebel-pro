<script setup lang="ts">
import { computed } from 'vue'

// Shared admin load-error surface (AB-08). Replaces the ~9 hand-copied
// `<section class="admin-error">` blocks so the copy lives in one place, every
// load gains a retry affordance, and a 403 renders a dedicated access-revoked
// state instead of a generic "service down" message (AB-01). Announced via
// role="alert" so a screen reader hears the failure (AB-28).
const props = defineProps<{
  code: string | null
  traceId?: string | null
  title?: string
}>()

const emit = defineEmits<{ retry: [] }>()

const isDenied = computed(
  () => props.code === 'permission_denied' || props.code === 'password_reset_required',
)
</script>

<template>
  <section class="admin-error" role="alert">
    <h3>{{ isDenied ? 'Kirish cheklangan' : (title ?? "Ma'lumotlarni yuklab bo'lmadi") }}</h3>
    <p>
      {{
        isDenied
          ? 'Platforma operatori huquqi tasdiqlanmadi — chiqib, qaytadan kiring.'
          : "Birozdan so'ng qayta urinib ko'ring."
      }}
      <span v-if="traceId" class="admin-mono">trace {{ traceId }}</span>
    </p>
    <button type="button" class="mp-button mp-button-outline mt-3" @click="emit('retry')">
      Qayta urinish
    </button>
  </section>
</template>
