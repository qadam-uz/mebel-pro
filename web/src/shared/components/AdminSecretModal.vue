<script setup lang="ts">
import { ref, toRef } from 'vue'

import { copyText } from '@/shared/app/clipboard'
import AdminModalCloseIcon from '@/shared/components/AdminModalCloseIcon.vue'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'

interface SecretRow {
  label: string
  value: string
}

const props = defineProps<{
  open: boolean
  title: string
  intro?: string
  rows: SecretRow[]
}>()

const emit = defineEmits<{ close: [] }>()

const toast = useToast()
const panel = ref<HTMLElement | null>(null)
const trap = useFocusTrap(panel, toRef(props, 'open'), () => emit('close'))

async function copyOne(row: SecretRow) {
  const ok = await copyText(row.value)
  if (ok) toast.success(`${row.label} nusxalandi`)
  else toast.danger("Nusxalab bo'lmadi")
}

async function copyAll() {
  const ok = await copyText(props.rows.map((row) => `${row.label}: ${row.value}`).join('\n'))
  if (ok) toast.success('Hammasi nusxalandi')
  else toast.danger("Nusxalab bo'lmadi")
}
</script>

<template>
  <template v-if="open">
    <div class="admin-modal-scrim" aria-hidden="true" @click="emit('close')"></div>
    <section
      ref="panel"
      class="admin-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="admin-secret-title"
      tabindex="-1"
      @keydown="trap.onKeydown"
    >
      <div class="admin-modal-h">
        <h3 id="admin-secret-title">{{ title }}</h3>
        <button type="button" class="admin-icon-button" aria-label="Yopish" @click="emit('close')">
          <AdminModalCloseIcon />
        </button>
      </div>
      <div class="admin-modal-b">
        <p
          class="mb-4 rounded-md bg-warning-soft px-3 py-2 text-sm font-bold text-warning"
          role="alert"
        >
          Bu maxfiy ma'lumot faqat shu yerda bir marta ko'rsatiladi — egasiga yetkazib, saqlab
          oling.
        </p>
        <p v-if="intro" class="mb-3 text-sm text-ink-soft">{{ intro }}</p>
        <div class="admin-secret-box">
          <div v-for="row in rows" :key="row.label" class="admin-secret-row">
            <span class="grid min-w-0 gap-0.5">
              <span class="admin-secret-key">{{ row.label }}</span>
              <span class="admin-secret-value">{{ row.value }}</span>
            </span>
            <button
              type="button"
              class="mp-button mp-button-outline min-h-9 px-3 text-xs"
              @click="copyOne(row)"
            >
              Nusxa
            </button>
          </div>
        </div>
      </div>
      <div class="admin-modal-f">
        <button type="button" class="mp-button mp-button-outline" @click="copyAll">
          Hammasini nusxalash
        </button>
        <button type="button" class="mp-button mp-button-primary" @click="emit('close')">
          Yopdim · saqladim
        </button>
      </div>
    </section>
  </template>
</template>
