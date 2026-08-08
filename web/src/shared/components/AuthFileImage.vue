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
    /**
     * Which stored rendition to fetch.
     *
     * `sm` (160 px) is the default because most uses here are 34-40 px swatches
     * in grids, where the original — measured at 2160x2160 and 1.5 MB in
     * production — was over 99% waste. Pass `md` (640 px) where the image is
     * actually shown large, and `original` only where the full file is the point.
     *
     * An unknown or missing rendition falls back to the original server-side, so
     * this is safe on images uploaded before renditions existed.
     */
    size?: 'sm' | 'md' | 'original'
    /**
     * Load `size` first, then quietly replace it with this larger rendition.
     *
     * Only worth it where the smaller one is *already cached* — a detail pane
     * reached from a grid that just drew the same `sm` file. There the placeholder
     * is free and the upgrade is visible. Everywhere else it just downloads the
     * same picture twice on a connection that was the bottleneck, so it is opt-in
     * rather than the default.
     */
    upgradeTo?: 'md' | 'original'
  }>(),
  {
    class: '',
    size: 'sm',
    upgradeTo: undefined,
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
  // Re-runs on a size change too, so a component that switches rendition swaps
  // the image instead of keeping the one it first loaded.
  () => [props.fileId, props.size] as const,
  async ([fileId, size]) => {
    const seq = ++loadSeq
    revoke()
    failed.value = false
    if (!fileId) {
      loading.value = false
      return
    }
    loading.value = true
    try {
      const handle = await files.loadObjectUrl(fileId, size)
      if (seq !== loadSeq || props.fileId !== fileId) {
        handle.revoke()
        return
      }
      revokeCurrent?.()
      revokeCurrent = handle.revoke
      src.value = handle.url
    } catch {
      if (seq === loadSeq) failed.value = true
      return
    } finally {
      // Only the freshest load owns the flag; a superseded run must not clear it.
      if (seq === loadSeq) loading.value = false
    }
    if (props.upgradeTo) void upgrade(fileId, seq, props.upgradeTo)
  },
  { immediate: true },
)

/**
 * Swap in a larger rendition behind the one already on screen.
 *
 * Deliberately silent: no loading flag, no error state. The image the user is
 * looking at is already correct, so a failed or superseded upgrade must change
 * nothing at all — the worst outcome is that the picture stays as sharp as it
 * was. The old object URL is only revoked once the new one is in place, so there
 * is never a frame with no `src` and therefore no flicker.
 */
async function upgrade(fileId: string, seq: number, target: 'md' | 'original') {
  try {
    const handle = await files.loadObjectUrl(fileId, target)
    if (seq !== loadSeq || props.fileId !== fileId) {
      handle.revoke()
      return
    }
    const previousRevoke = revokeCurrent
    revokeCurrent = handle.revoke
    src.value = handle.url
    previousRevoke?.()
  } catch {
    // Keep the smaller rendition. Nothing to report.
  }
}

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
