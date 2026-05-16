<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="flex min-h-full flex-col">
    <header class="border-b border-[#E5DDD0] bg-white">
      <nav class="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
        <RouterLink to="/" class="flex items-center gap-[10px] text-[#1A1614]">
          <img src="/favicon.svg" alt="" class="h-[30px] w-[30px]" />
          <span class="font-serif text-[19px] font-semibold tracking-[-0.01em]">Mebel Pro</span>
        </RouterLink>
        <RouterLink to="/about" class="text-sm text-[#5C4F44] hover:text-[#A6471F]"
          >About</RouterLink
        >
      </nav>
    </header>

    <main class="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
      <RouterView />
    </main>
  </div>
</template>
