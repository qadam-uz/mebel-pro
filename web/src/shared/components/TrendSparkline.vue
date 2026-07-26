<script setup lang="ts">
import { computed } from 'vue'

import { SPARK_HEIGHT, SPARK_WIDTH, sparklineGeometry } from '@/shared/app/sparkline'

// AB-119: a decorative-supporting trend beside a KPI — no axes, no tooltips, no
// legend. The number next to it is the headline and carries the meaning, so the
// SVG stays out of the accessibility tree entirely.
const props = defineProps<{ values: number[] }>()

const geometry = computed(() => sparklineGeometry(props.values))
</script>

<template>
  <svg
    class="admin-spark"
    :class="{ flat: geometry.flat }"
    :viewBox="`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`"
    :width="SPARK_WIDTH"
    :height="SPARK_HEIGHT"
    aria-hidden="true"
    focusable="false"
  >
    <path v-if="geometry.area" class="admin-spark-area" :d="geometry.area" />
    <polyline class="admin-spark-line" :points="geometry.line" vector-effect="non-scaling-stroke" />
    <circle
      v-if="geometry.last"
      class="admin-spark-tip"
      :cx="geometry.last.x"
      :cy="geometry.last.y"
      r="2"
    />
  </svg>
</template>
