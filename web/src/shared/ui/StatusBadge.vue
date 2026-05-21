<script setup lang="ts">
// A .pill with a status dot. `tone` picks the colour class directly, or pass
// an order `state` to derive both the colour and the Uzbek label.
import { computed } from 'vue'
import { t } from '@/shared/i18n'

type Tone = 'new' | 'pay' | 'conf' | 'cut' | 'eb' | 'rdy' | 'del' | 'dn' | 'bad' | 'ok' | 'warn'

type OrderState =
  | 'new'
  | 'confirmed'
  | 'cutting'
  | 'edge_banding'
  | 'ready'
  | 'completed'
  | 'cancelled'

const STATE_PILL: Record<OrderState, Tone> = {
  new: 'new',
  confirmed: 'conf',
  cutting: 'cut',
  edge_banding: 'eb',
  ready: 'rdy',
  completed: 'dn',
  cancelled: 'bad',
}

const props = defineProps<{
  tone?: Tone
  state?: OrderState
  label?: string
  // For client app: show the collapsed 5-phase label instead of the full state.
  clientPhase?: boolean
}>()

const resolvedTone = computed<Tone>(
  () => props.tone ?? (props.state ? STATE_PILL[props.state] : 'dn'),
)

const resolvedLabel = computed(() => {
  if (props.label) return props.label
  if (props.state) {
    return t(`${props.clientPhase ? 'clientPhase' : 'orderState'}.${props.state}`)
  }
  return ''
})
</script>

<template>
  <span class="pill" :class="`p-${resolvedTone}`">
    <span class="pd" aria-hidden="true" />
    <slot>{{ resolvedLabel }}</slot>
  </span>
</template>
