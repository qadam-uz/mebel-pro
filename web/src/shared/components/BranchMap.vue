<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type L from 'leaflet'

import { yandexMapUrl } from '@/shared/app/yandexMapLink'

// A branch on a map. Editable in the workshop forms — the operator clicks where
// the shop is rather than transcribing coordinates — and read-only everywhere a
// client is shown where to collect their order.
//
// OpenStreetMap tiles, so no API key and no per-deploy configuration — the
// picker works the moment the app is served. The saved pin is still opened in
// Yandex Maps on the client-facing surfaces, which is what people here use for
// directions.
//
// Leaflet itself arrives through a dynamic `import()` on mount
// (`branchMapLeaflet.ts`) — it is by far the heaviest dependency in the app and
// only two screens ever draw a map. The `import type` above is erased at build
// time, so it does not pull the library back in. The frame keeps its final
// height from the first frame, so nothing on the page moves when the map lands.
const props = defineProps<{
  latitude: number | string | null
  longitude: number | string | null
  /** Display only: no click-to-place, no dragging, no clear. */
  readonly?: boolean
}>()

const emit = defineEmits<{
  'update:point': [{ latitude: number; longitude: number } | null]
}>()

// Tashkent centre — where a branch is, absent any other signal. Zoomed to city
// level so the operator pans from a recognisable place instead of the globe.
const FALLBACK = { lat: 41.311081, lon: 69.240562, zoom: 12 }
const PIN_ZOOM = 16

const host = ref<HTMLElement | null>(null)
/** `loading` until the Leaflet chunk lands, `failed` if it never does — a
 *  stale-chunk 404 after a deploy, or a dropped connection. */
const status = ref<'loading' | 'ready' | 'failed'>('loading')
let leaflet: typeof import('@/shared/components/branchMapLeaflet') | null = null
let map: L.Map | null = null
let marker: L.Marker | null = null
let disposed = false

const point = ref<{ latitude: number; longitude: number } | null>(readPoint())
const openUrl = ref<string | null>(null)

function readPoint() {
  const lat = Number(props.latitude)
  const lon = Number(props.longitude)
  if (props.latitude == null || props.longitude == null) return null
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
  return { latitude: lat, longitude: lon }
}

function place(latitude: number, longitude: number) {
  point.value = { latitude, longitude }
  openUrl.value = yandexMapUrl(latitude, longitude)
  if (!map || !leaflet) return
  if (marker) marker.setLatLng([latitude, longitude])
  else {
    marker = leaflet.L.marker([latitude, longitude], {
      icon: leaflet.markerIcon,
      draggable: !props.readonly,
    }).addTo(map)
    marker.on('dragend', () => {
      const next = marker?.getLatLng()
      if (next) commit(next.lat, next.lng)
    })
  }
}

function commit(latitude: number, longitude: number) {
  place(latitude, longitude)
  emit('update:point', point.value)
}

function clear() {
  point.value = null
  openUrl.value = null
  if (marker && map) {
    map.removeLayer(marker)
    marker = null
  }
  emit('update:point', null)
}

onMounted(async () => {
  try {
    leaflet = await import('@/shared/components/branchMapLeaflet')
  } catch {
    // The coordinates and the "open in Yandex Maps" link below stay usable, so
    // the screen degrades to read-only rather than breaking.
    status.value = 'failed'
    return
  }
  // Unmounted while the chunk was in flight — the host element is gone.
  if (disposed || !host.value) return
  status.value = 'ready'

  const start = point.value
  map = leaflet.L.map(host.value, { scrollWheelZoom: false }).setView(
    [start?.latitude ?? FALLBACK.lat, start?.longitude ?? FALLBACK.lon],
    start ? PIN_ZOOM : FALLBACK.zoom,
  )
  leaflet.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap',
  }).addTo(map)
  // Scroll-zoom is off so the page still scrolls over the map; Ctrl+wheel and
  // the +/- control remain, which is the behaviour a long form needs.
  if (!props.readonly) {
    map.on('click', (event: L.LeafletMouseEvent) => commit(event.latlng.lat, event.latlng.lng))
  }
  if (start) place(start.latitude, start.longitude)
})

onBeforeUnmount(() => {
  disposed = true
  map?.remove()
  map = null
  marker = null
})

// A branch loaded after mount (the detail page fetches, then fills the form)
// has to move the pin that is already on screen.
watch(
  () => [props.latitude, props.longitude],
  () => {
    const next = readPoint()
    if (!next) return
    if (next.latitude === point.value?.latitude && next.longitude === point.value?.longitude) return
    place(next.latitude, next.longitude)
    map?.setView([next.latitude, next.longitude], PIN_ZOOM)
  },
)
</script>

<template>
  <div class="grid gap-2">
    <div class="relative h-64 w-full overflow-hidden rounded-md border border-hairline">
      <div
        ref="host"
        class="h-full w-full"
        role="application"
        :aria-label="$t('workshopAdmin.branches.map.aria')"
      ></div>
      <!-- Sits over the frame rather than replacing it: Leaflet needs the host
           element in the DOM at the moment it initialises, and the box already
           holds its final height so nothing reflows when the map appears. -->
      <div
        v-if="status !== 'ready'"
        class="absolute inset-0 grid place-items-center bg-sunk px-4 text-center text-xs text-ink-muted"
      >
        {{
          status === 'failed' ? $t('workshopAdmin.branches.map.failed') : $t('common.state.loading')
        }}
      </div>
    </div>

    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-xs text-ink-muted">
        <template v-if="point">
          <span v-if="!readonly" class="text-ink">
            {{ point.latitude.toFixed(6) }}, {{ point.longitude.toFixed(6) }}
          </span>
          <a
            v-if="openUrl"
            :href="openUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="font-bold text-accent-deep underline underline-offset-2"
            :class="readonly ? '' : 'ml-2'"
          >
            {{ $t('client.branches.openMap') }}
          </a>
        </template>
        <template v-else-if="!readonly">{{ $t('workshopAdmin.branches.map.hint') }}</template>
      </p>
      <button
        v-if="point && !readonly"
        type="button"
        class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        @click="clear"
      >
        {{ $t('workshopAdmin.branches.map.clear') }}
      </button>
    </div>
  </div>
</template>
