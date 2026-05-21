<script setup lang="ts">
// Wraps the design system's .btn family. Renders <button> by default, or <a>
// / <RouterLink> when `href` / `to` is given.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'

type Variant = 'primary' | 'acc' | 'outline' | 'ghost' | 'deep' | 'danger' | 'success'
type Size = 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    variant?: Variant
    size?: Size
    block?: boolean
    disabled?: boolean
    loading?: boolean
    type?: 'button' | 'submit' | 'reset'
    to?: RouteLocationRaw
    href?: string
  }>(),
  { variant: 'outline', size: 'md', type: 'button' },
)

const classes = computed(() => [
  'btn',
  `btn-${props.variant}`,
  props.size === 'sm' && 'btn-sm',
  props.size === 'lg' && 'btn-lg',
  props.block && 'btn-block',
])

const tag = computed(() => (props.to ? RouterLink : props.href ? 'a' : 'button'))
const isDisabled = computed(() => props.disabled || props.loading)
</script>

<template>
  <component
    :is="tag"
    :class="classes"
    :to="to"
    :href="href"
    :type="tag === 'button' ? type : undefined"
    :disabled="tag === 'button' ? isDisabled : undefined"
    :aria-disabled="tag !== 'button' && isDisabled ? 'true' : undefined"
    :aria-busy="loading ? 'true' : undefined"
  >
    <slot name="icon" />
    <slot />
  </component>
</template>
