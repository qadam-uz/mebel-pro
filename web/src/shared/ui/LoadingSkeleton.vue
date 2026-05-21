<script setup lang="ts">
// Shimmering placeholders. `variant="block"` → a single .sk box (set height);
// `variant="lines"` → N .sk-line rows; `variant="rows"` → a skeleton <tbody>
// shaped like a table with `cols` columns and `rows` rows.
withDefaults(
  defineProps<{
    variant?: 'block' | 'lines' | 'rows'
    lines?: number
    rows?: number
    cols?: number
    height?: string
  }>(),
  { variant: 'lines', lines: 3, rows: 6, cols: 4, height: '96px' },
)
</script>

<template>
  <div v-if="variant === 'block'" class="sk" :style="{ height }" aria-hidden="true" />

  <div v-else-if="variant === 'lines'" aria-hidden="true">
    <div v-for="n in lines" :key="n" class="sk-line" :class="n === 1 ? 'w-80' : 'w-60'" />
  </div>

  <tbody v-else aria-hidden="true">
    <tr v-for="r in rows" :key="r">
      <td v-for="c in cols" :key="c">
        <span class="sk-line" :class="c === 1 ? 'w-80' : 'w-60'" />
      </td>
    </tr>
  </tbody>
</template>
