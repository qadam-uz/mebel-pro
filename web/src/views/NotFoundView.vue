<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <section class="space-y-2">
    <h1 class="text-2xl font-semibold">404</h1>
    <p class="text-gray-600">Page not found.</p>
    <RouterLink to="/" class="text-blue-600 hover:underline">Go home</RouterLink>
  </section>
</template>
