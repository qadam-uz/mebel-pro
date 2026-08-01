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
// A saved image is fetched (authenticated) into an object URL before it can
// render; without a placeholder the box sits blank and reads as "no image".
const loading = ref(false)
// We own the object URL's lifetime via the handle's revoke (CB-131).
let revokeCurrent: (() => void) | null = null
let loadSeq = 0

function revoke() {
  revokeCurrent?.()
  revokeCurrent = null
  src.value = null
}

watch(
  () => props.fileId,
  async (fileId) => {
    const seq = ++loadSeq
    revoke()
    failed.value = false
    if (!fileId) {
      loading.value = false
      return
    }
    loading.value = true
    try {
      const handle = await files.loadObjectUrl(fileId)
      if (seq !== loadSeq || props.fileId !== fileId) {
        handle.revoke()
        return
      }
      revokeCurrent?.()
      revokeCurrent = handle.revoke
      src.value = handle.url
    } catch {
      if (seq === loadSeq) failed.value = true
    } finally {
      // Only the freshest load owns the flag; a superseded run must not clear it.
      if (seq === loadSeq) loading.value = false
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  loadSeq += 1
  revoke()
})
</script>

<template>
  <img v-if="src" :src="src" :alt="alt" :class="props.class" />
  <span
    v-else-if="loading"
    :class="props.class"
    class="sk block"
    role="img"
    :aria-label="alt ? $t('catalog.image.loadingNamed', { alt }) : $t('catalog.image.loading')"
    aria-busy="true"
  />
  <span
    v-else-if="failed"
    :class="props.class"
    role="img"
    :aria-label="alt ? $t('catalog.image.failedNamed', { alt }) : $t('catalog.image.failed')"
    class="grid place-items-center bg-sunk text-xs text-ink-muted"
  >
    {{ $t('catalog.image.none') }}
  </span>
</template>
