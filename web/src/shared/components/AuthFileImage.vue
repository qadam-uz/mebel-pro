<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import { useFilesStore } from '@/shared/stores/files'

// `alt` is required: a meaningful image without alt is hidden from assistive
// tech, and the load-failure fallback needs it to announce what was missing
// (CB-54). Pass an empty string explicitly for a purely decorative image.
const props = withDefaults(
  defineProps<{
    fileId: string | null
    alt: string
    class?: string
  }>(),
  {
    class: '',
  },
)

const files = useFilesStore()
const src = ref<string | null>(null)
const failed = ref(false)
// We own the object URL's lifetime via the handle's revoke (CB-131).
let revokeCurrent: (() => void) | null = null

function revoke() {
  revokeCurrent?.()
  revokeCurrent = null
  src.value = null
}

watch(
  () => props.fileId,
  async (fileId) => {
    revoke()
    failed.value = false
    if (!fileId) return
    try {
      const handle = await files.loadObjectUrl(fileId)
      revokeCurrent = handle.revoke
      src.value = handle.url
    } catch {
      failed.value = true
    }
  },
  { immediate: true },
)

onBeforeUnmount(revoke)
</script>

<template>
  <img v-if="src" :src="src" :alt="alt" :class="props.class" />
  <span
    v-else-if="failed"
    :class="props.class"
    role="img"
    :aria-label="alt ? `${alt} — rasmni yuklab bo'lmadi` : 'Rasmni yuklab bo\'lmadi'"
    class="grid place-items-center bg-sunk text-xs text-ink-muted"
  >
    Rasm yo'q
  </span>
</template>
