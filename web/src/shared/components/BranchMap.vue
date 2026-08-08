<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import { yandexMapUrl } from '@/shared/app/yandexMapLink'

// A branch on a map. Editable in the workshop forms — the operator clicks where
// the shop is rather than transcribing coordinates — and read-only everywhere a
// client is shown where to collect their order.
//
// OpenStreetMap tiles, so no API key and no per-deploy configuration — the
// picker works the moment the app is served. The saved pin is still opened in
// Yandex Maps on the client-facing surfaces, which is what people here use for
// directions.
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
let map: L.Map | null = null
let marker: L.Marker | null = null

const point = ref<{ latitude: number; longitude: number } | null>(readPoint())
const openUrl = ref<string | null>(null)

function readPoint() {
  const lat = Number(props.latitude)
  const lon = Number(props.longitude)
  if (props.latitude == null || props.longitude == null) return null
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
  return { latitude: lat, longitude: lon }
}

// Leaflet ships its marker icons as bundler-hostile relative URLs; pointing at
// the packaged assets keeps the pin visible under Vite without copying files.
const icon = L.icon({
  iconUrl: new URL('leaflet/dist/images/marker-icon.png', import.meta.url).href,
  iconRetinaUrl: new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).href,
  shadowUrl: new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).href,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  shadowSize: [41, 41],
})

function place(latitude: number, longitude: number) {
  point.value = { latitude, longitude }
  openUrl.value = yandexMapUrl(latitude, longitude)
  if (!map) return
  if (marker) marker.setLatLng([latitude, longitude])
  else {
    marker = L.marker([latitude, longitude], { icon, draggable: !props.readonly }).addTo(map)
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

onMounted(() => {
  if (!host.value) return
  const start = point.value
  map = L.map(host.value, { scrollWheelZoom: false }).setView(
    [start?.latitude ?? FALLBACK.lat, start?.longitude ?? FALLBACK.lon],
    start ? PIN_ZOOM : FALLBACK.zoom,
  )
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
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
    <div
      ref="host"
      class="h-64 w-full overflow-hidden rounded-md border border-hairline"
      role="application"
      :aria-label="$t('workshopAdmin.branches.map.aria')"
    ></div>

    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-xs text-ink-muted">
        <template v-if="point">
          <span v-if="!readonly" class="font-mono text-ink">
            {{ point.latitude.toFixed(6) }}, {{ point.longitude.toFixed(6) }}
          </span>
          <a
            v-if="openUrl"
            :href="openUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="font-bold text-accent underline underline-offset-2"
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
