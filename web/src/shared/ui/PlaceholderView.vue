<script setup lang="ts">
// Placeholder route view used while screens are filled in by later agents.
// Renders the page head + a friendly empty state so navigation/layout are
// exercisable end to end.
import { useRoute } from 'vue-router'
import EmptyState from './EmptyState.vue'

defineProps<{ title: string; sub?: string }>()
const route = useRoute()
</script>

<template>
  <div>
    <header class="page-head">
      <div>
        <h1>{{ title }}</h1>
        <p v-if="sub" class="sub">{{ sub }}</p>
      </div>
    </header>
    <EmptyState
      icon="◷"
      :title="title"
      :body="`Bu ekran keyingi bosqichda to'ldiriladi. (${route.path})`"
    />
  </div>
</template>
