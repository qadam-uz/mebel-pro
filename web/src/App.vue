<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="flex min-h-full flex-col">
    <header class="border-b border-gray-200 bg-white">
      <nav class="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
        <RouterLink to="/" class="font-semibold">Mebel Pro</RouterLink>
        <RouterLink to="/about" class="text-sm text-gray-600 hover:text-gray-900">About</RouterLink>
      </nav>
    </header>

    <main class="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
      <RouterView />
    </main>
  </div>
</template>
