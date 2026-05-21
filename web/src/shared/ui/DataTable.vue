<script setup lang="ts" generic="Row extends Record<string, unknown>">
// A thin generic table over the design system's .tbl. Columns describe header
// labels + alignment; the default-scoped `cell` slot renders each cell, or a
// per-column slot named `cell-<key>`. Clickable rows emit `row-click`.
import LoadingSkeleton from './LoadingSkeleton.vue'

export interface Column {
  key: string
  label: string
  align?: 'left' | 'right'
}

const props = withDefaults(
  defineProps<{
    columns: Column[]
    rows: Row[]
    rowKey?: (row: Row, index: number) => string | number
    clickable?: boolean
    loading?: boolean
  }>(),
  { clickable: false, loading: false },
)

const emit = defineEmits<{ 'row-click': [row: Row] }>()

function keyFor(row: Row, index: number): string | number {
  return props.rowKey ? props.rowKey(row, index) : index
}
</script>

<template>
  <table class="tbl">
    <thead>
      <tr>
        <th v-for="col in columns" :key="col.key" :class="{ right: col.align === 'right' }">
          {{ col.label }}
        </th>
      </tr>
    </thead>
    <LoadingSkeleton v-if="loading" variant="rows" :cols="columns.length" />
    <tbody v-else>
      <tr
        v-for="(row, index) in rows"
        :key="keyFor(row, index)"
        :class="{ clickable }"
        @click="clickable && emit('row-click', row)"
      >
        <td v-for="col in columns" :key="col.key" :class="{ right: col.align === 'right' }">
          <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
            <slot name="cell" :row="row" :column="col" :value="row[col.key]">
              {{ row[col.key] }}
            </slot>
          </slot>
        </td>
      </tr>
    </tbody>
  </table>
</template>
