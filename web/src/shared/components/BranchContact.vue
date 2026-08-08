<script setup lang="ts">
import { computed } from 'vue'

import { formatPhone } from '@/shared/app/clientUi'
import { yandexMapUrl } from '@/shared/app/yandexMapLink'
import Icon from '@/shared/components/AppIcon.vue'

// How to reach a branch: address, every published number, and the map pin.
// Three surfaces show this — checkout, a placed order, the workshop's own branch
// page — and they had drifted into showing one phone and no pin.
const props = defineProps<{
  address: string
  phone: string
  additionalPhones?: string[]
  latitude?: string | number | null
  longitude?: string | number | null
}>()

/** Primary first, then the extras — all tap-to-call. */
const phones = computed(() => [props.phone, ...(props.additionalPhones ?? [])].filter(Boolean))
const mapUrl = computed(() => yandexMapUrl(props.latitude, props.longitude))
</script>

<template>
  <div class="grid gap-1.5">
    <p class="text-sm text-ink-muted">{{ address }}</p>

    <p class="flex flex-wrap items-center gap-x-3 gap-y-1">
      <a
        v-for="phone in phones"
        :key="phone"
        :href="`tel:${phone}`"
        class="inline-flex min-h-11 items-center font-mono text-xs font-bold text-accent underline underline-offset-2"
      >
        {{ formatPhone(phone) }}
      </a>

      <!-- A pin icon, not an embedded map: this sits inside a contact block the
           client reads in passing, and a map frame here would outweigh the
           order it belongs to. Only rendered when the branch has coordinates. -->
      <a
        v-if="mapUrl"
        :href="mapUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="grid size-11 place-items-center rounded-md border border-hairline text-accent transition hover:border-accent hover:bg-accent-soft"
        :title="$t('client.branches.openMap')"
        :aria-label="$t('client.branches.openMap')"
      >
        <Icon name="map-pin" class="size-[18px]" />
      </a>
    </p>
  </div>
</template>
