<script setup lang="ts">
import { computed } from 'vue'
import QRCode from 'qrcode'

/**
 * A QR rendered as inline SVG from the module matrix.
 *
 * `qrcode`'s own renderers are a canvas bitmap or an HTML string — the first is
 * blurry when the card scales and unreadable in a test, the second needs
 * `v-html`. `QRCode.create` hands over the matrix instead, so the marks are real
 * DOM: crisp at every size, `currentColor` so the palette stays token-driven,
 * and nothing leaves the page (no network fetch for the image).
 */
const props = withDefaults(
  defineProps<{
    /** The payload — a `t.me` deep link, or a workshop's `/w/{code}` URL. */
    value: string
    /** Accessible name; the QR is an image of the link, not decoration. */
    label: string
    /** Quiet zone, in modules. The spec's minimum is 4. */
    margin?: number
  }>(),
  { margin: 4 },
)

interface QrMatrix {
  size: number
  path: string
}

const matrix = computed<QrMatrix | null>(() => {
  if (!props.value) return null
  try {
    const { modules } = QRCode.create(props.value, { errorCorrectionLevel: 'M' })
    const size = modules.size
    const data = modules.data
    let path = ''
    for (let y = 0; y < size; y += 1) {
      for (let x = 0; x < size; x += 1) {
        if (data[y * size + x]) path += `M${x + props.margin} ${y + props.margin}h1v1h-1z`
      }
    }
    return { size: size + props.margin * 2, path }
  } catch {
    // Only an over-long payload can land here, and a deep link never is — but a
    // silent blank square would read as a broken page, so the host is told.
    return null
  }
})
</script>

<template>
  <svg
    v-if="matrix"
    class="block h-auto w-full text-ink"
    :viewBox="`0 0 ${matrix.size} ${matrix.size}`"
    shape-rendering="crispEdges"
    role="img"
    :aria-label="label"
  >
    <rect :width="matrix.size" :height="matrix.size" fill="var(--color-elevated)" />
    <path :d="matrix.path" fill="currentColor" />
  </svg>
  <!-- Shared, not client-login copy: the same component draws the workshop's
       client-link QR, where "use the link instead" is the same recovery. -->
  <p v-else class="p-4 text-center text-sm text-ink-muted">
    {{ $t('common.qr.failed') }}
  </p>
</template>
