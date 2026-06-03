<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import { useFilesStore } from '@/shared/stores/files'

const props = withDefaults(
  defineProps<{
    fileId: string | null
    alt?: string
    class?: string
  }>(),
  {
    alt: '',
    class: '',
  },
)

const files = useFilesStore()
const src = ref<string | null>(null)
const failed = ref(false)

function revoke() {
  if (src.value) URL.revokeObjectURL(src.value)
  src.value = null
}

watch(
  () => props.fileId,
  async (fileId) => {
    revoke()
    failed.value = false
    if (!fileId) return
    try {
      src.value = await files.loadObjectUrl(fileId)
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
    class="grid place-items-center bg-sunk text-xs text-ink-muted"
  >
    image
  </span>
</template>
